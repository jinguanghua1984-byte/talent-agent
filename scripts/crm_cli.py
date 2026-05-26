"""CRM 新增人才 API 的最小辅助 CLI。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, parse, request


DEFAULT_BASE_URL = "http://101.200.132.164"
CRM_COOKIE_ENV = "CRM_COOKIE"
DEFAULT_COLDCALL_GENDER = "男"
DEFAULT_COLDCALL_INDUSTRIES = ["AI"]
DEFAULT_COLDCALL_FUNCTIONS = ["AI产品"]
DEFAULT_COLDCALL_CHANNELS = ["脉脉-企业版付费账号", "脉脉-企业付费账号"]

KNOWN_TOP_LEVEL_FIELDS = {
    "attachments",
    "avatar_id",
    "email",
    "email1",
    "email2",
    "mobile",
    "mobile1",
    "mobile2",
    "englishName",
    "chineseName",
    "gllueext113",
    "gllueextWechat",
    "gender",
    "_ext4",
    "locations",
    "citys",
    "industrys",
    "functions",
    "gllueextfirstdegree",
    "annualSalary",
    "channel",
    "owner",
    "shares",
    "_ext1",
    "folders",
    "source",
    "type",
    "gllueext112",
    "gllueext114",
    "gllueextNBC",
    "candidateexperience_set",
    "candidateproject_set",
    "candidateeducation_set",
    "note_set",
    "record_type",
}

REQUIRED_FIELDS = ("type", "record_type")
COLD_CALL_PHONE_FIELDS = ("mobile", "mobile1", "mobile2")
COLD_CALL_NAME_FIELDS = ("englishName", "chineseName")
NESTED_LIST_FIELDS = (
    "candidateexperience_set",
    "candidateproject_set",
    "candidateeducation_set",
)

TREE_ENDPOINTS = {
    "city": ("/rest/city/list", {}),
    "industry": ("/rest/industry/list", {}),
    "function": ("/rest/function/list", {}),
    "channel": ("/rest/channel/comtree/list", {}),
    "folder": ("/rest/folder/list", {"type": "candidate"}),
}


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json(path: str | Path, data: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _timestamp_ms() -> str:
    return str(int(time.time() * 1000))


def _headers(base_url: str, cookie: str | None = None, form: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "*/*",
        "Origin": base_url,
        "Referer": f"{base_url}/crm",
        "X-Requested-With": "XMLHttpRequest",
        "x-request-id": _timestamp_ms(),
    }
    if form:
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    if cookie:
        headers["Cookie"] = cookie
    return headers


def _url(base_url: str, path: str, params: dict[str, str | None]) -> str:
    clean_params = {key: value for key, value in params.items() if value not in {None, ""}}
    query = parse.urlencode(clean_params)
    url = f"{_normalize_base_url(base_url)}{path}"
    return f"{url}?{query}" if query else url


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    data: dict[str, str] | None = None,
) -> Any:
    body = None
    if data is not None:
        body = parse.urlencode(data).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method=method)
    with request.urlopen(req, timeout=30) as response:  # noqa: S310 - 内部系统手动授权调用。
        text = response.read().decode("utf-8-sig")
    return json.loads(text)


def _api_failure_message(data: Any) -> str | None:
    if not isinstance(data, dict) or data.get("status") is not False:
        return None
    message = data.get("message") or data.get("current_message") or "crm api returned status=false"
    if isinstance(message, (dict, list)):
        return json.dumps(message, ensure_ascii=False)
    return str(message)


def _load_object(path: str | Path, label: str) -> dict[str, Any]:
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{label} JSON must be an object")
    return data


def _metadata_fields(metadata: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not metadata:
        return {}
    fields = metadata.get("list")
    if not isinstance(fields, list):
        raise ValueError("metadata list must be a list")
    result: dict[str, dict[str, Any]] = {}
    for item in fields:
        if not isinstance(item, dict):
            continue
        if item.get("entry_type") != "field":
            continue
        name = item.get("name")
        if isinstance(name, str) and name:
            result[name] = item
    return result


def _runtime_cookie(cookie_env: str) -> str:
    cookie = os.environ.get(cookie_env)
    if not cookie:
        raise ValueError(f"missing runtime cookie env var: {cookie_env}")
    return cookie


def _node_label(node: dict[str, Any]) -> str:
    for key in ("label", "name", "__name__"):
        value = node.get(key)
        if value is not None:
            return str(value)
    return ""


def _flatten_tree(
    nodes: list[Any],
    path: list[str] | None = None,
) -> list[dict[str, Any]]:
    path = path or []
    result: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        label = _node_label(node)
        current_path = [*path, label] if label else [*path]
        result.append({
            "id": node.get("id"),
            "label": label,
            "path": current_path,
        })
        children = node.get("children")
        if isinstance(children, list):
            result.extend(_flatten_tree(children, current_path))
    return result


def _matches_query(items: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    needle = query.strip().lower()
    if not needle:
        return items[:limit]
    matched = [
        item
        for item in items
        if needle in str(item.get("label") or item.get("name") or "").lower()
        or any(needle in str(part).lower() for part in item.get("path") or [])
    ]
    return matched[:limit]


def _list_response_items(data: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        raise ValueError(f"{label} response must be an object")
    items = data.get("list")
    if not isinstance(items, list):
        raise ValueError(f"{label} response list must be a list")
    return [item for item in items if isinstance(item, dict)]


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _lookup_items(cache: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    items = cache.get(kind) or []
    if not isinstance(items, list):
        raise ValueError(f"lookup cache {kind} must be a list")
    return [item for item in items if isinstance(item, dict)]


def _lookup_texts(item: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key in ("label", "name", "__name__"):
        value = item.get(key)
        if value not in {None, ""}:
            texts.append(str(value))
    path = item.get("path")
    if isinstance(path, list):
        texts.extend(str(part) for part in path if part not in {None, ""})
    return texts


def _lookup_item(
    cache: dict[str, Any],
    kind: str,
    label: Any,
    client_id: Any | None = None,
) -> dict[str, Any]:
    needle = str(label).strip().lower()
    if not needle:
        raise ValueError(f"lookup value not found for {kind}: {label}")
    candidates = [
        item
        for item in _lookup_items(cache, kind)
        if client_id is None or str(item.get("client_id")) == str(client_id)
    ]
    for item in candidates:
        if any(
            text.strip().lower() == needle
            for text in _lookup_texts(item)
        ):
            return item
    for item in candidates:
        if any(needle in text.strip().lower() for text in _lookup_texts(item)):
            return item
    raise ValueError(f"lookup value not found for {kind}: {label}")


def _lookup_id(
    cache: dict[str, Any],
    kind: str,
    label: Any,
    client_id: Any | None = None,
) -> str:
    item = _lookup_item(cache, kind, label, client_id=client_id)
    if item.get("id") in {None, ""}:
        raise ValueError(f"lookup value not found for {kind}: {label}")
    return str(item["id"])


def _lookup_ids(cache: dict[str, Any], kind: str, labels: Any) -> list[str]:
    return [_lookup_id(cache, kind, label) for label in _as_list(labels)]


def _missing_draft_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not value
    return False


def _draft_value_or_default(value: Any, default: Any) -> tuple[Any, bool]:
    if _missing_draft_value(value):
        return default, True
    return value, False


def _lookup_required_ids(
    cache: dict[str, Any],
    kind: str,
    labels: Any,
    field: str,
    default_used: bool = False,
) -> list[str]:
    try:
        return _lookup_ids(cache, kind, labels)
    except ValueError as exc:
        if default_used:
            raise ValueError(
                f"required field {field} default lookup failed: {exc}; 请确认 CRM 中的准确选项名称"
            ) from exc
        raise


def _lookup_required_id(
    cache: dict[str, Any],
    kind: str,
    label: Any,
    field: str,
    default_used: bool = False,
) -> str:
    labels = _as_list(label)
    last_error: ValueError | None = None
    for item_label in labels:
        try:
            return _lookup_id(cache, kind, item_label)
        except ValueError as exc:
            last_error = exc
    if last_error is None:
        last_error = ValueError(f"lookup value not found for {kind}: {label}")
    if default_used:
        tried = ", ".join(str(item) for item in labels)
        detail = f"{last_error}; tried defaults: {tried}" if tried else str(last_error)
        raise ValueError(
            f"required field {field} default lookup failed: {detail}; 请确认 CRM 中的准确选项名称"
        ) from last_error
    raise last_error


def _optional_lookup_id(cache: dict[str, Any], kind: str, label: Any) -> str:
    if label in {None, ""}:
        return ""
    return _lookup_id(cache, kind, label)


def _draft_gender(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {None, ""}:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"true", "male", "\u7537"}:
        return True
    if normalized in {"false", "female", "\u5973"}:
        return False
    return None


def _compose_experience(item: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    company_label = item.get("company") or item.get("client")
    if not company_label:
        raise ValueError("experience company is required")
    company = _lookup_item(cache, "company", company_label)
    company_id = company.get("id")
    if company_id in {None, ""}:
        raise ValueError(f"lookup value not found for company: {company_label}")
    company_name = str(company.get("name") or company.get("label") or company_label)
    department = ""
    if item.get("department"):
        department = _lookup_id(cache, "department", item["department"], client_id=company_id)
    is_current = 1 if bool(item.get("current") or item.get("is_current")) else 0
    return {
        "department": department,
        "title": item.get("title") or "",
        "description": item.get("description") or "",
        "gllueextTitle": item.get("level") or item.get("gllueextTitle") or "",
        "is_current": is_current,
        "client": {
            "industrys": "",
            "citys": "",
            "id": company_id,
            "name": company_name,
        },
        "start": item.get("start") or "",
        "end": None if is_current else item.get("end"),
        "lang": item.get("lang") or "default",
    }


def _compose_education(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "school": item.get("school") or "",
        "degree": item.get("degree") or "",
        "major": item.get("major") or "",
        "is_current": 1 if bool(item.get("current") or item.get("is_current")) else 0,
        "start": item.get("start") or "",
        "end": item.get("end"),
        "lang": item.get("lang") or "default",
    }


def compose_candidate_payload(draft: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    owner_id = _optional_lookup_id(cache, "user", draft.get("owner"))
    record_type = str(draft.get("type") or "coldcall")
    use_coldcall_defaults = record_type == "coldcall"
    gender_value, _ = _draft_value_or_default(
        draft.get("gender"),
        DEFAULT_COLDCALL_GENDER if use_coldcall_defaults else None,
    )
    industry_labels, industry_defaulted = _draft_value_or_default(
        draft.get("industries"),
        DEFAULT_COLDCALL_INDUSTRIES if use_coldcall_defaults else [],
    )
    function_labels, function_defaulted = _draft_value_or_default(
        draft.get("functions"),
        DEFAULT_COLDCALL_FUNCTIONS if use_coldcall_defaults else [],
    )
    channel_label, channel_defaulted = _draft_value_or_default(
        draft.get("channel"),
        DEFAULT_COLDCALL_CHANNELS if use_coldcall_defaults else "",
    )
    payload: dict[str, Any] = {
        "attachments": "",
        "avatar_id": None,
        "email": draft.get("email") or "",
        "email1": draft.get("email1") or "",
        "email2": draft.get("email2") or "",
        "mobile": draft.get("mobile") or "",
        "mobile1": draft.get("mobile1") or "",
        "mobile2": draft.get("mobile2") or "",
        "englishName": draft.get("englishName") or "",
        "chineseName": draft.get("chineseName") or "",
        "gllueext113": draft.get("nickname") or draft.get("gllueext113") or "",
        "gllueextWechat": draft.get("wechat") or draft.get("gllueextWechat") or "",
        "gender": _draft_gender(gender_value),
        "_ext4": draft.get("birthDate") or draft.get("_ext4") or "",
        "locations": ",".join(_lookup_ids(cache, "city", draft.get("currentLocation"))),
        "citys": ",".join(_lookup_ids(cache, "city", draft.get("expectedLocations"))),
        "industrys": ",".join(_lookup_required_ids(
            cache, "industry", industry_labels, "industrys", default_used=industry_defaulted
        )),
        "functions": ",".join(_lookup_required_ids(
            cache, "function", function_labels, "functions", default_used=function_defaulted
        )),
        "gllueextfirstdegree": draft.get("firstDegree") or draft.get("gllueextfirstdegree") or "",
        "annualSalary": draft.get("annualSalary") or 0,
        "channel": _lookup_required_id(
            cache, "channel", channel_label, "channel", default_used=channel_defaulted
        ),
        "owner": owner_id,
        "shares": draft.get("shares") or [],
        "_ext1": draft.get("maritalStatus") or draft.get("_ext1") or "",
        "folders": _lookup_ids(cache, "folder", draft.get("folders")),
        "source": draft.get("source") or "gllue",
        "type": record_type,
        "gllueext112": draft.get("constellation") or draft.get("gllueext112") or "",
        "gllueext114": draft.get("talentLevel") or draft.get("gllueext114") or "",
        "gllueextNBC": draft.get("talentPool") or draft.get("gllueextNBC") or "",
        "candidateexperience_set": [
            _compose_experience(item, cache)
            for item in _as_list(draft.get("experiences"))
            if isinstance(item, dict)
        ],
        "candidateproject_set": draft.get("projects") or draft.get("candidateproject_set") or [],
        "candidateeducation_set": [
            _compose_education(item)
            for item in _as_list(draft.get("educations"))
            if isinstance(item, dict)
        ],
        "record_type": record_type,
    }
    if draft.get("note"):
        note_set: dict[str, Any] = {
            "status": "Active",
            "content_69": draft["note"],
            "category": draft.get("noteCategory") or "Candidate Call",
            "date": draft.get("noteDate") or "",
            "noteuser_set": [],
        }
        if owner_id:
            note_set["noteuser_set"] = [{"user": int(owner_id)}]
        payload["note_set"] = note_set
    return payload


def _enum_codes(field: dict[str, Any]) -> set[str]:
    meta = field.get("meta_class")
    if not isinstance(meta, dict):
        return set()
    type_data = meta.get("type_data")
    if not isinstance(type_data, list):
        return set()
    codes: set[str] = set()
    for item in type_data:
        if isinstance(item, dict) and item.get("code") is not None:
            codes.add(str(item["code"]))
    return codes


def _submitted_codes(value: Any, field_type: str) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, bool):
        return [str(value).lower()]
    if field_type == "checkboxdropdown" and isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item) for item in value if item not in {None, ""}]
    return [str(value)]


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return value != ""


def _has_any_present(payload: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(_is_present(payload.get(field)) for field in fields)


def _experience_has_company(item: dict[str, Any]) -> bool:
    client = item.get("client")
    if isinstance(client, dict):
        return _is_present(client.get("id")) or _is_present(client.get("name"))
    return _is_present(client) or _is_present(item.get("company"))


def _validate_coldcall_required(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if not _has_any_present(payload, COLD_CALL_PHONE_FIELDS):
        errors.append("required one of mobile/mobile1/mobile2")
    if not _has_any_present(payload, COLD_CALL_NAME_FIELDS):
        errors.append("required one of englishName/chineseName")
    for field in ("gender", "locations", "industrys", "functions", "channel"):
        if not _is_present(payload.get(field)):
            errors.append(f"required field {field}")

    experiences = payload.get("candidateexperience_set")
    if not isinstance(experiences, list) or not experiences:
        errors.append("candidateexperience_set must contain at least one work experience")
    elif experiences:
        for index, item in enumerate(experiences):
            if not isinstance(item, dict):
                errors.append(f"candidateexperience_set[{index}] must be an object")
                continue
            if not _experience_has_company(item):
                errors.append(f"candidateexperience_set[{index}].client must include company")
            if not _is_present(item.get("title")):
                errors.append(f"candidateexperience_set[{index}].title must be a non-empty string")

    if errors:
        raise ValueError("; ".join(errors))


def validate_candidate_payload(
    payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    strict_fields: bool = False,
) -> None:
    for field in REQUIRED_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"required field {field} must be a non-empty string")

    for field in NESTED_LIST_FIELDS:
        value = payload.get(field)
        if value is not None and not isinstance(value, list):
            raise ValueError(f"{field} must be a list")
    if "note_set" in payload and not isinstance(payload["note_set"], dict):
        raise ValueError("note_set must be an object")
    for field in ("shares", "folders"):
        value = payload.get(field)
        if value is not None and not isinstance(value, list):
            raise ValueError(f"{field} must be a list")

    fields = _metadata_fields(metadata)
    if strict_fields and fields:
        allowed = KNOWN_TOP_LEVEL_FIELDS | set(fields)
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValueError("unknown top-level fields: " + ", ".join(unknown))

    for name, field in fields.items():
        if name not in payload:
            continue
        field_type = str(field.get("type") or "")
        if field_type not in {"radio", "dropdown", "checkboxdropdown"}:
            continue
        codes = _enum_codes(field)
        if not codes:
            continue
        invalid = [code for code in _submitted_codes(payload[name], field_type) if code not in codes]
        if invalid:
            raise ValueError(
                f"invalid enum value for {name}: {', '.join(invalid)}; "
                f"allowed: {', '.join(sorted(codes))}"
            )

    if payload.get("type") != payload.get("record_type"):
        raise ValueError("type and record_type must match")

    if payload.get("type") == "coldcall":
        _validate_coldcall_required(payload)


def _curl_template_powershell(endpoint: str, base_url: str) -> str:
    return " ".join(
        [
            f"curl '{endpoint}'",
            "-H 'Accept: */*'",
            "-H 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8'",
            f"-H 'Origin: {base_url}'",
            f"-H 'Referer: {base_url}/crm'",
            "-H 'X-Requested-With: XMLHttpRequest'",
            "-H 'x-request-id: <milliseconds timestamp>'",
            '-H "Cookie: $env:CRM_COOKIE"',
            "--data-urlencode 'data@candidate.json'",
        ]
    )


def _redacted_summary(payload: dict[str, Any], endpoint: str, base_url: str) -> dict[str, Any]:
    contact_fields = ("email", "email1", "email2", "mobile", "mobile1", "mobile2")
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "mode": "dry-run",
        "method": "POST",
        "endpoint": endpoint,
        "content_type": "application/x-www-form-urlencoded; charset=UTF-8",
        "headers": {
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": base_url,
            "Referer": f"{base_url}/crm",
            "X-Requested-With": "XMLHttpRequest",
            "x-request-id": "<milliseconds timestamp>",
            "Cookie": "[CRM_COOKIE]",
        },
        "form_keys": ["data"],
        "form": {
            "data": "[REDACTED_PAYLOAD_JSON]",
        },
        "top_level_keys": sorted(payload),
        "contact_fields": {
            field: "[REDACTED]" for field in contact_fields if payload.get(field)
        },
        "nested_counts": {
            field: len(payload.get(field) or []) for field in NESTED_LIST_FIELDS
        },
        "payload_json_bytes": len(payload_json.encode("utf-8")),
        "payload_json_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "curl_template_powershell": _curl_template_powershell(endpoint, base_url),
    }


def _live_response_summary(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise ValueError("candidate add response must be an object")
    current_message = response.get("current_message") or {}
    if not isinstance(current_message, dict):
        current_message = {}
    nested_counts: dict[str, int] = {}
    nested_ids: dict[str, list[Any]] = {}
    for key in ("candidateexperience", "candidateeducation"):
        items = current_message.get(key) or []
        if isinstance(items, list):
            nested_counts[key] = len(items)
            nested_ids[key] = [
                item.get("data")
                for item in items
                if isinstance(item, dict) and item.get("data") not in {None, ""}
            ]
        else:
            nested_counts[key] = 0
            nested_ids[key] = []
    return {
        "status": response.get("status"),
        "candidate_id": response.get("data"),
        "nested_counts": nested_counts,
        "nested_ids": nested_ids,
    }


def cmd_metadata_candidate(args: argparse.Namespace) -> int:
    base_url = _normalize_base_url(args.base_url)
    cookie = _runtime_cookie(args.cookie_env)
    url = _url(
        base_url,
        "/rest/custom_field/candidate/detail",
        {
            "suffix": args.suffix,
            "_v_user": args.user_id,
            "_v": args.request_version,
        },
    )
    data = request_json("GET", url, _headers(base_url, cookie=cookie))
    failure = _api_failure_message(data)
    if failure:
        raise ValueError(failure)
    _write_json(args.output, data)
    fields = len(data.get("list") or []) if isinstance(data, dict) else 0
    print(f"元数据已写入：{args.output}，字段项 {fields}")
    return 0


def cmd_auth_check(args: argparse.Namespace) -> int:
    base_url = _normalize_base_url(args.base_url)
    cookie = None if args.no_cookie else os.environ.get(args.cookie_env)
    url = _url(
        base_url,
        "/rest/custom_field/candidate/detail",
        {
            "suffix": args.suffix,
            "_v_user": args.user_id,
            "_v": args.request_version,
        },
    )
    data = request_json("GET", url, _headers(base_url, cookie=cookie))
    failure = _api_failure_message(data)
    result = {
        "authenticated": failure is None,
        "endpoint": url,
        "message": failure or "ok",
    }
    if isinstance(data, dict) and "status" in data:
        result["status"] = data["status"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if failure is None else 1


def cmd_candidate_validate(args: argparse.Namespace) -> int:
    payload = _load_object(args.input, "candidate")
    metadata = _load_object(args.metadata, "metadata") if args.metadata else None
    validate_candidate_payload(payload, metadata=metadata, strict_fields=args.strict_fields)
    print(f"校验通过：{args.input}")
    return 0


def cmd_candidate_compose(args: argparse.Namespace) -> int:
    draft = _load_object(args.input, "candidate draft")
    cache = _load_object(args.lookup_cache, "lookup cache")
    payload = compose_candidate_payload(draft, cache)
    validate_candidate_payload(payload)
    _write_json(args.output, payload)
    print(f"candidate payload written: {args.output}")
    return 0


def cmd_candidate_add(args: argparse.Namespace) -> int:
    if not args.dry_run and not args.confirm_real_write:
        raise ValueError("真实写入暂未启用；如已完成 dry-run 和重复预检，请显式传入 --confirm-real-write")
    payload = _load_object(args.input, "candidate")
    metadata = _load_object(args.metadata, "metadata") if args.metadata else None
    validate_candidate_payload(payload, metadata=metadata, strict_fields=args.strict_fields)
    base_url = _normalize_base_url(args.base_url)
    endpoint = _url(
        base_url,
        "/rest/candidate/add",
        {
            "_v_user": args.user_id,
            "_v": args.request_version,
        },
    )
    summary = _redacted_summary(payload, endpoint, base_url)
    if args.dry_run:
        if args.output:
            _write_json(args.output, summary)
            print(f"request summary written: {args.output}")
        else:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    cookie = _runtime_cookie(args.cookie_env)
    response = request_json(
        "POST",
        endpoint,
        _headers(base_url, cookie=cookie, form=True),
        {"data": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
    )
    failure = _api_failure_message(response)
    if failure:
        raise ValueError(failure)
    summary["mode"] = "live"
    summary["response"] = _live_response_summary(response)
    if args.output:
        _write_json(args.output, summary)
        print(f"live request summary written: {args.output}")
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_candidate_duplicate_check(args: argparse.Namespace) -> int:
    base_url = _normalize_base_url(args.base_url)
    cookie = _runtime_cookie(args.cookie_env)
    url = _url(
        base_url,
        "/rest/candidate/email_autocomplete",
        {
            "email": args.email,
            "type": args.type,
        },
    )
    data = request_json("GET", url, _headers(base_url, cookie=cookie))
    failure = _api_failure_message(data)
    if failure:
        raise ValueError(failure)
    if not isinstance(data, list):
        raise ValueError("candidate email autocomplete response must be a list")
    result = {
        "has_matches": len(data) > 0,
        "match_count": len(data),
        "endpoint": "/rest/candidate/email_autocomplete",
        "query": {
            "email": "[REDACTED]",
            "type": args.type or "",
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if data else 0


def cmd_lookup_tree(args: argparse.Namespace) -> int:
    base_url = _normalize_base_url(args.base_url)
    cookie = _runtime_cookie(args.cookie_env)
    endpoint, params = TREE_ENDPOINTS[args.kind]
    data = request_json("GET", _url(base_url, endpoint, params), _headers(base_url, cookie=cookie))
    failure = _api_failure_message(data)
    if failure:
        raise ValueError(failure)
    if not isinstance(data, list):
        raise ValueError(f"{args.kind} lookup response must be a list")
    flattened = _flatten_tree(data)
    matches = _matches_query(flattened, args.query or "", args.limit)
    print(
        json.dumps(
            {
                "kind": args.kind,
                "query": args.query or "",
                "count": len(matches),
                "matches": matches,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_lookup_company(args: argparse.Namespace) -> int:
    base_url = _normalize_base_url(args.base_url)
    cookie = _runtime_cookie(args.cookie_env)
    data = request_json(
        "GET",
        _url(
            base_url,
            "/rest/data/autocomplete",
            {
                "demandKeys": '["people_count","city"]',
                "use_hide_generated": "1",
                "type": "client",
                "name": args.name,
                "sort_func": "company_suggestion",
            },
        ),
        _headers(base_url, cookie=cookie),
    )
    failure = _api_failure_message(data)
    if failure:
        raise ValueError(failure)
    if not isinstance(data, list):
        raise ValueError("company autocomplete response must be a list")
    matches = [
        {
            "id": item.get("id"),
            "name": item.get("name") or item.get("__name__") or "",
            "people_count": item.get("people_count"),
            "city": item.get("city"),
        }
        for item in data[: args.limit]
        if isinstance(item, dict)
    ]
    print(
        json.dumps(
            {
                "kind": "company",
                "query": args.name,
                "count": len(matches),
                "matches": matches,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_lookup_user(args: argparse.Namespace) -> int:
    base_url = _normalize_base_url(args.base_url)
    cookie = _runtime_cookie(args.cookie_env)
    data = request_json(
        "GET",
        _url(base_url, "/rest/data/userlist", {}),
        _headers(base_url, cookie=cookie),
    )
    failure = _api_failure_message(data)
    if failure:
        raise ValueError(failure)
    items = _list_response_items(data, "userlist")
    normalized = [
        {
            "id": item.get("id"),
            "name": item.get("name") or item.get("__name__") or "",
            "status": item.get("status"),
            "email": "[REDACTED]" if item.get("email") else "",
        }
        for item in items
    ]
    matches = _matches_query(normalized, args.query or "", args.limit)
    print(
        json.dumps(
            {
                "kind": "user",
                "query": args.query or "",
                "count": len(matches),
                "matches": matches,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_lookup_department(args: argparse.Namespace) -> int:
    base_url = _normalize_base_url(args.base_url)
    cookie = _runtime_cookie(args.cookie_env)
    data = request_json(
        "GET",
        _url(
            base_url,
            "/rest/clientdepartment/listdepartment",
            {"client": args.client_id},
        ),
        _headers(base_url, cookie=cookie),
    )
    failure = _api_failure_message(data)
    if failure:
        raise ValueError(failure)
    if not isinstance(data, list):
        raise ValueError("client department response must be a list")
    flattened = _flatten_tree(data)
    matches = _matches_query(flattened, args.query or "", args.limit)
    print(
        json.dumps(
            {
                "kind": "department",
                "client_id": args.client_id,
                "query": args.query or "",
                "count": len(matches),
                "matches": matches,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CRM API 辅助 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    metadata = subparsers.add_parser("metadata", help="抓取或缓存 CRM 元数据")
    metadata_subparsers = metadata.add_subparsers(dest="resource", required=True)
    metadata_candidate = metadata_subparsers.add_parser("candidate", help="缓存候选人字段元数据")
    metadata_candidate.add_argument("--suffix", default="coldcall")
    metadata_candidate.add_argument("--output", required=True)
    metadata_candidate.add_argument("--base-url", default=os.environ.get("CRM_BASE_URL", DEFAULT_BASE_URL))
    metadata_candidate.add_argument("--user-id", default=os.environ.get("CRM_USER_ID"))
    metadata_candidate.add_argument("--request-version", default=os.environ.get("CRM_REQUEST_VERSION"))
    metadata_candidate.add_argument("--cookie-env", default=CRM_COOKIE_ENV)
    metadata_candidate.set_defaults(func=cmd_metadata_candidate)

    auth = subparsers.add_parser("auth", help="登录态探针")
    auth_subparsers = auth.add_subparsers(dest="action", required=True)
    auth_check = auth_subparsers.add_parser("check", help="用候选人元数据接口检查登录态")
    auth_check.add_argument("--suffix", default="coldcall")
    auth_check.add_argument("--base-url", default=os.environ.get("CRM_BASE_URL", DEFAULT_BASE_URL))
    auth_check.add_argument("--user-id", default=os.environ.get("CRM_USER_ID"))
    auth_check.add_argument("--request-version", default=os.environ.get("CRM_REQUEST_VERSION"))
    auth_check.add_argument("--cookie-env", default=CRM_COOKIE_ENV)
    auth_check.add_argument("--no-cookie", action="store_true")
    auth_check.set_defaults(func=cmd_auth_check)

    candidate = subparsers.add_parser("candidate", help="候选人 payload 工具")
    candidate_subparsers = candidate.add_subparsers(dest="action", required=True)

    validate = candidate_subparsers.add_parser("validate", help="校验候选人 JSON")
    validate.add_argument("--input", required=True)
    validate.add_argument("--metadata")
    validate.add_argument("--strict-fields", action="store_true")
    validate.set_defaults(func=cmd_candidate_validate)

    compose = candidate_subparsers.add_parser("compose", help="离线生成候选人 payload JSON")
    compose.add_argument("--input", required=True)
    compose.add_argument("--lookup-cache", required=True)
    compose.add_argument("--output", required=True)
    compose.set_defaults(func=cmd_candidate_compose)

    add = candidate_subparsers.add_parser("add", help="生成新增候选人请求摘要或执行显式确认后的真实写入")
    add.add_argument("--input", required=True)
    add.add_argument("--metadata")
    add.add_argument("--output")
    add.add_argument("--dry-run", action="store_true")
    add.add_argument(
        "--confirm-real-write",
        action="store_true",
        help="显式确认执行真实 CRM 新增写入；默认不启用",
    )
    add.add_argument("--strict-fields", action="store_true")
    add.add_argument("--base-url", default=os.environ.get("CRM_BASE_URL", DEFAULT_BASE_URL))
    add.add_argument("--user-id", default=os.environ.get("CRM_USER_ID"))
    add.add_argument("--request-version", default=os.environ.get("CRM_REQUEST_VERSION"))
    add.add_argument("--cookie-env", default=CRM_COOKIE_ENV)
    add.set_defaults(func=cmd_candidate_add)

    duplicate_check = candidate_subparsers.add_parser(
        "duplicate-check",
        help="用邮箱自动补全接口做只读重复候选人预检",
    )
    duplicate_check.add_argument("--email", required=True)
    duplicate_check.add_argument("--type", default="")
    duplicate_check.add_argument("--base-url", default=os.environ.get("CRM_BASE_URL", DEFAULT_BASE_URL))
    duplicate_check.add_argument("--cookie-env", default=CRM_COOKIE_ENV)
    duplicate_check.set_defaults(func=cmd_candidate_duplicate_check)

    lookup = subparsers.add_parser("lookup", help="只读查询 CRM 字典和外键 ID")
    lookup_subparsers = lookup.add_subparsers(dest="target", required=True)
    lookup_tree = lookup_subparsers.add_parser("tree", help="查询城市/行业/职能/渠道/文件夹树")
    lookup_tree.add_argument("--kind", required=True, choices=sorted(TREE_ENDPOINTS))
    lookup_tree.add_argument("--query", default="")
    lookup_tree.add_argument("--limit", type=int, default=20)
    lookup_tree.add_argument("--base-url", default=os.environ.get("CRM_BASE_URL", DEFAULT_BASE_URL))
    lookup_tree.add_argument("--cookie-env", default=CRM_COOKIE_ENV)
    lookup_tree.set_defaults(func=cmd_lookup_tree)

    lookup_company = lookup_subparsers.add_parser("company", help="按公司名查询 client ID")
    lookup_company.add_argument("--name", required=True)
    lookup_company.add_argument("--limit", type=int, default=10)
    lookup_company.add_argument("--base-url", default=os.environ.get("CRM_BASE_URL", DEFAULT_BASE_URL))
    lookup_company.add_argument("--cookie-env", default=CRM_COOKIE_ENV)
    lookup_company.set_defaults(func=cmd_lookup_company)

    lookup_user = lookup_subparsers.add_parser("user", help="查询 owner/user ID")
    lookup_user.add_argument("--query", default="")
    lookup_user.add_argument("--limit", type=int, default=20)
    lookup_user.add_argument("--base-url", default=os.environ.get("CRM_BASE_URL", DEFAULT_BASE_URL))
    lookup_user.add_argument("--cookie-env", default=CRM_COOKIE_ENV)
    lookup_user.set_defaults(func=cmd_lookup_user)

    lookup_department = lookup_subparsers.add_parser("department", help="按 client ID 查询部门 ID")
    lookup_department.add_argument("--client-id", required=True)
    lookup_department.add_argument("--query", default="")
    lookup_department.add_argument("--limit", type=int, default=20)
    lookup_department.add_argument("--base-url", default=os.environ.get("CRM_BASE_URL", DEFAULT_BASE_URL))
    lookup_department.add_argument("--cookie-env", default=CRM_COOKIE_ENV)
    lookup_department.set_defaults(func=cmd_lookup_department)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, json.JSONDecodeError, ValueError, error.URLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
