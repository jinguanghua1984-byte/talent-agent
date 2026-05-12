import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "extensions" / "maimai-scraper"


def read_extension_file(name: str) -> str:
    return (EXTENSION_DIR / name).read_text(encoding="utf-8")


def test_manifest_is_json_and_version_is_2_4():
    manifest = json.loads(read_extension_file("manifest.json"))

    assert manifest["version"] == "2.4"


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

    assert 'data-tab="detail"' in popup_html
    assert "btn-start-detail-batch" in popup_html


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


def test_detail_import_accepts_recommendation_shapes():
    background = read_extension_file("background.js")
    popup = read_extension_file("popup.js")

    for key in ["top10", "candidates", "matches", "results", "items"]:
        assert key in background
    assert "parseMaimaiProfileUrl" in background
    assert "normalizeImportContacts" in background
    assert '{ type: "importDetailContacts", contacts: parsed }' in popup


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
    assert "chrome.action.openPopup" in background
    assert "chrome.tabs.create" in background


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


def test_background_reset_detail_batch_clears_persisted_state():
    background = read_extension_file("background.js")
    reset_block = background.split('if (msg.type === "resetDetailBatch")', 1)[1].split('if (msg.type === "startDetailBatch")', 1)[0]

    assert "contacts: []" in reset_block
    assert "detailBatchState: null" in reset_block
    assert "detailBatchRunToken: __detailBatchRunToken" in reset_block
    assert "state: resetState" in reset_block


def test_popup_detail_tab_has_reset_and_realtime_logs():
    popup_html = read_extension_file("popup.html")
    popup_js = read_extension_file("popup.js")

    assert "btn-reset-detail-batch" in popup_html
    assert "detail-log-list" in popup_html
    assert "resetDetailBatch" in popup_js
    assert "renderDetailBatchLogs" in popup_js
    assert "getScraperSummary" in popup_js
    assert "summary.detail.totalJobs || summary.detail.jobs || 0" in popup_js
    assert "summary.totalDetails" in popup_js
    assert "summary.detail.state.status" in popup_js
    assert "input.total_jobs" in popup_js
    assert "function isDetailBadgeActive()" in popup_js
    assert "function setCaptureBadge(text)" in popup_js


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
    content = read_extension_file("content.js")

    assert "batch_pause_until" in popup
    assert "批间休息中" in popup
    assert "batch_pause_until" in content
    assert "批间休息中" in content


def test_search_template_tracks_headers_and_nested_pagination():
    inject = read_extension_file("inject.js")
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
    assert "请求头" in popup
    assert "headerList.join" in popup


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

    assert "detail_batch_job_succeeded" in detail_batch
    assert "detail_batch_job_failed" in detail_batch
    assert "详情抓取成功" in background
    assert "详情抓取失败" in background
    assert "endpointStatusText" in background
    assert "logs.slice(-50).reverse()" in popup
    assert "执行日志" in popup_html
    detail_message_block = popup.split('if (msg.type && msg.type.indexOf("detail_batch_") === 0)', 1)[1].split("});", 1)[0]
    assert "refreshDetailBatchStatus()" in detail_message_block
    assert "async function emit" in detail_batch
    assert "return onEvent(event)" in detail_batch
    assert "await emit(onEvent" in detail_batch
