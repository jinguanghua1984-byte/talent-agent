import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "extensions" / "maimai-scraper"


def read_extension_file(name: str) -> str:
    return (EXTENSION_DIR / name).read_text(encoding="utf-8")


def test_manifest_is_json_and_version_is_2_4():
    manifest = json.loads(read_extension_file("manifest.json"))

    assert manifest["version"] == "2.4"
    assert manifest["name"] == "脉脉人选数据采集"
    assert manifest["action"]["default_title"] == "脉脉人选数据采集"


def test_background_imports_detail_batch():
    background = read_extension_file("background.js")

    assert "importScripts" in background
    assert "detail_batch.js" in background


def test_idb_exposes_detail_db_contract():
    idb = read_extension_file("idb.js")

    assert "DetailDB" in idb
    for method in ["getAllJobs", "getAllDetails", "clear"]:
        assert method in idb


def test_background_handles_detail_batch_messages():
    background = read_extension_file("background.js")

    for message_type in [
        "startDetailBatch",
        "pauseDetailBatch",
        "resumeDetailBatch",
        "stopDetailBatch",
        "getDetailBatchStatus",
    ]:
        assert message_type in background


def test_content_handles_detail_fetch_bridge():
    content = read_extension_file("content.js")

    assert "detailFetch" in content


def test_inject_handles_detail_fetch_and_required_endpoints():
    inject = read_extension_file("inject.js")

    assert "__MAIMAI_DETAIL_FETCH__" in inject
    for endpoint in [
        "/api/ent/talent/basic",
        "/api/ent/candidate/associated/project/list",
        "/api/ent/talent/job_preference",
    ]:
        assert endpoint in inject


def test_popup_contains_detail_tab_and_start_button():
    popup_html = read_extension_file("popup.html")
    workbench_html = read_extension_file("workbench.html")

    assert "脉脉人选数据采集" in popup_html
    assert "popup-summary" in popup_html
    assert "btn-open-workbench" in popup_html
    assert "btn-start-detail-batch" in workbench_html
    assert "detail-log-list" in workbench_html
    assert "btn-start-pager" in workbench_html
    assert "pager-log-list" in workbench_html
    assert 'data-tab="capture"' not in popup_html
    assert 'data-tab="detail"' not in popup_html
    assert "btn-start-detail-batch" not in popup_html
    assert "主动搜索" not in popup_html
    assert "DOM 抓取" not in popup_html


def test_export_full_json_exports_detail_jobs():
    background = read_extension_file("background.js")

    assert "exportFullJson" in background
    assert "detailJobs" in background


def test_full_export_supports_unattended_data_return():
    background = read_extension_file("background.js")

    assert "function buildFullExportData" in background
    assert "getFullExportData" in background
    assert "msg.saveAs === false" in background
    assert "sendResponse({ ok: true, data: data })" in background


def test_automation_page_exposes_detail_bridge_without_popup_dom():
    automation_html = read_extension_file("automation.html")
    automation_js = read_extension_file("automation.js")
    manifest = json.loads(read_extension_file("manifest.json"))

    assert "automation.js" in automation_html
    assert "function sendCommand" in automation_js
    for message_type in [
        "clearAll",
        "importDetailContacts",
        "startDetailBatch",
        "getDetailBatchStatus",
        "getFullExportData",
    ]:
        assert message_type in automation_js
    assert "document.getElementById(\"popup\"" not in automation_js
    resources = manifest.get("web_accessible_resources", [])
    resource_names = {
        item
        for group in resources
        for item in group.get("resources", [])
    }
    assert "automation.html" in resource_names
    assert "automation.js" in resource_names


def test_detail_daily_limit_defaults_to_10000_without_popup_controls():
    detail_batch = read_extension_file("detail_batch.js")
    popup_html = read_extension_file("popup.html")
    popup_js = read_extension_file("popup.js")
    automation_js = read_extension_file("automation.js")

    safe_policy_block = detail_batch.split("var SAFE_POLICY =", 1)[1].split("var TEST_POLICY =", 1)[0]
    assert "dailyLimit: 10000" in safe_policy_block
    assert "detail-daily-limit" not in popup_html
    assert "detail-mode" not in popup_html
    assert "detailDailyLimitEl" not in popup_js
    assert "detailModeEl" not in popup_js
    assert "dailyLimit: options.dailyLimit || 10000" in automation_js


