import json

import pytest

from scripts.liepin_api_contract import (
    CONDITION_BY_JOB_URL,
    SEARCH_RESUMES_URL,
    build_condition_request_body,
    build_search_request_body,
    classify_api_result,
    decode_form_body,
    merge_condition_data,
)


def test_condition_request_body_is_form_encoded_job_id():
    body = build_condition_request_body(75703601)

    assert body == "jobId=75703601"
    assert CONDITION_BY_JOB_URL.endswith(
        "/api/com.liepin.searchfront4r.h.get-search-condition-by-job"
    )


def test_search_request_body_round_trips_json_form_fields():
    params = {
        "jobId": 75703601,
        "curPage": 0,
        "resumetype": "0",
        "sortType": "0",
        "wantDqs": "010",
    }
    log_form = {
        "ckId": "ck-1",
        "skId": "",
        "fkId": "",
        "searchScene": "job",
    }

    body = build_search_request_body(params, log_form)
    decoded = decode_form_body(body)

    assert SEARCH_RESUMES_URL.endswith(
        "/api/com.liepin.searchfront4r.h.search-resumes"
    )
    assert decoded["searchParamsInputVo"] == params
    assert decoded["logForm"] == log_form


def test_merge_condition_data_applies_default_shape_and_overrides():
    condition_data = {
        "workYearsLow": 3,
        "workYearsHigh": 99,
        "eduLevels": ["040", "030", "010"],
        "eduLevelTz": True,
        "wantDqsOut": [{"dqCode": "010", "dqName": "北京"}],
        "searchType": "1",
        "sortType": "0",
    }

    params = merge_condition_data(
        condition_data,
        overrides={"keyword": "运营", "sortType": "43"},
        job_id=75703601,
        cur_page=2,
    )

    assert params["jobId"] == 75703601
    assert params["curPage"] == 2
    assert params["wantDqs"] == "010"
    assert params["workYearsLow"] == 3
    assert params["workYearsHigh"] == 99
    assert params["eduLevels"] == ["040", "030", "010"]
    assert params["keyword"] == "运营"
    assert params["sortType"] == "43"
    assert params["resumetype"] == "0"
    assert params["anyKeyword"] == "0"


@pytest.mark.parametrize(
    ("status", "content_type", "raw_text", "parsed", "reason"),
    [
        (403, "application/json", '{"flag":1}', {"flag": 1}, "http_403"),
        (429, "application/json", '{"flag":1}', {"flag": 1}, "http_429"),
        (432, "application/json", '{"flag":1}', {"flag": 1}, "http_432"),
        (200, "text/html", "<html></html>", None, "html_response"),
        (200, "application/json", "{bad json", None, "non_json_response"),
        (200, "application/json", '{"flag":0}', {"flag": 0}, "flag_not_1"),
    ],
)
def test_classify_api_result_stop_reasons(status, content_type, raw_text, parsed, reason):
    result = classify_api_result(
        http_status=status,
        content_type=content_type,
        raw_text=raw_text,
        parsed=parsed,
    )

    assert result["ok"] is False
    assert result["reason"] == reason
    assert result["http_status"] == status


def test_classify_api_result_accepts_flag_one_json():
    result = classify_api_result(
        http_status=200,
        content_type="application/json;charset=utf-8",
        raw_text=json.dumps({"flag": 1, "data": {}}),
        parsed={"flag": 1, "data": {}},
    )

    assert result == {"ok": True, "reason": None, "http_status": 200}
