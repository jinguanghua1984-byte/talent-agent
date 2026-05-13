// detail_batch.js — 批量详情抓取调度器
// 不直接访问页面，只编排 job、限流、熔断和状态持久化。

var DetailBatch = (function () {
  var DEFAULT_STATE = {
    status: "idle",
    mode: "safe",
    total_jobs: 0,
    current_index: 0,
    duplicate_contacts: 0,
    counts: { queued: 0, running: 0, done: 0, failed: 0, skipped: 0 },
    circuit_breaker: { tripped: false, reason: null },
    started_at: null,
    updated_at: null,
    finished_at: null,
    policy: null,
    batch_pause_started_at: null,
    batch_pause_until: null,
    batch_pause_delay_ms: 0,
    batch_pause_completed: 0,
  };

  var SAFE_POLICY = {
    minDelayMs: 5000,
    maxDelayMs: 12000,
    batchSize: 30,
    minBatchPauseMs: 5 * 60 * 1000,
    maxBatchPauseMs: 10 * 60 * 1000,
    dailyLimit: 10000,
    maxRetries: 2,
    circuitBreakerThreshold: 3,
  };

  var TEST_POLICY = {
    minDelayMs: 500,
    maxDelayMs: 1200,
    batchSize: 30,
    minBatchPauseMs: 2000,
    maxBatchPauseMs: 5000,
    dailyLimit: 10,
    maxRetries: 1,
    circuitBreakerThreshold: 3,
  };

  var state = copy(DEFAULT_STATE);
  var stopRequested = false;
  var pauseRequested = false;
  var importedContacts = [];
  var runGeneration = 0;

  function copy(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function now() {
    return new Date().toISOString();
  }

  function policyFor(options) {
    var mode = options && options.mode === "test" ? "test" : "safe";
    var base = mode === "test" ? copy(TEST_POLICY) : copy(SAFE_POLICY);
    if (options && options.dailyLimit) {
      base.dailyLimit = Math.max(1, Number(options.dailyLimit) || base.dailyLimit);
    }
    base.mode = mode;
    return base;
  }

  function randomDelay(min, max) {
    return Math.floor(min + Math.random() * (max - min));
  }

  function wait(ms) {
    return new Promise(function (resolve) {
      var started = Date.now();
      function tick() {
        if (stopRequested) {
          resolve(false);
          return;
        }
        if (pauseRequested || state.status === "paused") {
          setTimeout(tick, 500);
          return;
        }
        if (Date.now() - started >= ms) {
          resolve(true);
          return;
        }
        setTimeout(tick, 500);
      }
      tick();
    });
  }

  function contactId(contact) {
    return contact && (
      contact.id ||
      contact.uid ||
      contact.user_id ||
      contact.to_uid ||
      contact.platform_id
    );
  }

  function contactToken(contact) {
    return contact && (
      contact.trackable_token ||
      contact.trackableToken ||
      contact.trackable ||
      contact.token
    );
  }

  function makeJob(contact) {
    var id = contactId(contact);
    var token = contactToken(contact);
    var job = {
      id: id ? String(id) : "",
      name: contact.name || contact.real_name || "",
      company: contact.company || contact.current_company || "",
      position: contact.position || contact.title || contact.current_title || "",
      trackable_token: token ? String(token) : "",
      status: "queued",
      attempts: 0,
      started_at: null,
      finished_at: null,
      detail: {
        basic: null,
        projects: null,
        job_preference: null,
        contact_btn: null,
      },
      errors: [],
      source_contact: contact,
    };

    if (!job.id) {
      job.status = "skipped";
      job.errors.push("missing_id");
      job.finished_at = now();
    } else if (!job.trackable_token) {
      job.status = "skipped";
      job.errors.push("missing_trackable_token");
      job.finished_at = now();
    }
    return job;
  }

  function buildJobs(contacts) {
    var seen = {};
    var duplicates = 0;
    var jobs = [];
    (contacts || []).forEach(function (contact) {
      if (!contact) return;
      var id = contactId(contact);
      var key = id ? String(id) : "missing_" + jobs.length;
      if (id && seen[key]) {
        duplicates++;
        return;
      }
      if (id) seen[key] = true;
      jobs.push(makeJob(contact));
    });
    return { jobs: jobs, duplicates: duplicates };
  }

  function countsFor(jobs) {
    var counts = { queued: 0, running: 0, done: 0, failed: 0, skipped: 0 };
    (jobs || []).forEach(function (job) {
      if (Object.prototype.hasOwnProperty.call(counts, job.status)) {
        counts[job.status]++;
      }
    });
    return counts;
  }

  function updateStateFromJobs(jobs, patch) {
    state = Object.assign({}, state, patch || {});
    state.total_jobs = jobs.length;
    state.counts = countsFor(jobs);
    state.updated_at = now();
    return state;
  }

  function isAuthFailure(result) {
    if (!result) return true;
    if (result.authFailure) return true;
    var endpoints = result.endpoints || {};
    return Object.keys(endpoints).some(function (key) {
      var endpoint = endpoints[key];
      return endpoint && (
        endpoint.authFailure ||
        endpoint.httpStatus === 401 ||
        endpoint.httpStatus === 403 ||
        endpoint.httpStatus === 429
      );
    });
  }

  function endpointStatusSummary(result) {
    var endpoints = (result && result.endpoints) || {};
    var summary = {};
    Object.keys(endpoints).forEach(function (key) {
      var endpoint = endpoints[key] || {};
      summary[key] = {
        httpStatus: endpoint.httpStatus || 0,
        error: endpoint.error || null,
        authFailure: Boolean(endpoint.authFailure || endpoint.httpStatus === 429),
      };
    });
    return summary;
  }

  function jobSummary(job) {
    return {
      id: job.id,
      name: job.name,
      company: job.company,
      position: job.position,
      status: job.status,
      attempts: job.attempts,
      errors: job.errors || [],
    };
  }

  function clearBatchPause() {
    state.batch_pause_started_at = null;
    state.batch_pause_until = null;
    state.batch_pause_delay_ms = 0;
    state.batch_pause_completed = 0;
  }

  function detailRecordFromResult(job, result) {
    var endpoints = result.endpoints || {};
    return {
      id: String(job.id),
      url: endpoints.basic ? endpoints.basic.url : "",
      ts: now(),
      mode: "batch_replay",
      data: result.detail || null,
      job: {
        id: String(job.id),
        status: job.status,
      },
      endpoints: {
        basic: endpoints.basic || null,
        projects: endpoints.projects || null,
        job_preference: endpoints.job_preference || null,
        contact_btn: endpoints.contact_btn || null,
      },
    };
  }

  async function emit(onEvent, event) {
    if (onEvent) return onEvent(event);
    return Promise.resolve();
  }

  function persistState(saveState) {
    if (!saveState) return Promise.resolve();
    return saveState(copy(state));
  }

  async function run(jobs, options, callbacks) {
    runGeneration++;
    var generation = runGeneration;
    var policy = policyFor(options || {});
    var saveState = callbacks.saveState;
    var saveJob = callbacks.saveJob;
    var saveDetail = callbacks.saveDetail;
    var sendDetailFetch = callbacks.sendDetailFetch;
    var onEvent = callbacks.onEvent;
    var authFailures = 0;
    var processed = 0;

    stopRequested = false;
    pauseRequested = false;
    state = updateStateFromJobs(jobs, {
      status: "running",
      mode: policy.mode,
      current_index: 0,
      duplicate_contacts: options.duplicateContacts || 0,
      circuit_breaker: { tripped: false, reason: null },
      started_at: now(),
      finished_at: null,
      policy: policy,
      batch_pause_started_at: null,
      batch_pause_until: null,
      batch_pause_delay_ms: 0,
      batch_pause_completed: 0,
    });
    await persistState(saveState);
    if (generation !== runGeneration) return copy(state);
    await emit(onEvent, Object.assign({ type: "detail_batch_progress" }, copy(state)));

    for (var i = 0; i < jobs.length; i++) {
      if (stopRequested) break;
      state.current_index = i;
      if (processed >= policy.dailyLimit) {
        state.status = "paused";
        state.circuit_breaker = { tripped: false, reason: "daily_limit_reached" };
        await persistState(saveState);
        if (generation !== runGeneration) return copy(state);
        await emit(onEvent, Object.assign({ type: "detail_batch_paused", reason: "daily_limit_reached" }, copy(state)));
        return copy(state);
      }

      var job = jobs[i];
      if (job.status === "skipped" || job.status === "done") {
        await saveJob(job);
        if (generation !== runGeneration) return copy(state);
        updateStateFromJobs(jobs);
        await persistState(saveState);
        if (generation !== runGeneration) return copy(state);
        continue;
      }

      job.status = "running";
      job.started_at = job.started_at || now();
      await saveJob(job);
      if (generation !== runGeneration) return copy(state);
      updateStateFromJobs(jobs);
      await persistState(saveState);
      if (generation !== runGeneration) return copy(state);
      await emit(onEvent, Object.assign({ type: "detail_batch_progress", job: job }, copy(state)));

      var result = null;
      var success = false;
      while (job.attempts <= policy.maxRetries && !success && !stopRequested) {
        job.attempts++;
        result = await sendDetailFetch(job);
        if (generation !== runGeneration) return copy(state);
        success = Boolean(result && result.ok);
        if (!success && job.attempts <= policy.maxRetries) {
          await wait(randomDelay(2000, 5000));
          if (generation !== runGeneration) return copy(state);
        }
      }

      job.finished_at = now();
      var riskFailure = false;
      if (success) {
        job.status = "done";
        job.detail = {
          basic: result.detail || null,
          projects: result.endpoints ? result.endpoints.projects : null,
          job_preference: result.endpoints ? result.endpoints.job_preference : null,
          contact_btn: result.endpoints ? result.endpoints.contact_btn : null,
        };
        job.errors = result.errors || [];
        authFailures = 0;
        await saveDetail(detailRecordFromResult(job, result));
        if (generation !== runGeneration) return copy(state);
      } else {
        job.status = "failed";
        job.errors = (result && (result.errors || [result.error])) || ["detail_fetch_failed"];
        riskFailure = isAuthFailure(result);
        if (riskFailure) {
          authFailures++;
        }
      }

      processed++;
      await saveJob(job);
      if (generation !== runGeneration) return copy(state);
      updateStateFromJobs(jobs);
      await persistState(saveState);
      if (generation !== runGeneration) return copy(state);
      await emit(onEvent, Object.assign({ type: "detail_batch_progress", job: job }, copy(state)));
      if (success) {
        await emit(onEvent, Object.assign({
          type: "detail_batch_job_succeeded",
          job: jobSummary(job),
          warnings: job.errors || [],
          endpoints: endpointStatusSummary(result),
        }, copy(state)));
      } else {
        await emit(onEvent, Object.assign({
          type: "detail_batch_job_failed",
          job: jobSummary(job),
          reason: (job.errors && job.errors[0]) || "detail_fetch_failed",
          riskFailure: riskFailure,
          endpoints: endpointStatusSummary(result),
        }, copy(state)));
      }

      if (authFailures >= policy.circuitBreakerThreshold) {
        state.status = "paused";
        state.circuit_breaker = {
          tripped: true,
          reason: "连续 " + policy.circuitBreakerThreshold + " 次认证或风控失败",
        };
        await persistState(saveState);
        if (generation !== runGeneration) return copy(state);
        await emit(onEvent, Object.assign({ type: "detail_batch_paused", reason: state.circuit_breaker.reason }, copy(state)));
        return copy(state);
      }

      if ((i + 1) < jobs.length && processed % policy.batchSize === 0) {
        var batchDelay = randomDelay(policy.minBatchPauseMs, policy.maxBatchPauseMs);
        var batchPauseStarted = new Date();
        var completedForBatchPause = (state.counts.done || 0) + (state.counts.failed || 0) + (state.counts.skipped || 0);
        state.batch_pause_started_at = batchPauseStarted.toISOString();
        state.batch_pause_until = new Date(batchPauseStarted.getTime() + batchDelay).toISOString();
        state.batch_pause_delay_ms = batchDelay;
        state.batch_pause_completed = completedForBatchPause;
        state.updated_at = now();
        await persistState(saveState);
        if (generation !== runGeneration) return copy(state);
        await emit(onEvent, Object.assign({ type: "detail_batch_paused", reason: "batch_pause", delayMs: batchDelay }, copy(state)));
        var shouldContinueAfterBatch = await wait(batchDelay);
        if (generation !== runGeneration) return copy(state);
        if (!shouldContinueAfterBatch) break;
        clearBatchPause();
        state.updated_at = now();
        await persistState(saveState);
        if (generation !== runGeneration) return copy(state);
      } else if ((i + 1) < jobs.length) {
        var delay = randomDelay(policy.minDelayMs, policy.maxDelayMs);
        var shouldContinue = await wait(delay);
        if (generation !== runGeneration) return copy(state);
        if (!shouldContinue) break;
      }
    }

    if (generation !== runGeneration) return copy(state);
    state = updateStateFromJobs(jobs, {
      status: stopRequested ? "stopped" : "completed",
      finished_at: now(),
      batch_pause_started_at: null,
      batch_pause_until: null,
      batch_pause_delay_ms: 0,
      batch_pause_completed: 0,
    });
    await persistState(saveState);
    if (generation !== runGeneration) return copy(state);
    await emit(onEvent, Object.assign({
      type: stopRequested ? "detail_batch_stopped" : "detail_batch_completed",
    }, copy(state)));
    return copy(state);
  }

  return {
    importContacts: function (contacts) {
      importedContacts = contacts || [];
      return importedContacts.length;
    },

    getImportedContacts: function () {
      return importedContacts.slice();
    },

    createJobs: function (contacts) {
      return buildJobs(contacts || importedContacts);
    },

    run: run,

    pause: function () {
      pauseRequested = true;
      state.status = "paused";
      clearBatchPause();
      state.updated_at = now();
      return copy(state);
    },

    resume: function () {
      pauseRequested = false;
      if (state.status === "paused") {
        state.status = "running";
        state.updated_at = now();
      }
      return copy(state);
    },

    stop: function () {
      stopRequested = true;
      state.status = "stopped";
      clearBatchPause();
      state.updated_at = now();
      return copy(state);
    },

    reset: function () {
      runGeneration++;
      stopRequested = true;
      pauseRequested = false;
      importedContacts = [];
      state = copy(DEFAULT_STATE);
      state.updated_at = now();
      return copy(state);
    },

    getState: function () {
      return copy(state);
    },
  };
})();