def test_background_exposes_diagnostic_trace_contract_without_real_detail_fetch():
    background = read_extension_file("background.js")

    for message_type in [
        "preflightTrace",
        "probeOnly",
        "getDiagnosticTraces",
        "clearDiagnosticTraces",
    ]:
        assert message_type in background
    assert "function buildDiagnosticTrace" in background
    assert "function recordDiagnosticTrace" in background
    assert "diagnosticTraces" in background
    assert "sender.url" in background
    assert "activeTab" in background
    assert "windowFocused" in background
    assert "tracePageState" in background
    probe_block = background.split('if (msg.type === "probeOnly")', 1)[1].split('if (msg.type === "startDetailBatch")', 1)[0]
    assert "sendDetailFetch" not in probe_block
    assert "DetailBatch.run" not in probe_block


def test_automation_page_exposes_trace_probe_api():
    automation_js = read_extension_file("automation.js")

    for api_name in [
        "preflightTrace",
        "probeOnly",
        "getDiagnosticTraces",
        "clearDiagnosticTraces",
    ]:
        assert api_name + ":" in automation_js
    assert '{ type: "preflightTrace"' in automation_js
    assert '{ type: "probeOnly"' in automation_js
    assert '{ type: "getDiagnosticTraces"' in automation_js
    assert '{ type: "clearDiagnosticTraces"' in automation_js


def test_content_trace_page_state_is_non_intrusive():
    content = read_extension_file("content.js")
    trace_block = content.split('if (msg.type === "tracePageState")', 1)[1].split('if (msg.type === "detailFetch")', 1)[0]

    assert 'location.href' in trace_block
    assert 'document.title' in trace_block
    assert 'document.visibilityState' in trace_block
    assert 'document.hasFocus()' in trace_block
    assert "__MAIMAI_DETAIL_FETCH__" not in trace_block
    assert "window.postMessage" not in trace_block


def test_background_records_diagnostic_trace_for_key_batch_actions():
    background = read_extension_file("background.js")

    assert "function recordActionDiagnosticTrace" in background
    for action in [
        'recordActionDiagnosticTrace("clearAll"',
        'recordActionDiagnosticTrace("getFullExportData"',
        'recordActionDiagnosticTrace("importDetailContacts"',
        'recordActionDiagnosticTrace("startDetailBatch"',
        'recordActionDiagnosticTrace("getDetailBatchStatus"',
    ]:
        assert action in background
    assert "diagnosticTraces: []" in background
    assert "diagnosticTraces: stored.diagnosticTraces || []" in background


def test_popup_hides_local_detail_plan_loader():
    manifest = json.loads(read_extension_file("manifest.json"))
    popup_html = read_extension_file("popup.html")
    popup_js = read_extension_file("popup.js")
    workbench_js = read_extension_file("workbench.js")

    assert "http://127.0.0.1/*" in manifest["host_permissions"]
    assert "http://localhost/*" in manifest["host_permissions"]
    assert "detail-local-plan-url" not in popup_html
    assert "btn-load-local-detail-plan" not in popup_html
    assert "btn-load-start-local-detail-plan" not in popup_html
    assert "detail-local-plan-status" not in popup_html
    assert "function loadLocalDetailPlan" not in popup_js
    assert "fetch(localPlanUrl" not in popup_js
    assert 'type: "startDetailBatch"' in workbench_js


def test_detail_import_accepts_recommendation_shapes():
    background = read_extension_file("background.js")
    workbench_js = read_extension_file("workbench.js")

    for key in ["top10", "candidates", "matches", "results", "items"]:
        assert key in background
    assert "parseMaimaiProfileUrl" in background
    assert "normalizeImportContacts" in background
    assert 'type: "importDetailContacts"' in workbench_js
    assert "contacts: JSON.parse(reader.result)" in workbench_js


def test_detail_db_supports_targeted_reset_methods():
    idb = read_extension_file("idb.js")

    assert "clearJobs" in idb
    assert "clearDetails" in idb


def test_detail_batch_exposes_reset_contract():
    detail_batch = read_extension_file("detail_batch.js")

    assert "reset: function" in detail_batch
    assert "importedContacts = []" in detail_batch
    assert "copy(DEFAULT_STATE)" in detail_batch


