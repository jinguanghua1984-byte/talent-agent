"""从扩展被动 capture 生成脉脉搜索 API 说明书。"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit


SEARCH_API_PATH = "/api/ent/v3/search/basic"

GENERATED_FIELDS = [
    "search.query",
    "search.search_query",
    "search.paginationParam.page",
    "search.paginationParam.size",
    "search.page",
    "search.size",
]

CONFIRMATION_FIELDS = [
    "search.allcompanies",
    "search.degrees",
    "search.query_relation",
    "search.positions",
    "search.worktimes",
    "search.schools",
    "search.major",
]

CRITICAL_FIELDS = [
    "search.query",
    "search.search_query",
    "search.query_relation",
    "search.paginationParam.page",
    "search.paginationParam.size",
    "search.page",
    "search.size",
]

PRIORITY_FILTER_FIELDS = [
    "search.allcompanies",
    "search.degrees",
    "search.degrees_min",
    "search.degrees_max",
    "search.only_bachelor_degree",
    "search.min_only_bachelor_degree",
    "search.max_only_bachelor_degree",
    "search.positions",
    "search.worktimes",
    "search.schools",
    "search.major",
    "search.cities",
    "search.provinces",
    "search.ht_cities",
    "search.ht_provinces",
    "search.mapping_pfs",
]

SECONDARY_FILTER_FIELDS = [
    "search.age",
    "search.min_age",
    "search.max_age",
    "search.gender",
    "search.expected_min_salary",
    "search.expected_max_salary",
    "search.salary",
    "search.job_hunting_status",
    "search.professions",
    "search.is_985",
    "search.is_211",
    "search.is_top_500",
    "search.is_world_500",
    "search.only_bachelor_degree",
    "search.min_only_bachelor_degree",
    "search.max_only_bachelor_degree",
]

DYNAMIC_TEMPLATE_FIELDS = [
    "search.sid",
    "search.sessionid",
    "search.data_version",
    "search.highlight_exp",
]

SENSITIVE_VALUE_FIELDS = {"search.sid", "search.sessionid", "sid", "sessionid"}

FIELD_SEMANTICS = {
    "search.allcompanies": {
        "meaning": "公司/公司集合筛选",
        "employment_scope": "正任职和曾任职默认全选，不区分",
        "separator": "OR",
    },
    "search.degrees": {
        "meaning": "学历筛选",
        "codes": {
            "0": "专科",
            "1": "本科",
            "2": "硕士",
            "3": "博士",
            "100": "自定义范围",
        },
        "presets": {
            "专科及以上": "0,1,2,3",
            "本科及以上": "1,2,3",
            "硕士及以上": "2,3",
            "博士": "3",
        },
        "range_fields": ["search.degrees_min", "search.degrees_max"],
        "range_strategy": "范围选择使用 degrees=100，并写 degrees_min/degrees_max；当前很少使用，可先不进入 runner",
        "range_examples": {
            "专科-硕士": {"degrees": "100", "degrees_min": "0", "degrees_max": "2"},
            "不限-本科": {"degrees": "100", "degrees_min": "", "degrees_max": "1"},
        },
        "only_bachelor_degree": {
            "0": "不限",
            "1": "只看统招本科",
        },
    },
    "search.major": {
        "meaning": "专业名",
        "separator": "OR",
    },
    "search.max_age": {
        "meaning": "年龄范围上限",
        "pair_field": "search.min_age",
        "example": "min_age=16 且 max_age=40 表示 16-40 岁",
    },
    "search.min_age": {
        "meaning": "年龄范围下限",
        "pair_field": "search.max_age",
        "example": "min_age=16 且 max_age=40 表示 16-40 岁",
    },
    "search.positions": {
        "meaning": "候选人职位关键词",
        "separator": "OR",
    },
    "search.query_relation": {
        "0": "AND",
        "1": "OR",
    },
    "search.schools": {
        "meaning": "学校名",
        "separator": "OR",
    },
    "search.worktimes": {
        "meaning": "工作年数筛选",
        "strategy": "忽略快捷档位，优先使用 worktimes_min/worktimes_max",
        "preferred_fields": ["search.worktimes_min", "search.worktimes_max"],
        "range_example": "worktimes_min=4 且 worktimes_max=8 表示工作 4-8 年",
    },
}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _parse_json_maybe(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _request_body(record: dict[str, Any]) -> dict[str, Any]:
    for key in ("rawRequestBody", "body", "requestBody"):
        parsed = _parse_json_maybe(record.get(key))
        if isinstance(parsed, dict):
            return parsed
    return {}


def _candidate_records(payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = []
        if "url" in payload:
            candidates.append(payload)
        for key in ("requests", "newSearchRecords", "latestSearchRecords"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates.extend(value)
    else:
        candidates = []

    for item in candidates:
        if isinstance(item, dict):
            records.append(item)
    return records


def _is_search_record(record: dict[str, Any]) -> bool:
    url = str(record.get("url") or "")
    method = str(record.get("method") or "POST").upper()
    return method == "POST" and urlsplit(url).path == SEARCH_API_PATH


def _search_records(payloads: list[Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in payloads:
        for record in _candidate_records(payload):
            if _is_search_record(record):
                body = _request_body(record)
                search = body.get("search") if isinstance(body, dict) else None
                if isinstance(search, dict):
                    dedupe_key = json.dumps(
                        {
                            "id": record.get("id"),
                            "ts": record.get("ts"),
                            "url": record.get("url"),
                            "body": body,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    normalized = dict(record)
                    normalized["rawRequestBody"] = body
                    records.append(normalized)
    return records


def _response_summary(record: dict[str, Any]) -> dict[str, Any]:
    existing = record.get("responseSummary")
    if isinstance(existing, dict):
        return existing
    data = record.get("responseData")
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    if not isinstance(data, dict):
        data = {}
    items = data.get("list") or data.get("contacts") or data.get("items") or []
    return {
        "total": data.get("total"),
        "total_match": data.get("total_match"),
        "count": data.get("count"),
        "listLength": len(items) if isinstance(items, list) else 0,
    }


def _header_names(record: dict[str, Any]) -> list[str]:
    headers = record.get("requestHeaders") or {}
    if not isinstance(headers, dict):
        return []
    return sorted({str(name).lower() for name in headers.keys() if str(name).strip()})


def _safe_value(field: str, value: Any) -> Any:
    if field in SENSITIVE_VALUE_FIELDS and value not in (None, ""):
        return "<session-value>"
    return value


def _flatten_search_fields(search: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in search.items():
        field = f"search.{key}"
        if key == "paginationParam" and isinstance(value, dict):
            for nested_key, nested_value in value.items():
                values[f"{field}.{nested_key}"] = nested_value
        else:
            values[field] = _safe_value(field, value)
    return values


def _unique_values(values: list[Any]) -> list[Any]:
    by_key: dict[str, Any] = {}
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        by_key[key] = value
    return [by_key[key] for key in sorted(by_key.keys())]


def _observed_in_order(fields: list[str], observed_fields: set[str]) -> list[str]:
    return [field for field in fields if field in observed_fields]


def _build_field_catalog(observed_fields: set[str]) -> dict[str, Any]:
    critical = _observed_in_order(CRITICAL_FIELDS, observed_fields)
    priority_filters = _observed_in_order(PRIORITY_FILTER_FIELDS, observed_fields)
    secondary_filters = _observed_in_order(SECONDARY_FILTER_FIELDS, observed_fields)
    template_only = _observed_in_order(DYNAMIC_TEMPLATE_FIELDS, observed_fields)

    categorized = set(critical + priority_filters + secondary_filters + template_only)
    other_observed = sorted(observed_fields - categorized)
    semantics = {
        field: FIELD_SEMANTICS[field]
        for field in sorted(FIELD_SEMANTICS)
        if field in observed_fields
    }

    return {
        "critical": critical,
        "priority_filters": priority_filters,
        "secondary_filters": secondary_filters,
        "template_only": template_only,
        "other_observed": other_observed,
        "semantics": semantics,
    }


def _sample_summary(record: dict[str, Any], index: int) -> dict[str, Any]:
    body = _request_body(record)
    search = body.get("search") if isinstance(body, dict) else {}
    if not isinstance(search, dict):
        search = {}
    response = _response_summary(record)
    return {
        "index": index,
        "id": record.get("id") or f"sample-{index}",
        "ts": record.get("ts") or "",
        "url": record.get("url") or "",
        "method": record.get("method") or "POST",
        "query": search.get("query") or search.get("search_query") or "",
        "headerNames": _header_names(record),
        "response": response,
    }


def build_search_api_spec(payloads: list[Any]) -> dict[str, Any]:
    records = _search_records(payloads)
    if not records:
        raise ValueError("no /api/ent/v3/search/basic POST records found")

    header_sets = [set(_header_names(record)) for record in records]
    observed_any = sorted(set().union(*header_sets)) if header_sets else []
    observed_common = sorted(set.intersection(*header_sets)) if header_sets else []

    field_values: dict[str, list[Any]] = defaultdict(list)
    for record in records:
        search = record["rawRequestBody"]["search"]
        for field, value in _flatten_search_fields(search).items():
            field_values[field].append(value)

    field_observations = {
        field: {
            "sample_count": len(values),
            "values": _unique_values(values),
        }
        for field, values in sorted(field_values.items())
    }

    observed_fields = set(field_observations.keys())
    preserve_only = sorted(
        field
        for field in observed_fields
        if field not in set(GENERATED_FIELDS)
    )
    for field in CONFIRMATION_FIELDS + DYNAMIC_TEMPLATE_FIELDS:
        if field in observed_fields and field not in preserve_only:
            preserve_only.append(field)
    preserve_only = sorted(set(preserve_only))

    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "endpoint": {
            "method": "POST",
            "path": SEARCH_API_PATH,
            "url_examples": sorted({str(record.get("url") or "") for record in records}),
        },
        "samples": {
            "count": len(records),
            "items": [_sample_summary(record, index) for index, record in enumerate(records, start=1)],
        },
        "headers": {
            "observed_any": observed_any,
            "observed_common": observed_common,
            "generation_rule": [
                "从最近一次真实搜索模板复制 requestHeaders",
                "缺少 Content-Type/content-type 时补 application/json",
                "使用页面上下文 fetch，并设置 credentials=include",
                "不在本地脚本中合成 cookie、session 或 csrf token",
            ],
            "browser_managed": ["cookie/session via credentials=include"],
        },
        "body_policy": {
            "generated_fields": GENERATED_FIELDS,
            "preserve_only_fields": preserve_only,
            "confirmation_required_fields": [
                field
                for field in CONFIRMATION_FIELDS
                if field in observed_fields and field not in FIELD_SEMANTICS
            ],
            "dynamic_template_fields": [
                field for field in DYNAMIC_TEMPLATE_FIELDS if field in observed_fields
            ],
        },
        "field_catalog": _build_field_catalog(observed_fields),
        "field_observations": field_observations,
    }


def _format_values(values: list[Any]) -> str:
    return ", ".join(json.dumps(value, ensure_ascii=False) for value in values)


def _append_field_list(lines: list[str], fields: list[str], empty_text: str) -> None:
    if fields:
        lines.extend(f"- `{field}`" for field in fields)
    else:
        lines.append(f"- {empty_text}")


def _format_semantic_line(field: str, mapping: dict[str, Any]) -> str:
    if field == "search.query_relation":
        return f"- `{field}`：`0` = {mapping.get('0')}，`1` = {mapping.get('1')}"
    if field == "search.allcompanies":
        return (
            f"- `{field}`：{mapping.get('meaning')}；"
            f"{mapping.get('employment_scope')}；逗号代表 {mapping.get('separator')}"
        )
    if field == "search.degrees":
        codes = mapping.get("codes") or {}
        return (
            f"- `{field}`：{mapping.get('meaning')}；"
            f"`0` = {codes.get('0')}，`1` = {codes.get('1')}，"
            f"`2` = {codes.get('2')}，`3` = {codes.get('3')}，"
            f"`100` = {codes.get('100')}"
        )
    if field == "search.worktimes":
        return (
            f"- `{field}`：忽略快捷档位，优先使用 `worktimes_min`/`worktimes_max` "
            "表示具体工作年数"
        )
    if field in {"search.min_age", "search.max_age"}:
        return f"- `{field}`：{mapping.get('meaning')}；{mapping.get('example')}"
    if mapping.get("separator"):
        return f"- `{field}`：{mapping.get('meaning')}；逗号代表 {mapping.get('separator')}"
    formatted = "，".join(f"`{key}` = {value}" for key, value in mapping.items())
    return f"- `{field}`：{formatted}"


def write_markdown_spec(spec: dict[str, Any], path: Path) -> None:
    lines = [
        "# 脉脉搜索 API 说明书",
        "",
        f"- 生成时间：{spec.get('generatedAt', '')}",
        f"- 方法：`{spec['endpoint']['method']}`",
        f"- 路径：`{spec['endpoint']['path']}`",
        f"- 样本数：{spec['samples']['count']}",
        "",
        "## 请求头策略",
        "",
        f"- 共同出现请求头：`{', '.join(spec['headers']['observed_common']) or '无'}`",
        f"- 任一样本出现请求头：`{', '.join(spec['headers']['observed_any']) or '无'}`",
        "- 生成规则：复制最近一次真实搜索模板的 requestHeaders；缺少 Content-Type 时补 `application/json`；页面上下文 fetch 使用 `credentials=include`。",
        "- 禁止：本地脚本不得合成 cookie、session 或 csrf token。",
        "",
        "## 可生成字段",
        "",
    ]
    lines.extend(f"- `{field}`" for field in spec["body_policy"]["generated_fields"])
    catalog = spec.get("field_catalog") or {}
    lines.extend(["", "## 字段优先级", ""])
    lines.extend(["### 关键字段", ""])
    _append_field_list(lines, catalog.get("critical") or [], "当前样本未观测到关键字段。")
    semantics = catalog.get("semantics") or {}
    if semantics:
        lines.extend(["", "### 已确认语义", ""])
        for field, mapping in semantics.items():
            lines.append(_format_semantic_line(field, mapping))
    lines.extend(["", "### 优先确认筛选字段", ""])
    _append_field_list(lines, catalog.get("priority_filters") or [], "当前样本未观测到优先筛选字段。")
    lines.extend(["", "### 次级筛选字段", ""])
    _append_field_list(lines, catalog.get("secondary_filters") or [], "当前样本未观测到次级筛选字段。")
    lines.extend(["", "### 模板保留字段", ""])
    _append_field_list(lines, catalog.get("template_only") or [], "当前样本未观测到模板保留字段。")
    lines.extend(["", "### 其他已观测字段", ""])
    _append_field_list(lines, catalog.get("other_observed") or [], "没有未分组字段。")
    lines.extend(["", "## 只保留字段", ""])
    lines.extend(f"- `{field}`" for field in spec["body_policy"]["preserve_only_fields"])
    lines.extend(["", "## 字段观测", "", "| 字段 | 样本数 | 观测值 |", "| --- | --- | --- |"])
    for field, item in spec["field_observations"].items():
        lines.append(
            f"| `{field}` | {item['sample_count']} | {_format_values(item['values'])} |"
        )
    lines.extend(["", "## 样本摘要", "", "| # | 查询词 | 响应 total | count | listLength |", "| --- | --- | --- | --- | --- |"])
    for sample in spec["samples"]["items"]:
        response = sample.get("response") or {}
        lines.append(
            "| {index} | `{query}` | {total} | {count} | {list_length} |".format(
                index=sample.get("index"),
                query=sample.get("query", ""),
                total=response.get("total"),
                count=response.get("count"),
                list_length=response.get("listLength"),
            )
        )
    lines.extend(["", "## 待用户确认", ""])
    if spec["body_policy"]["confirmation_required_fields"]:
        lines.extend(
            f"- `{field}` 的 UI 含义和可写入策略"
            for field in spec["body_policy"]["confirmation_required_fields"]
        )
    else:
        lines.append("- 当前样本没有出现需要额外确认的筛选字段。")
    lines.extend([
        "",
        "## 当前结论",
        "",
        "默认自动搜索仍只生成关键词和分页字段；其他筛选字段必须保留真实模板值，直到用户确认语义后再进入 runner。",
    ])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8-sig")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成脉脉搜索 API 说明书")
    parser.add_argument("--input", nargs="+", required=True, help="扩展导出的 capture JSON，可传多个")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args(argv)

    payloads = [_load_json(Path(item)) for item in args.input]
    spec = build_search_api_spec(payloads)
    _write_json(Path(args.out_json), spec)
    write_markdown_spec(spec, Path(args.out_md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
