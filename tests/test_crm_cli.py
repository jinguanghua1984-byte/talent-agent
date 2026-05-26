import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts import crm_cli


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _metadata() -> dict:
    return {
        "html": None,
        "list": [
            {
                "entry_type": "field",
                "name": "type",
                "type": "radio",
                "meta_class": {
                    "type_data": [
                        {"code": "candidate", "__name__": "候选人"},
                        {"code": "coldcall", "__name__": "Cold Call"},
                    ]
                },
            },
            {
                "entry_type": "field",
                "name": "gender",
                "type": "radio",
                "meta_class": {
                    "type_data": [
                        {"code": "true", "__name__": "男"},
                        {"code": "false", "__name__": "女"},
                    ]
                },
            },
            {
                "entry_type": "field",
                "name": "_ext1",
                "type": "dropdown",
                "meta_class": {
                    "type_data": [
                        {"code": "未婚", "__name__": "未婚"},
                        {"code": "已婚", "__name__": "已婚"},
                    ]
                },
            },
            {"entry_type": "field", "name": "owner", "type": "foreignkey"},
            {"entry_type": "field", "name": "candidateexperience_set", "type": "reverse_foreignkey"},
            {"entry_type": "field", "name": "candidateeducation_set", "type": "reverse_foreignkey"},
        ],
    }


def _candidate() -> dict:
    return {
        "englishName": "Alice Test",
        "email": "person@placeholder.invalid",
        "mobile": "00000000000",
        "gender": True,
        "_ext1": "未婚",
        "locations": "102",
        "industrys": "4",
        "functions": "1267",
        "channel": "400034",
        "owner": "300",
        "source": "gllue",
        "type": "coldcall",
        "record_type": "coldcall",
        "candidateexperience_set": [
            {
                "title": "AI infra 工程师",
                "client": {"id": 46033, "name": "示例公司"},
                "start": "2020-01",
                "end": None,
                "is_current": 1,
                "lang": "default",
            }
        ],
        "candidateeducation_set": [],
    }