def test_detail_batch_reset_invalidates_in_flight_runs():
    detail_batch = read_extension_file("detail_batch.js")

    assert "runGeneration" in detail_batch
    assert "var generation = runGeneration" in detail_batch
    assert "generation !== runGeneration" in detail_batch
    assert "runGeneration++" in detail_batch


def test_background_replaces_stale_detail_jobs_before_new_run():
    background = read_extension_file("background.js")

    assert "resetDetailBatch" in background
    assert "appendDetailBatchLog" in background
    assert "detailBatchLogs" in background
    assert "DetailDB.clear()" in background
    assert "DetailBatch.reset()" in background
    assert "totalJobs: jobs.length" in background


def test_background_exposes_summary_and_open_main_page_messages():
    background = read_extension_file("background.js")

    assert "getScraperSummary" in background
    assert "openMainPage" in background
    assert "openWorkbenchPage" in background
    assert "chrome.sidePanel.open" in background
    assert "sidePanelOpenOptions" in background


def test_workbench_opener_uses_side_panel_window_context_without_tab_fallback():
    background = read_extension_file("background.js")
    popup_js = read_extension_file("popup.js")

    assert "chrome.windows.getCurrent" in popup_js
    assert 'type: "openWorkbench", windowId: windowInfo && windowInfo.id' in popup_js

    opener_block = background.split("function openWorkbenchPage", 1)[1].split("function saveDetailBatchState", 1)[0]
    assert "function sidePanelOpenOptions" in background
    assert "msg.windowId" in background
    assert 'typeof sender.tab.windowId === "number"' in background
    assert "chrome.sidePanel.open(openOptions)" in opener_block
    assert "chrome.sidePanel.open({})" not in opener_block
    assert "openTabFallback" not in opener_block
    assert "opened: \"tab\"" not in opener_block
    assert "chrome.tabs.create" not in opener_block


def test_background_summary_detail_exposes_popup_status_shape():
    background = read_extension_file("background.js")
    summary_block = background.split("function buildScraperSummary()", 1)[1].split("function detailBatchContacts()", 1)[0]

    assert "running: Boolean(detailBatchState &&" in summary_block
    assert 'detailBatchState.status === "running"' in summary_block
    assert 'detailBatchState.status === "paused"' in summary_block
    assert 'completed: Boolean(detailBatchState && detailBatchState.status === "completed")' in summary_block
    assert "totalJobs: detailBatchState.total_jobs || detailJobs.length" in summary_block
    assert "counts: detailStatusCounts(detailJobs, detailBatchState)" in summary_block
    assert "storageCounts: detailCounts" in summary_block
    assert "jobs: detailJobs.length" in summary_block


def test_background_guards_stale_detail_batch_callbacks():
    background = read_extension_file("background.js")
    full_export_builder = background.split("function buildFullExportData()", 1)[1].split("function downloadJsonData", 1)[0]

    assert "__detailBatchRunToken" in background
    assert "__detailBatchRunToken++" in background
    assert "var runToken = __detailBatchRunToken" in background
    assert "runToken !== __detailBatchRunToken" in background
    assert "run_token" in background
    assert "filterDetailBatchJobs" in background
    assert "filterDetailBatchRecords" in background
    assert "tagDetailBatchRecord(job, runToken)" in background
    assert "tagDetailBatchRecord(detail, runToken)" in background
    assert "detailBatchRunToken: __detailBatchRunToken" in full_export_builder
    assert "filterDetailBatchJobs(detailJobs, currentRunToken)" in full_export_builder
    assert "filterDetailBatchRecords(detailDbDetails, currentRunToken)" in full_export_builder


def test_background_captures_detail_batch_token_before_start_prework():
    background = read_extension_file("background.js")
    start_block = background.split('if (msg.type === "startDetailBatch")', 1)[1].split('if (msg.type === "pauseDetailBatch")', 1)[0]

    assert start_block.index("var runToken = __detailBatchRunToken") < start_block.index("Promise.all([")


def test_background_persists_current_detail_batch_token_with_state():
    background = read_extension_file("background.js")
    save_state_block = background.split("function saveDetailBatchState", 1)[1].split("function appendStorageDetail", 1)[0]

    assert "detailBatchRunToken: runToken || __detailBatchRunToken" in save_state_block


