"""猎聘搜索 API P0 合同辅助函数。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any
from urllib.parse import parse_qsl, urlencode


API_HOST = "https://api-h.liepin.com"
CONDITION_BY_JOB_PATH = "/api/com.liepin.searchfront4r.h.get-search-condition-by-job"
SEARCH_RESUMES_PATH = "/api/com.liepin.searchfront4r.h.search-resumes"
CONDITION_BY_JOB_URL = API_HOST + CONDITION_BY_JOB_PATH
SEARCH_RESUMES_URL = API_HOST + SEARCH_RESUMES_PATH


DEFAULT_SEARCH_PARAMS: dict[str, Any] = {
    "nowDqs": "",
    "wantDqs": "",
    "onlyLatestWorkExp": "",
    "workYearsLow": "",
    "workYearsHigh": "",
    "graduate": False,
    "eduLevels": [],
    "eduLevelTz": False,
    "studyAbroad": False,
    "industrys": "",
    "nowJobTitles": "",
    "wantIndustry": "",
    "wantJobTitles": "",
    "userHope": "",
    "modifytimeType": "",
    "workAbroad": False,
    "managerial": False,
    "languageSkills": [],
    "languageContent": "",
    "wantSalaryLow": "",
    "wantSalaryHigh": "",
    "nowSalaryLow": "",
    "nowSalaryHigh": "",
    "sex": "",
    "resLanguage": "",
    "ageLow": "",
    "ageHigh": "",
    "filterViewed": False,
    "filterChat": False,
    "filterDownload": False,
    "resumetype": "0",
    "sortType": "0",
    "skId": "",
    "fkId": "",
    "searchType": "1",
    "curPage": 0,
    "pageSize": "",
    "keyword": "",
    "anyKeyword": "0",
    "jobName": "",
    "jobPeriod": "0",
    "compName": "",
    "compPeriod": "0",
    "school": "",
    "major": "",
    "version": "",
    "schoolKindList": [],
    "eduLevelTzCode": "",
    "activeStatus": "",
    "pushId": "",
    "csId": "",
    "jobStability": "",
}


DEFAULT_LOG_FORM: dict[str, Any] = {
    "ckId": "",
    "skId": "",
    "fkId": "",
    "searchScene": "job",
}


def build_condition_request_body(job_id: int | str) -> str:
    return urlencode({"jobId": str(job_id)})


def _dq_codes(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    codes: list[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("dqCode") not in (None, ""):
            codes.append(str(item["dqCode"]))
    return ",".join(codes)


def merge_condition_data(
    condition_data: dict[str, Any] | None,
    overrides: dict[str, Any] | None = None,
    *,
    job_id: int | str,
    cur_page: int = 0,
) -> dict[str, Any]:
    params = deepcopy(DEFAULT_SEARCH_PARAMS)
    data = condition_data or {}
    params["jobId"] = int(job_id) if str(job_id).isdigit() else job_id
    params["curPage"] = int(cur_page)

    for key in (
        "workYearsLow",
        "workYearsHigh",
        "eduLevels",
        "eduLevelTz",
        "languageSkills",
        "searchType",
        "sortType",
        "nowDqs",
    ):
        if key in data:
            params[key] = data[key]

    want_dqs = _dq_codes(data.get("wantDqsOut"))
    if want_dqs:
        params["wantDqs"] = want_dqs

    for key, value in (overrides or {}).items():
        params[key] = value

    return params


def build_search_request_body(
    search_params: dict[str, Any],
    log_form: dict[str, Any] | None = None,
) -> str:
    payload = {
        "searchParamsInputVo": json.dumps(search_params, ensure_ascii=False, separators=(",", ":")),
        "logForm": json.dumps(log_form or DEFAULT_LOG_FORM, ensure_ascii=False, separators=(",", ":")),
    }
    return urlencode(payload)


def decode_form_body(body: str) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in parse_qsl(body, keep_blank_values=True):
        if key in {"searchParamsInputVo", "logForm"}:
            decoded[key] = json.loads(value)
        else:
            decoded[key] = value
    return decoded


def classify_api_result(
    *,
    http_status: int | None,
    content_type: str | None,
    raw_text: str | None,
    parsed: Any,
) -> dict[str, Any]:
    if http_status in {403, 429, 432}:
        return {"ok": False, "reason": f"http_{http_status}", "http_status": http_status}

    normalized_type = (content_type or "").lower()
    stripped = (raw_text or "").lstrip()
    if "html" in normalized_type or stripped.startswith("<"):
        return {"ok": False, "reason": "html_response", "http_status": http_status}

    if parsed is None:
        return {"ok": False, "reason": "non_json_response", "http_status": http_status}

    if not isinstance(parsed, dict):
        return {"ok": False, "reason": "template_drift", "http_status": http_status}

    if parsed.get("flag") != 1:
        return {"ok": False, "reason": "flag_not_1", "http_status": http_status}

    return {"ok": True, "reason": None, "http_status": http_status}
