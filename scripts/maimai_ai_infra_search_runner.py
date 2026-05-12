"""脉脉 AI Infra 搜索执行器。

默认只执行请求模板 dry-run，不访问脉脉网络。真实浏览器执行必须先通过
Phase 0 小样本可行性门禁后再打开。
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_TEMPLATE = {
    "search": {
        "query": "",
        "search_query": "",
        "positions": "",
        "allcompanies": "",
        "degrees": "",
        "worktimes": "",
        "age": "",
        "query_relation": 0,
        "paginationParam": {"page": 1, "size": 30},
        "page": 0,
        "size": 30,
    }
}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def patch_search_body(template: dict[str, Any], batch: dict[str, Any], page: int) -> dict[str, Any]:
    if not isinstance(template, dict):
        raise ValueError("template body must be an object")
    body = copy.deepcopy(template)
    search = body.get("search")
    if not isinstance(search, dict):
        raise ValueError("search must be an object")

    query = str(batch.get("query") or "")
    page_size = int(batch.get("page_size") or search.get("size") or 30)
    search["query"] = query
    if "search_query" in search:
        search["search_query"] = query
    if "paginationParam" not in search or not isinstance(search["paginationParam"], dict):
        search["paginationParam"] = {}
    search["paginationParam"]["page"] = page
    search["paginationParam"]["size"] = page_size
    if "page" in search:
        search["page"] = max(page - 1, 0)
    if "size" in search:
        search["size"] = page_size
    return body


def _load_template(path: str | None) -> dict[str, Any]:
    if not path:
        return copy.deepcopy(DEFAULT_TEMPLATE)
    data = _load_json(Path(path))
    if not isinstance(data, dict):
        raise ValueError("template must be a JSON object")
    return data


def build_dry_run_result(plan: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    batches = []
    for batch in plan.get("batches") or []:
        max_pages = int(batch.get("max_pages") or 1)
        patched_pages = [
            {"page": page, "body": patch_search_body(template, batch, page)}
            for page in range(1, max_pages + 1)
        ]
        batches.append({
            "batch_id": batch.get("batch_id"),
            "status": "dry-run-template-only",
            "pages_fetched": 0,
            "contacts": 0,
            "ab_stop_reason": "dry_run_template_only",
            "patched_pages": patched_pages,
        })
    return {
        "run_id": plan.get("run_id") or f"maimai-ai-infra-{datetime.now().date().isoformat()}",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "dry-run-template-only",
        "execution_mode": "template_patch_only",
        "phase0": {
            "live_search_verified": False,
            "default_live_path": "extension_or_ui_passive_capture",
            "direct_cdp_fetch": "disabled_until_small_sample_verification",
        },
        "batches": batches,
        "contacts": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="脉脉 AI Infra 搜索执行器")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--template")
    parser.add_argument("--dry-run-template-only", action="store_true")
    args = parser.parse_args(argv)

    plan = _load_json(Path(args.plan))
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object")

    if not args.dry_run_template_only:
        raise RuntimeError(
            "live search is disabled until Phase 0 verifies extension/UI execution "
            "without logout, captcha, 403 or 429"
        )

    template = _load_template(args.template)
    result = build_dry_run_result(plan, template)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