def test_background_reset_detail_batch_clears_persisted_state():
    background = read_extension_file("background.js")
    reset_block = background.split('if (msg.type === "resetDetailBatch")', 1)[1].split('if (msg.type === "startDetailBatch")', 1)[0]

    assert "contacts: []" in reset_block
    assert "detailBatchState: null" in reset_block
    assert "detailBatchRunToken: __detailBatchRunToken" in reset_block
    assert "state: resetState" in reset_block


def test_popup_detail_tab_hides_extra_controls_and_keeps_realtime_logs():
    popup_html = read_extension_file("popup.html")
    popup_js = read_extension_file("popup.js")
    workbench_html = read_extension_file("workbench.html")
    workbench_js = read_extension_file("workbench.js")

    assert "btn-reset-detail-batch" not in popup_html
    assert "btn-pause-detail-batch" not in popup_html
    assert "btn-resume-detail-batch" not in popup_html
    assert "btn-refresh-detail-batch" not in popup_html
    assert "开始人选详情采集" in workbench_html
    assert ">终止<" in workbench_html
    assert "detail-log-list" in workbench_html
    assert "btn-start-detail-batch" in workbench_html
    assert "detail-log-list" not in popup_html
    assert "btn-start-detail-batch" not in popup_html
    assert "resetDetailBatch" not in popup_js
    assert "startDetailBatch" not in popup_js
    assert "renderDetailLogs" in workbench_js
    assert "detailLogs.slice(-80).reverse()" in workbench_js
    assert 'type: "startDetailBatch"' in workbench_js
    assert 'type: "stopDetailBatch"' in workbench_js
    assert 'type: "getWorkbenchSnapshot"' in workbench_js
    assert "chrome.storage.onChanged.addListener" in workbench_js
    assert "getScraperSummary" in popup_js
    assert 'type: "openWorkbench"' in popup_js
    assert 'type: "exportFullJson"' in popup_js


def test_popup_capture_tab_has_split_exports_and_pager_logs():
    popup_html = read_extension_file("popup.html")
    popup_js = read_extension_file("popup.js")
    workbench_html = read_extension_file("workbench.html")
    workbench_js = read_extension_file("workbench.js")
    background = read_extension_file("background.js")

    assert "btn-refresh" in popup_html
    assert "btn-open-workbench" in popup_html
    assert "btn-export-full" in popup_html
    assert "btn-export-capture" in workbench_html
    assert "导出被动拦截 JSON" in workbench_html
    assert "btn-export-pager" in workbench_html
    assert "导出人选列表 JSON" in workbench_html
    assert "pager-log-list" in workbench_html
    assert "列表执行日志" in workbench_html
    assert "人选列表逐页采集" in workbench_html
    assert "capture-log-list" not in popup_html
    assert "btn-export-pager" not in popup_html
    assert '{ type: "getScraperSummary" }' in popup_js
    assert '{ type: "exportFullJson", filename: filename }' in popup_js
    assert 'type: "exportCaptureJson"' in workbench_js
    assert 'type: "exportPagerJson"' in workbench_js
    assert "renderPagerLogs" in workbench_js
    assert "pagerLogs.slice(-80).reverse()" in workbench_js
    assert "appendPagerLog" not in popup_js
    assert "pager_progress" not in popup_js
    assert "exportCaptureJson" in background
    assert "exportPagerJson" in background


def test_content_mounts_floating_scraper_widget():
    content = read_extension_file("content.js")

    assert "mountFloatingScraperWidget" in content
    assert "maimai-scraper-floating-host" in content
    assert "getScraperSummary" in content
    assert "openMainPage" in content
    assert "setInterval(refresh, 2000)" in content
    for label in [
        "联系人",
        "详情",
        "执行中",
        "导出 JSON",
    ]:
        assert label in content


def test_detail_batch_persists_batch_pause_window():
    detail_batch = read_extension_file("detail_batch.js")

    for marker in [
        "batch_pause_until",
        "batch_pause_delay_ms",
        "batch_pause_completed",
        "batch_pause_started_at",
    ]:
        assert marker in detail_batch
    assert 'reason: "batch_pause"' in detail_batch
    assert "await persistState(saveState)" in detail_batch