def test_metadata_candidate_fetches_detail_with_runtime_cookie_and_writes_cache(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[dict] = []

    def fake_request_json(method, url, headers, data=None):
        calls.append({"method": method, "url": url, "headers": headers, "data": data})
        return _metadata()

    output = tmp_path / "candidate-fields.json"
    monkeypatch.setenv("CRM_COOKIE", "session=secret")
    monkeypatch.setattr(crm_cli, "request_json", fake_request_json)

    exit_code = crm_cli.main(
        [
            "metadata",
            "candidate",
            "--suffix",
            "coldcall",
            "--output",
            str(output),
            "--base-url",
            "http://crm.local",
            "--user-id",
            "300",
        ]
    )

    assert exit_code == 0
    assert len(calls) == 1
    parsed = urlparse(calls[0]["url"])
    query = parse_qs(parsed.query)
    assert calls[0]["method"] == "GET"
    assert parsed.path == "/rest/custom_field/candidate/detail"
    assert query["suffix"] == ["coldcall"]
    assert query["_v_user"] == ["300"]
    assert calls[0]["headers"]["Cookie"] == "session=secret"
    cached = json.loads(output.read_text(encoding="utf-8-sig"))
    assert cached["list"][0]["name"] == "type"


def test_metadata_candidate_rejects_login_required_response(tmp_path: Path, monkeypatch, capsys) -> None:
    def fake_request_json(method, url, headers, data=None):
        return {"status": False, "message": "login required"}

    output = tmp_path / "candidate-fields.json"
    monkeypatch.setenv("CRM_COOKIE", "session=expired")
    monkeypatch.setattr(crm_cli, "request_json", fake_request_json)

    exit_code = crm_cli.main(
        [
            "metadata",
            "candidate",
            "--suffix",
            "coldcall",
            "--output",
            str(output),
            "--base-url",
            "http://crm.local",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "login required" in captured.err
    assert not output.exists()


def test_auth_check_reports_login_required_without_cookie(monkeypatch, capsys) -> None:
    calls: list[dict] = []

    def fake_request_json(method, url, headers, data=None):
        calls.append({"method": method, "url": url, "headers": headers, "data": data})
        return {"status": False, "message": "login required"}

    monkeypatch.delenv("CRM_COOKIE", raising=False)
    monkeypatch.setattr(crm_cli, "request_json", fake_request_json)

    exit_code = crm_cli.main(
        [
            "auth",
            "check",
            "--no-cookie",
            "--base-url",
            "http://crm.local",
            "--suffix",
            "coldcall",
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 1
    assert calls[0]["headers"].get("Cookie") is None
    assert result["authenticated"] is False
    assert result["message"] == "login required"
    assert "Traceback" not in captured.err


def test_candidate_validate_accepts_metadata_enum_codes(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    metadata_path = tmp_path / "metadata.json"
    _write_json(candidate_path, _candidate())
    _write_json(metadata_path, _metadata())

    exit_code = crm_cli.main(
        [
            "candidate",
            "validate",
            "--input",
            str(candidate_path),
            "--metadata",
            str(metadata_path),
        ]
    )

    assert exit_code == 0


def test_candidate_validate_rejects_invalid_enum_from_metadata(tmp_path: Path, capsys) -> None:
    candidate = _candidate()
    candidate["type"] = "bad-type"
    candidate_path = tmp_path / "candidate.json"
    metadata_path = tmp_path / "metadata.json"
    _write_json(candidate_path, candidate)
    _write_json(metadata_path, _metadata())

    exit_code = crm_cli.main(
        [
            "candidate",
            "validate",
            "--input",
            str(candidate_path),
            "--metadata",
            str(metadata_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "invalid enum value for type" in captured.err
    assert "Traceback" not in captured.err


def test_candidate_validate_enforces_coldcall_form_required_fields(
    tmp_path: Path, capsys
) -> None:
    candidate = _candidate()
    candidate.update(
        {
            "englishName": "",
            "chineseName": "",
            "mobile": "",
            "mobile1": "",
            "mobile2": "",
            "gender": None,
            "locations": "",
            "industrys": "",
            "functions": "",
            "channel": "",
            "candidateexperience_set": [],
        }
    )
    candidate_path = tmp_path / "candidate.json"
    _write_json(candidate_path, candidate)

    exit_code = crm_cli.main(["candidate", "validate", "--input", str(candidate_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "required one of mobile/mobile1/mobile2" in captured.err
    assert "required one of englishName/chineseName" in captured.err
    assert "required field gender" in captured.err
    assert "required field locations" in captured.err
    assert "required field industrys" in captured.err
    assert "required field functions" in captured.err
    assert "required field channel" in captured.err
    assert "candidateexperience_set must contain at least one work experience" in captured.err


def test_candidate_validate_allows_coldcall_phone_and_name_alternatives(
    tmp_path: Path,
) -> None:
    candidate = _candidate()
    candidate["englishName"] = ""
    candidate["chineseName"] = "测试候选人"
    candidate["mobile"] = ""
    candidate["mobile1"] = "00000000000"
    candidate_path = tmp_path / "candidate.json"
    _write_json(candidate_path, candidate)

    exit_code = crm_cli.main(["candidate", "validate", "--input", str(candidate_path)])

    assert exit_code == 0


def test_candidate_validate_rejects_coldcall_experience_missing_company_or_title(
    tmp_path: Path, capsys
) -> None:
    candidate = _candidate()
    candidate["candidateexperience_set"] = [
        {"title": "", "client": {"id": "", "name": ""}},
    ]
    candidate_path = tmp_path / "candidate.json"
    _write_json(candidate_path, candidate)

    exit_code = crm_cli.main(["candidate", "validate", "--input", str(candidate_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "candidateexperience_set[0].client must include company" in captured.err
    assert "candidateexperience_set[0].title must be a non-empty string" in captured.err


def test_candidate_validate_strict_fields_rejects_unknown_top_level_key(
    tmp_path: Path, capsys
) -> None:
    candidate = _candidate()
    candidate["unknown_field"] = "unexpected"
    candidate_path = tmp_path / "candidate.json"
    metadata_path = tmp_path / "metadata.json"
    _write_json(candidate_path, candidate)
    _write_json(metadata_path, _metadata())

    exit_code = crm_cli.main(
        [
            "candidate",
            "validate",
            "--input",
            str(candidate_path),
            "--metadata",
            str(metadata_path),
            "--strict-fields",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "unknown top-level fields" in captured.err
    assert "unknown_field" in captured.err


def test_candidate_add_dry_run_prints_redacted_summary_without_network(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    def fail_request_json(*args, **kwargs):
        raise AssertionError("dry-run must not call network")

    candidate_path = tmp_path / "candidate.json"
    _write_json(candidate_path, _candidate())
    monkeypatch.setattr(crm_cli, "request_json", fail_request_json)

    exit_code = crm_cli.main(
        [
            "candidate",
            "add",
            "--input",
            str(candidate_path),
            "--dry-run",
            "--base-url",
            "http://crm.local",
            "--user-id",
            "300",
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert "dry-run" in captured.out
    assert "http://crm.local/rest/candidate/add" in captured.out
    assert "person@placeholder.invalid" not in captured.out
    assert "00000000000" not in captured.out
    assert "email" in captured.out
    assert "mobile" in captured.out
    assert result["headers"] == {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "http://crm.local",
        "Referer": "http://crm.local/crm",
        "X-Requested-With": "XMLHttpRequest",
        "x-request-id": "<milliseconds timestamp>",
        "Cookie": "[CRM_COOKIE]",
    }
    assert result["form"] == {"data": "[REDACTED_PAYLOAD_JSON]"}
    assert result["curl_template_powershell"].startswith("curl 'http://crm.local/rest/candidate/add")
    assert "$env:CRM_COOKIE" in result["curl_template_powershell"]


def test_candidate_add_dry_run_can_write_redacted_request_summary(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    def fail_request_json(*args, **kwargs):
        raise AssertionError("dry-run must not call network")

    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "request-summary.json"
    _write_json(candidate_path, _candidate())
    monkeypatch.setattr(crm_cli, "request_json", fail_request_json)

    exit_code = crm_cli.main(
        [
            "candidate",
            "add",
            "--input",
            str(candidate_path),
            "--dry-run",
            "--base-url",
            "http://crm.local",
            "--user-id",
            "300",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert exit_code == 0
    assert "request summary written" in captured.out
    assert result["mode"] == "dry-run"
    assert result["form"]["data"] == "[REDACTED_PAYLOAD_JSON]"
    assert "person@placeholder.invalid" not in output_path.read_text(encoding="utf-8-sig")
    assert "00000000000" not in output_path.read_text(encoding="utf-8-sig")


def test_candidate_add_without_dry_run_is_blocked(tmp_path: Path, capsys) -> None:
    candidate_path = tmp_path / "candidate.json"
    _write_json(candidate_path, _candidate())

    exit_code = crm_cli.main(["candidate", "add", "--input", str(candidate_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "真实写入暂未启用" in captured.err
    assert "Traceback" not in captured.err


def test_candidate_add_confirm_real_write_posts_payload_and_redacts_summary(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    calls: list[dict] = []

    def fake_request_json(method, url, headers, data=None):
        calls.append({"method": method, "url": url, "headers": headers, "data": data})
        return {
            "status": True,
            "current_message": {
                "candidateexperience": [
                    {"status": True, "current_message": {}, "data": 2671303},
                ],
                "candidateeducation": [],
            },
            "data": 1449495,
        }

    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "live-summary.json"
    _write_json(candidate_path, _candidate())
    monkeypatch.setenv("CRM_COOKIE", "session=secret")
    monkeypatch.setattr(crm_cli, "request_json", fake_request_json)

    exit_code = crm_cli.main(
        [
            "candidate",
            "add",
            "--input",
            str(candidate_path),
            "--confirm-real-write",
            "--base-url",
            "http://crm.local",
            "--user-id",
            "300",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert exit_code == 0
    assert "live request summary written" in captured.out
    assert calls[0]["method"] == "POST"
    parsed = urlparse(calls[0]["url"])
    query = parse_qs(parsed.query)
    assert parsed.path == "/rest/candidate/add"
    assert query["_v_user"] == ["300"]
    assert calls[0]["headers"]["Cookie"] == "session=secret"
    submitted = json.loads(calls[0]["data"]["data"])
    assert submitted["email"] == "person@placeholder.invalid"
    assert submitted["mobile"] == "00000000000"
    assert result["mode"] == "live"
    assert result["response"]["status"] is True
    assert result["response"]["candidate_id"] == 1449495
    assert result["response"]["nested_counts"] == {
        "candidateexperience": 1,
        "candidateeducation": 0,
    }
    assert result["form"]["data"] == "[REDACTED_PAYLOAD_JSON]"
    assert "person@placeholder.invalid" not in output_path.read_text(encoding="utf-8-sig")
    assert "00000000000" not in output_path.read_text(encoding="utf-8-sig")


def test_candidate_duplicate_check_uses_email_autocomplete_and_redacts_query(
    monkeypatch, capsys
) -> None:
    calls: list[dict] = []

    def fake_request_json(method, url, headers, data=None):
        calls.append({"method": method, "url": url, "headers": headers, "data": data})
        return [{"id": 123, "email": "person@placeholder.invalid", "category": "custom_user"}]

    monkeypatch.setenv("CRM_COOKIE", "session=secret")
    monkeypatch.setattr(crm_cli, "request_json", fake_request_json)

    exit_code = crm_cli.main(
        [
            "candidate",
            "duplicate-check",
            "--email",
            "person@placeholder.invalid",
            "--type",
            "coldcall",
            "--base-url",
            "http://crm.local",
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 2
    assert calls[0]["method"] == "GET"
    parsed = urlparse(calls[0]["url"])
    query = parse_qs(parsed.query)
    assert parsed.path == "/rest/candidate/email_autocomplete"
    assert query["email"] == ["person@placeholder.invalid"]
    assert query["type"] == ["coldcall"]
    assert calls[0]["headers"]["Cookie"] == "session=secret"
    assert result["has_matches"] is True
    assert result["match_count"] == 1
    assert result["query"]["email"] == "[REDACTED]"
    assert "person@placeholder.invalid" not in captured.out


def test_candidate_duplicate_check_returns_zero_when_no_email_matches(monkeypatch, capsys) -> None:
    def fake_request_json(method, url, headers, data=None):
        return []

    monkeypatch.setenv("CRM_COOKIE", "session=secret")
    monkeypatch.setattr(crm_cli, "request_json", fake_request_json)

    exit_code = crm_cli.main(
        [
            "candidate",
            "duplicate-check",
            "--email",
            "new@example.com",
            "--base-url",
            "http://crm.local",
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result["has_matches"] is False
    assert result["match_count"] == 0
    assert "new@example.com" not in captured.out


def test_lookup_tree_flattens_tree_and_filters_by_query(monkeypatch, capsys) -> None:
    calls: list[dict] = []

    def fake_request_json(method, url, headers, data=None):
        calls.append({"method": method, "url": url, "headers": headers, "data": data})
        return [
            {
                "id": 100,
                "label": "中国",
                "children": [
                    {"id": 102, "label": "上海", "children": []},
                    {"id": 125, "label": "北京", "children": []},
                ],
            }
        ]

    monkeypatch.setenv("CRM_COOKIE", "session=secret")
    monkeypatch.setattr(crm_cli, "request_json", fake_request_json)

    exit_code = crm_cli.main(
        [
            "lookup",
            "tree",
            "--kind",
            "city",
            "--query",
            "上海",
            "--base-url",
            "http://crm.local",
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    parsed = urlparse(calls[0]["url"])
    assert exit_code == 0
    assert calls[0]["method"] == "GET"
    assert parsed.path == "/rest/city/list"
    assert calls[0]["headers"]["Cookie"] == "session=secret"
    assert result["kind"] == "city"
    assert result["count"] == 1
    assert result["matches"][0]["id"] == 102
    assert result["matches"][0]["label"] == "上海"
    assert result["matches"][0]["path"] == ["中国", "上海"]


def test_lookup_company_uses_autocomplete_endpoint(monkeypatch, capsys) -> None:
    calls: list[dict] = []

    def fake_request_json(method, url, headers, data=None):
        calls.append({"method": method, "url": url, "headers": headers, "data": data})
        return [
            {
                "id": 46033,
                "name": "示例公司",
                "people_count": 1000,
                "city": "北京",
            }
        ]

    monkeypatch.setenv("CRM_COOKIE", "session=secret")
    monkeypatch.setattr(crm_cli, "request_json", fake_request_json)

    exit_code = crm_cli.main(
        [
            "lookup",
            "company",
            "--name",
            "示例",
            "--base-url",
            "http://crm.local",
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    parsed = urlparse(calls[0]["url"])
    query = parse_qs(parsed.query)
    assert exit_code == 0
    assert parsed.path == "/rest/data/autocomplete"
    assert query["type"] == ["client"]
    assert query["name"] == ["示例"]
    assert query["sort_func"] == ["company_suggestion"]
    assert result["count"] == 1
    assert result["matches"][0]["id"] == 46033
    assert result["matches"][0]["name"] == "示例公司"


def test_lookup_user_filters_userlist_and_redacts_email(monkeypatch, capsys) -> None:
    calls: list[dict] = []

    def fake_request_json(method, url, headers, data=None):
        calls.append({"method": method, "url": url, "headers": headers, "data": data})
        return {
            "count": 2,
            "list": [
                {
                    "id": 300,
                    "name": "顾问A",
                    "__name__": "顾问A",
                    "email": "consultant-email-token",
                    "status": "active",
                },
                {
                    "id": 301,
                    "name": "其他用户",
                    "__name__": "其他用户",
                    "email": "other-email-token",
                    "status": "active",
                },
            ],
        }

    monkeypatch.setenv("CRM_COOKIE", "session=secret")
    monkeypatch.setattr(crm_cli, "request_json", fake_request_json)

    exit_code = crm_cli.main(
        [
            "lookup",
            "user",
            "--query",
            "顾问",
            "--base-url",
            "http://crm.local",
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    parsed = urlparse(calls[0]["url"])
    assert exit_code == 0
    assert parsed.path == "/rest/data/userlist"
    assert result["kind"] == "user"
    assert result["count"] == 1
    assert result["matches"][0]["id"] == 300
    assert result["matches"][0]["name"] == "顾问A"
    assert result["matches"][0]["email"] == "[REDACTED]"
    assert "consultant-email-token" not in captured.out
    assert "other-email-token" not in captured.out


def test_lookup_department_uses_client_department_endpoint(monkeypatch, capsys) -> None:
    calls: list[dict] = []

    def fake_request_json(method, url, headers, data=None):
        calls.append({"method": method, "url": url, "headers": headers, "data": data})
        return [
            {
                "id": 10,
                "name": "研发",
                "children": [
                    {"id": 11, "name": "AI 平台", "children": []},
                    {"id": 12, "name": "商业化", "children": []},
                ],
            }
        ]

    monkeypatch.setenv("CRM_COOKIE", "session=secret")
    monkeypatch.setattr(crm_cli, "request_json", fake_request_json)

    exit_code = crm_cli.main(
        [
            "lookup",
            "department",
            "--client-id",
            "46033",
            "--query",
            "AI",
            "--base-url",
            "http://crm.local",
        ]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    parsed = urlparse(calls[0]["url"])
    query = parse_qs(parsed.query)
    assert exit_code == 0
    assert parsed.path == "/rest/clientdepartment/listdepartment"
    assert query["client"] == ["46033"]
    assert result["kind"] == "department"
    assert result["client_id"] == "46033"
    assert result["count"] == 1
    assert result["matches"][0]["id"] == 11
    assert result["matches"][0]["label"] == "AI 平台"
    assert result["matches"][0]["path"] == ["研发", "AI 平台"]


def _lookup_cache() -> dict:
    return {
        "city": [
            {"id": 102, "label": "上海"},
            {"id": 125, "label": "北京"},
        ],
        "industry": [
            {"id": 4, "label": "互联网"},
        ],
        "function": [
            {"id": 1267, "label": "算法"},
            {"id": 1286, "label": "后端"},
        ],
        "channel": [
            {"id": 400034, "label": "Gllue"},
        ],
        "folder": [
            {"id": 13009, "label": "人才库"},
        ],
        "user": [
            {"id": 300, "name": "顾问A"},
        ],
        "company": [
            {"id": 46033, "name": "示例公司"},
        ],
        "department": [
            {"id": 306319, "label": "AI 平台", "client_id": 46033},
        ],
    }


def test_candidate_compose_resolves_human_readable_draft_to_payload(tmp_path: Path) -> None:
    draft_path = tmp_path / "draft.json"
    cache_path = tmp_path / "lookup-cache.json"
    output_path = tmp_path / "candidate.json"
    lookup_cache = _lookup_cache()
    _write_json(cache_path, lookup_cache)
    _write_json(
        draft_path,
        {
            "englishName": "Alice Test",
            "chineseName": "测试候选人",
            "email": "person@placeholder.invalid",
            "mobile": "00000000000",
            "gender": "男",
            "birthDate": "1990-01-01",
            "currentLocation": "上海",
            "expectedLocations": ["上海", "北京"],
            "industries": ["互联网"],
            "functions": ["算法", "后端"],
            "channel": "Gllue",
            "owner": "顾问A",
            "folders": ["人才库"],
            "maritalStatus": "未婚",
            "type": "coldcall",
            "nickname": "Ace",
            "wechat": "wx-placeholder",
            "annualSalary": 5000000,
            "firstDegree": "n75722502808443490",
            "constellation": "n81682323688982850",
            "talentLevel": "n73407498137465810",
            "talentPool": "n51095470956125190",
            "experiences": [
                {
                    "company": "示例公司",
                    "department": "AI 平台",
                    "title": "AI infra 工程师",
                    "description": "负责 AI 基础设施。",
                    "level": "M2",
                    "current": True,
                    "start": "2020-01",
                }
            ],
            "educations": [
                {
                    "school": "示例大学",
                    "degree": "Master",
                    "major": "计算机",
                    "start": "2013-09",
                    "end": "2016-07",
                }
            ],
            "note": "候选人沟通记录。",
            "noteDate": "2026-05-26 10:35:00",
        },
    )

    exit_code = crm_cli.main(
        [
            "candidate",
            "compose",
            "--input",
            str(draft_path),
            "--lookup-cache",
            str(cache_path),
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert exit_code == 0
    assert payload["source"] == "gllue"
    assert payload["type"] == "coldcall"
    assert payload["record_type"] == "coldcall"
    assert payload["gender"] is True
    assert payload["_ext4"] == "1990-01-01"
    assert payload["locations"] == "102"
    assert payload["citys"] == "102,125"
    assert payload["industrys"] == "4"
    assert payload["functions"] == "1267,1286"
    assert payload["channel"] == "400034"
    assert payload["owner"] == "300"
    assert payload["folders"] == ["13009"]
    assert payload["gllueext113"] == "Ace"
    assert payload["gllueextWechat"] == "wx-placeholder"
    experience = payload["candidateexperience_set"][0]
    assert experience["department"] == "306319"
    assert experience["client"] == {
        "industrys": "",
        "citys": "",
        "id": 46033,
        "name": "示例公司",
    }
    assert experience["is_current"] == 1
    assert experience["end"] is None
    assert payload["candidateeducation_set"][0]["degree"] == "Master"
    assert payload["note_set"]["content_69"] == "候选人沟通记录。"
    assert payload["note_set"]["noteuser_set"] == [{"user": 300}]
    crm_cli.validate_candidate_payload(payload)


def test_candidate_compose_allows_optional_owner_source_and_folders(tmp_path: Path) -> None:
    draft_path = tmp_path / "draft.json"
    cache_path = tmp_path / "lookup-cache.json"
    output_path = tmp_path / "candidate.json"
    lookup_cache = _lookup_cache()
    lookup_cache.pop("user")
    lookup_cache.pop("folder")
    _write_json(cache_path, lookup_cache)
    _write_json(
        draft_path,
        {
            "chineseName": "测试候选人",
            "mobile1": "00000000000",
            "gender": "女",
            "currentLocation": "上海",
            "industries": ["互联网"],
            "functions": ["算法"],
            "channel": "Gllue",
            "type": "coldcall",
            "experiences": [
                {
                    "company": "示例公司",
                    "title": "AI infra 工程师",
                    "current": True,
                }
            ],
        },
    )

    exit_code = crm_cli.main(
        [
            "candidate",
            "compose",
            "--input",
            str(draft_path),
            "--lookup-cache",
            str(cache_path),
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert exit_code == 0
    assert payload["owner"] == ""
    assert payload["source"] == "gllue"
    assert payload["folders"] == []
    assert payload["gender"] is False
    assert payload["chineseName"] == "测试候选人"
    assert payload["mobile1"] == "00000000000"
    crm_cli.validate_candidate_payload(payload)


def test_candidate_compose_defaults_missing_coldcall_required_lookup_values(
    tmp_path: Path,
) -> None:
    draft_path = tmp_path / "draft.json"
    cache_path = tmp_path / "lookup-cache.json"
    output_path = tmp_path / "candidate.json"
    lookup_cache = _lookup_cache()
    lookup_cache["industry"] = [
        {"id": 999, "label": "AI 咨询"},
        {"id": 4, "label": "AI"},
    ]
    lookup_cache["function"] = [
        {"id": 1267, "label": "AI产品经理"},
        {"id": 1286, "label": "AI产品运营"},
    ]
    lookup_cache["channel"] = [
        {"id": 400034, "label": "脉脉-企业付费账号"},
    ]
    _write_json(cache_path, lookup_cache)
    _write_json(
        draft_path,
        {
            "chineseName": "测试候选人",
            "mobile": "00000000000",
            "currentLocation": "上海",
            "type": "coldcall",
            "experiences": [
                {
                    "company": "示例公司",
                    "title": "AI 产品负责人",
                }
            ],
        },
    )

    exit_code = crm_cli.main(
        [
            "candidate",
            "compose",
            "--input",
            str(draft_path),
            "--lookup-cache",
            str(cache_path),
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert exit_code == 0
    assert payload["gender"] is True
    assert payload["industrys"] == "4"
    assert payload["functions"] == "1267"
    assert payload["channel"] == "400034"
    crm_cli.validate_candidate_payload(payload)


def test_candidate_compose_reports_default_lookup_failure_for_required_field(
    tmp_path: Path, capsys
) -> None:
    draft_path = tmp_path / "draft.json"
    cache_path = tmp_path / "lookup-cache.json"
    output_path = tmp_path / "candidate.json"
    lookup_cache = _lookup_cache()
    lookup_cache["industry"] = [{"id": 4, "label": "互联网"}]
    lookup_cache["function"] = [{"id": 1267, "label": "AI产品"}]
    lookup_cache["channel"] = [{"id": 400034, "label": "脉脉-企业付费账号"}]
    _write_json(cache_path, lookup_cache)
    _write_json(
        draft_path,
        {
            "chineseName": "测试候选人",
            "mobile": "00000000000",
            "currentLocation": "上海",
            "type": "coldcall",
            "experiences": [
                {
                    "company": "示例公司",
                    "title": "AI 产品负责人",
                }
            ],
        },
    )

    exit_code = crm_cli.main(
        [
            "candidate",
            "compose",
            "--input",
            str(draft_path),
            "--lookup-cache",
            str(cache_path),
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "required field industrys default lookup failed" in captured.err
    assert "AI" in captured.err
    assert "请确认 CRM 中的准确选项名称" in captured.err
    assert not output_path.exists()


def test_candidate_compose_rejects_missing_lookup_value(tmp_path: Path, capsys) -> None:
    draft_path = tmp_path / "draft.json"
    cache_path = tmp_path / "lookup-cache.json"
    output_path = tmp_path / "candidate.json"
    lookup_cache = _lookup_cache()
    _write_json(cache_path, lookup_cache)
    _write_json(
        draft_path,
        {
            "englishName": "Alice Test",
            "owner": "顾问A",
            "type": "coldcall",
            "currentLocation": "深圳",
        },
    )

    exit_code = crm_cli.main(
        [
            "candidate",
            "compose",
            "--input",
            str(draft_path),
            "--lookup-cache",
            str(cache_path),
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "lookup value not found for city: 深圳" in captured.err
    assert not output_path.exists()
