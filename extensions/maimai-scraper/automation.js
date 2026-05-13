(function () {
  "use strict";

  var inputEl = document.getElementById("automation-input");
  var outputEl = document.getElementById("automation-output");
  var runButton = document.getElementById("automation-run");
  var statusButton = document.getElementById("automation-status");
  var exportButton = document.getElementById("automation-export");

  function render(value) {
    outputEl.textContent = JSON.stringify(value, null, 2);
  }

  function sendCommand(command) {
    return new Promise(function (resolve) {
      chrome.runtime.sendMessage(command, function (response) {
        if (chrome.runtime.lastError) {
          resolve({ ok: false, error: chrome.runtime.lastError.message });
          return;
        }
        resolve(response || { ok: false, error: "无响应" });
      });
    });
  }

  function readCommand() {
    var text = inputEl.value.trim();
    if (!text) return { type: "getDetailBatchStatus" };
    return JSON.parse(text);
  }

  function run(command) {
    return sendCommand(command).then(function (response) {
      render(response);
      return response;
    }).catch(function (err) {
      var response = { ok: false, error: err.message };
      render(response);
      return response;
    });
  }

  var api = {
    clearAll: function () {
      return run({ type: "clearAll" });
    },
    importDetailContacts: function (contacts) {
      return run({ type: "importDetailContacts", contacts: contacts || [] });
    },
    startDetailBatch: function (options) {
      options = options || {};
      return run({
        type: "startDetailBatch",
        mode: options.mode || "safe",
        dailyLimit: options.dailyLimit || 10000,
      });
    },
    getDetailBatchStatus: function () {
      return run({ type: "getDetailBatchStatus" });
    },
    getFullExportData: function () {
      return run({ type: "getFullExportData" });
    },
    preflightTrace: function (label) {
      return run({ type: "preflightTrace", label: label || "automation_preflight" });
    },
    probeOnly: function (label) {
      return run({ type: "probeOnly", label: label || "automation_probe" });
    },
    getDiagnosticTraces: function () {
      return run({ type: "getDiagnosticTraces" });
    },
    clearDiagnosticTraces: function () {
      return run({ type: "clearDiagnosticTraces" });
    },
    exportFullJson: function (filename) {
      return run({
        type: "exportFullJson",
        filename: filename || "maimai-export.json",
        saveAs: false,
      });
    },
    sendCommand: sendCommand,
  };

  window.maimaiScraperAutomation = api;

  runButton.addEventListener("click", function () {
    run(readCommand());
  });

  statusButton.addEventListener("click", function () {
    api.getDetailBatchStatus();
  });

  exportButton.addEventListener("click", function () {
    api.getFullExportData();
  });
})();