def test_background_recovers_expired_batch_pause_from_persisted_jobs():
    background = read_extension_file("background.js")
    status_block = background.split('if (msg.type === "getDetailBatchStatus")', 1)[1].split("// ---- AutoPager", 1)[0]

    assert "function recoverExpiredBatchPauseIfNeeded" in background
    assert "function runDetailBatchJobs" in background
    assert "batch_pause_until" in background
    assert "DetailDB.getAllJobs()" in background
    assert "chrome.tabs.get" in background
    assert "DetailBatch.run(jobs" in background
    assert "__detailBatchRunning" in background
    assert "批间休息到点，自动继续" in background
    assert "recoverExpiredBatchPauseIfNeeded()" in status_block


def test_batch_pause_progress_uses_cumulative_completed_count_after_resume():
    detail_batch = read_extension_file("detail_batch.js")
    background = read_extension_file("background.js")
    workbench_js = read_extension_file("workbench.js")
    content = read_extension_file("content.js")

    assert "completedForBatchPause" in detail_batch
    assert "state.batch_pause_completed = completedForBatchPause" in detail_batch
    assert "Math.max(batchCompleted, counted)" in background
    assert "Math.max(detailState.batch_pause_completed || 0, completed)" in workbench_js
    assert "Math.max(state.batch_pause_completed || 0, completedJobs)" in content


def test_background_explains_batch_pause_and_rate_limit_logs():
    background = read_extension_file("background.js")
    detail_batch = read_extension_file("detail_batch.js")
    inject = read_extension_file("inject.js")

    assert "formatDelayMs" in background
    assert "批间暂停" in background
    assert "后继续" in background
    assert "detail_batch_job_failed" in background
    assert "详情抓取失败" in background
    assert "429" in detail_batch
    assert "429" in inject


def test_popup_and_floating_widget_show_batch_pause_as_resting():
    popup = read_extension_file("popup.js")
    workbench = read_extension_file("workbench.js")
    content = read_extension_file("content.js")

    assert "batch_pause_until" not in popup
    assert "批间休息中" not in popup
    assert "batch_pause_until" in workbench
    assert "批间休息中" in workbench
    assert "batch_pause_until" in content
    assert "批间休息中" in content


def test_search_template_tracks_headers_and_nested_pagination():
    inject = read_extension_file("inject.js")
    workbench_html = read_extension_file("workbench.html")
    workbench_js = read_extension_file("workbench.js")
    background = read_extension_file("background.js")
    popup = read_extension_file("popup.js")

    for marker in [
        "headerNames",
        "requestHeaders",
        "extractPageMeta",
        "applyPagerPage",
        "paginationParam",
        "total_match",
    ]:
        assert marker in inject
    assert "pager-template-info" in workbench_html
    assert "pager-meta-info" in workbench_html
    assert 'type: "startPager"' in workbench_js
    assert "renderPagerLogs" in workbench_js
    assert "headerNames" in background
    assert "pageMeta" in background
    assert "请求头" not in popup
    assert "headerList.join" not in popup


def test_active_search_patches_nested_search_query_fields():
    inject = read_extension_file("inject.js")

    assert "applySearchQuery(body, params.body.query)" in inject
    assert 'body.search.query = query' in inject
    assert 'body.search.search_query = query' in inject
    assert 'body.query = query' in inject


def test_autopager_updates_total_from_api_response():
    autopager = read_extension_file("autopager.js")
    background = read_extension_file("background.js")

    assert "updatePageMetaFromResponse" in autopager
    assert "state.totalFromApi" in autopager
    assert "state.totalPages" in autopager
    assert "pageMeta" in background
    assert "headerNames" in background


def test_detail_batch_logs_each_job_success_and_failure():
    detail_batch = read_extension_file("detail_batch.js")
    background = read_extension_file("background.js")
    popup = read_extension_file("popup.js")
    popup_html = read_extension_file("popup.html")
    workbench_js = read_extension_file("workbench.js")
    workbench_html = read_extension_file("workbench.html")

    assert "detail_batch_job_succeeded" in detail_batch
    assert "detail_batch_job_failed" in detail_batch
    assert "详情抓取成功" in background
    assert "详情抓取失败" in background
    assert "endpointStatusText" in background
    assert "renderDetailLogs" in workbench_js
    assert "detailLogs.slice(-80).reverse()" in workbench_js
    assert "chrome.storage.onChanged.addListener" in workbench_js
    assert "detail-log-list" in workbench_html
    assert "详情执行日志" in workbench_html
    assert "runtime.onMessage" not in popup
    assert "detail-log-list" not in popup_html
    assert "async function emit" in detail_batch
    assert "return onEvent(event)" in detail_batch
    assert "await emit(onEvent" in detail_batch


