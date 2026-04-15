#!/usr/bin/env python3
"""enrich.py — 字段映射 + 逐字段冲突合并 + 写入

负责将 API 搜索结果映射为 candidate.schema 格式，
处理多源数据冲突，并通过 data-manager.py 写入候选人库。

用法:
    python enrich.py map --platform maimai --api-data <json-string>
    python enrich.py merge --candidate-id <id> --new-data <json-file>
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# 逐字段冲突策略
# ---------------------------------------------------------------------------

LATEST_FIRST_FIELDS = {
    "current_company", "current_title", "expected_salary",
    "expected_city", "status", "active_state",
}

FIRST_SOURCE_FIELDS = {
    "education_experience",
}

MERGE_DEDUP_FIELDS = {
    "skill_tags", "work_experience",
}

MAJORITY_VOTE_FIELDS = {
    "age", "gender",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def merge_fields(existing: dict, new_data: dict) -> dict:
    """按逐字段冲突策略合并新数据到已有候选人。"""
    result = dict(existing)

    for key, value in new_data.items():
        if key.startswith("_"):
            continue

        if value is None or value == "" or value == []:
            continue

        if key in LATEST_FIRST_FIELDS:
            result[key] = value

        elif key in FIRST_SOURCE_FIELDS:
            if not result.get(key):
                result[key] = value

        elif key in MERGE_DEDUP_FIELDS:
            existing_val = result.get(key, [])
            if isinstance(existing_val, list) and isinstance(value, list):
                if key == "skill_tags":
                    merged = list(set(existing_val) | set(value))
                    result[key] = sorted(merged)
                elif key == "work_experience":
                    existing_keys = {
                        (e.get("company", ""), e.get("period", ""))
                        for e in existing_val
                    }
                    merged = list(existing_val)
                    for item in value:
                        item_key = (item.get("company", ""), item.get("period", ""))
                        if item_key not in existing_keys:
                            merged.append(item)
                            existing_keys.add(item_key)
                    result[key] = merged

        elif key in MAJORITY_VOTE_FIELDS:
            if not result.get(key):
                result[key] = value

        else:
            if not result.get(key):
                result[key] = value

    result["updated_at"] = _now_iso()
    return result


def append_source(existing: dict, source: dict) -> dict:
    """追加 source 到 sources 数组（去重）。"""
    result = dict(existing)
    sources = list(result.get("sources", []))

    new_key = (source.get("channel", ""), source.get("platform_id", ""))
    existing_keys = {
        (s.get("channel", ""), s.get("platform_id", ""))
        for s in sources
    }

    if new_key not in existing_keys or not new_key[1]:
        sources.append(source)

    result["sources"] = sources
    return result


def enrich_enrichment_level(existing: dict) -> dict:
    """提升 enrichment_level（只升不降）。"""
    result = dict(existing)
    level_order = {"raw": 0, "partial": 1, "enriched": 2}
    current = level_order.get(result.get("enrichment_level", "raw"), 0)

    for src in result.get("sources", []):
        src_level = level_order.get(src.get("enrichment_level", "raw"), 0)
        current = max(current, src_level)

    level_map = {0: "raw", 1: "partial", 2: "enriched"}
    result["enrichment_level"] = level_map[current]
    return result


# ---------------------------------------------------------------------------
# data-manager.py 交互
# ---------------------------------------------------------------------------

def _get_data_manager_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "data-manager.py",
    )


def _run_data_manager(*args: str) -> dict:
    """调用 data-manager.py 并返回 JSON 输出。"""
    dm_path = _get_data_manager_path()
    if not os.path.exists(dm_path):
        return {"error": f"data-manager.py 不存在: {dm_path}"}

    result = subprocess.run(
        [sys.executable, dm_path, *args],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw_output": result.stdout}


# ---------------------------------------------------------------------------
# CLI 命令
# ---------------------------------------------------------------------------

def cmd_map(args):
    """将 API 数据映射为 schema 格式。"""
    from adapters.maimai import MaimaiAdapter

    adapter = MaimaiAdapter()

    try:
        api_data = json.loads(args.api_data)
    except json.JSONDecodeError as e:
        print(json.dumps({
            "status": "error",
            "code": "INVALID_JSON",
            "message": f"JSON 解析失败: {e}",
        }, ensure_ascii=False, indent=2))
        return 1

    mapped = adapter.map_to_schema(api_data)
    print(json.dumps({
        "status": "ok",
        "data": mapped,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_merge(args):
    """合并新数据到已有候选人。"""
    candidate_id = args.candidate_id

    existing = _run_data_manager("candidate", "get", candidate_id)
    if "error" in existing:
        print(json.dumps({
            "status": "error",
            "code": "CANDIDATE_NOT_FOUND",
            "message": existing["error"],
        }, ensure_ascii=False, indent=2))
        return 1

    with open(args.new_data, "r", encoding="utf-8") as f:
        new_data = json.load(f)

    source = new_data.pop("_source", None)

    merged = merge_fields(existing, new_data)

    if source:
        merged = append_source(merged, source)

    merged = enrich_enrichment_level(merged)

    tmp_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"_tmp_update_{candidate_id}.json",
    )
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    result = _run_data_manager("candidate", "update", candidate_id, tmp_file)

    try:
        os.remove(tmp_file)
    except OSError:
        pass

    if "error" in result:
        print(json.dumps({
            "status": "error",
            "code": "UPDATE_FAILED",
            "message": result["error"],
        }, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({
        "status": "ok",
        "candidate_id": candidate_id,
        "fields_updated": list(set(new_data.keys()) - {"_source"}),
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="数据丰富 CLI")
    subparsers = parser.add_subparsers(dest="command")

    map_p = subparsers.add_parser("map", help="将 API 数据映射为 schema 格式")
    map_p.add_argument("--platform", required=True, help="平台名称")
    map_p.add_argument("--api-data", required=True, help="API 原始数据 (JSON 字符串)")

    merge_p = subparsers.add_parser("merge", help="合并新数据到已有候选人")
    merge_p.add_argument("--candidate-id", required=True, help="候选人 ID")
    merge_p.add_argument("--new-data", required=True, help="新数据 JSON 文件路径")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "map": cmd_map,
        "merge": cmd_merge,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