def test_manifest_declares_side_panel_workbench():
    manifest = json.loads(read_extension_file("manifest.json"))

    assert "sidePanel" in manifest["permissions"]
    assert manifest["side_panel"]["default_path"] == "workbench.html"
    assert manifest["action"]["default_popup"] == "popup.html"


def test_workbench_files_define_restoreable_ui_contract():
    workbench_html = read_extension_file("workbench.html")
    workbench_js = read_extension_file("workbench.js")
    workbench_css = read_extension_file("workbench.css")

    assert 'id="workbench-root"' in workbench_html
    assert "workbench.css" in workbench_html
    assert "workbench.js" in workbench_html
    for marker in [
        "btn-start-pager",
        "btn-stop-pager",
        "btn-export-pager",
        "detail-import-file",
        "btn-start-detail-batch",
        "btn-stop-detail-batch",
        "btn-export-detail-batch",
        "btn-export-capture",
        "btn-clear-all",
        "pager-log-list",
        "detail-log-list",
    ]:
        assert marker in workbench_html
    for marker in [
        'type: "getWorkbenchSnapshot"',
        'type: "setWorkbenchView"',
        'type: "startPager"',
        'type: "stopPager"',
        'type: "exportPagerJson"',
        'type: "importDetailContacts"',
        'type: "startDetailBatch"',
        'type: "stopDetailBatch"',
        'type: "exportFullJson"',
        "chrome.storage.onChanged.addListener",
        "renderPagerLogs",
        "renderDetailLogs",
    ]:
        assert marker in workbench_js
    assert ".workbench-shell" in workbench_css
    assert ".log-list" in workbench_css


def test_background_exposes_workbench_state_snapshot_and_logs():
    background = read_extension_file("background.js")

    for marker in [
        "DEFAULT_WORKBENCH_STATE",
        "workbenchState",
        "pagerLogs",
        "getWorkbenchSnapshot",
        "setWorkbenchView",
        "appendPagerLog",
        "clearPagerLogs",
        "recordExportResult",
        "updateWorkbenchPagerStateFromEvent",
        "buildWorkbenchSnapshot",
        "openWorkbench",
        "chrome.sidePanel.open",
        "workbench.html",
    ]:
        assert marker in background

    pager_block = background.split("AutoPager.run", 1)[1].split("safeRespond", 1)[0]
    assert "updateWorkbenchPagerStateFromEvent(event" in pager_block
    assert "chrome.runtime.sendMessage(event)" in pager_block


def test_workbench_refreshes_detail_state_and_disables_running_controls():
    workbench_js = read_extension_file("workbench.js")

    storage_block = workbench_js.split("chrome.storage.onChanged.addListener", 1)[1].split("renderAll();", 1)[0]
    for marker in [
        "changes.detailBatchState",
        "changes.detailImportedContacts",
        "changes.detailBatchRunToken",
        "changes.detailBatchLogs",
        "scheduleSnapshotRefresh()",
    ]:
        assert marker in storage_block

    for marker in [
        "function updateControlStates()",
        "isPagerActiveStatus",
        "isDetailActiveStatus",
        '$("btn-start-pager").disabled = pagerActive',
        '$("btn-stop-pager").disabled = !pagerActive || pagerStopping',
        '$("btn-start-detail-batch").disabled = detailActive',
        '$("btn-stop-detail-batch").disabled = !detailActive || detailStopping',
        '$("detail-import-file").disabled = detailActive',
    ]:
        assert marker in workbench_js


def test_background_rejects_duplicate_pager_and_detail_batch_starts():
    background = read_extension_file("background.js")

    detail_start_block = background.split('if (msg.type === "startDetailBatch")', 1)[1].split('if (msg.type === "pauseDetailBatch")', 1)[0]
    for marker in [
        "__detailBatchStarting",
        "__detailBatchRunning || __detailBatchStarting",
        "isActiveDetailBatchState(storedState)",
        "批量详情正在运行，请先终止当前任务",
        "__detailBatchStarting = true",
        "__detailBatchStarting = false",
    ]:
        assert marker in detail_start_block

    pager_start_block = background.split('if (msg.type === "startPager")', 1)[1].split('if (msg.type === "stopPager")', 1)[0]
    assert "__pagerStarting || (__activePager && __activePager.running)" in pager_start_block
    assert "__pagerStarting = true" in pager_start_block
    assert "__pagerStarting = false" in pager_start_block
    assert "人选列表采集正在运行，请先停止当前任务" in pager_start_block


def test_start_pager_keeps_existing_contact_count_in_scope():
    background = read_extension_file("background.js")
    pager_start_block = background.split('if (msg.type === "startPager")', 1)[1].split('if (msg.type === "stopPager")', 1)[0]

    assert "var existingContactCount = 0" in pager_start_block
    assert "existingContactCount = existingContacts.length" in pager_start_block
    assert "total_contacts: existingContactCount" in pager_start_block
    after_append_block = pager_start_block.split("PagerDB.append(existingContacts)", 1)[1]
    assert "existingContacts.length" not in after_append_block


def test_popup_is_launcher_not_long_running_console():
    popup_html = read_extension_file("popup.html")
    popup_js = read_extension_file("popup.js")

    assert "btn-open-workbench" in popup_html
    assert "打开工作台" in popup_html
    assert "popup-summary" in popup_html
    assert 'type: "openWorkbench"' in popup_js
    assert 'type: "getScraperSummary"' in popup_js
    assert 'type: "exportFullJson"' in popup_js
    assert "pagerExecutionLogs" not in popup_js
    assert "setInterval(refreshPagerInfo" not in popup_js
    assert "capture-log-list" not in popup_html
    assert "detail-log-list" not in popup_html


def assert_manifest_keeps_main_world_inject_script():
    manifest = json.loads(read_extension_file("manifest.json"))

    def is_main_world_maimai_inject_script(script):
        matches = script.get("matches", [])
        return (
            "inject.js" in script.get("js", [])
            and script.get("world") == "MAIN"
            and (
                "*://*.maimai.cn/*" in matches
                or "*://maimai.cn/*" in matches
            )
        )

    assert any(
        is_main_world_maimai_inject_script(script)
        for script in manifest["content_scripts"]
    )


def assert_no_direct_maimai_business_fetch_calls(text):
    compact = text.replace(" ", "")
    for forbidden in [
        'fetch("/api/',
        "fetch('/api/",
        'fetch("https://maimai.cn/api',
        "fetch('https://maimai.cn/api",
        'fetch("https://www.maimai.cn/api',
        "fetch('https://www.maimai.cn/api",
        'fetch("https://maimai.cn/ent/',
        "fetch('https://maimai.cn/ent/",
        'fetch("https://www.maimai.cn/ent/',
        "fetch('https://www.maimai.cn/ent/",
    ]:
        assert forbidden not in compact


def test_workbench_and_popup_do_not_directly_fetch_maimai_business_urls():
    assert_manifest_keeps_main_world_inject_script()
    for name in ["workbench.js", "popup.js"]:
        assert_no_direct_maimai_business_fetch_calls(read_extension_file(name))

    assert_no_direct_maimai_business_fetch_calls(read_extension_file("background.js"))
    assert "__MAIMAI_PAGER_FETCH__" in read_extension_file("content.js")
    assert "origFetch.call(window, tpl.url" in read_extension_file("inject.js")
    assert "__MAIMAI_DETAIL_FETCH__" in read_extension_file("content.js")
    assert "fetchDetailEndpoint(\"basic\", urls.basic)" in read_extension_file("inject.js")


def test_open_main_page_delegates_to_workbench():
    background = read_extension_file("background.js")
    content = read_extension_file("content.js")

    open_main_block = background.split('if (msg.type === "openMainPage")', 1)[1].split('if (msg.type === "clearAll")', 1)[0]
    assert "openWorkbenchPage" in open_main_block
    assert "popup.html" not in open_main_block
    assert 'safeSendMessage({ type: "openMainPage" })' in content
