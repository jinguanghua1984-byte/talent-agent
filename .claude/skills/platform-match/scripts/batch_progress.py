#!/usr/bin/env python3
"""batch_progress.py — 批次断点恢复管理

管理模式 1 批次执行的进度，支持中断恢复。

用法:
    python batch_progress.py create --batch-id <id> --candidates <json-array>
    python batch_progress.py update --batch-id <id> --candidate-id <cand-id> --status completed
    python batch_progress.py get --batch-id <id>
    python batch_progress.py list
    python batch_progress.py resume <batch-id>
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


SESSION_DIR = os.path.join(os.getcwd(), "data", "session")


def _progress_path(batch_id: str) -> str:
    os.makedirs(SESSION_DIR, exist_ok=True)
    return os.path.join(SESSION_DIR, f"batch-progress-{batch_id}.json")


def _list_progress_files() -> list[str]:
    if not os.path.exists(SESSION_DIR):
        return []
    return [
        f for f in os.listdir(SESSION_DIR)
        if f.startswith("batch-progress-") and f.endswith(".json")
    ]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cmd_create(args):
    """创建进度文件。"""
    candidates = json.loads(args.candidates)
    progress = {
        "batch_id": args.batch_id,
        "started_at": _now_iso(),
        "candidates": [
            {"id": c["id"], "status": "pending", "result": None}
            for c in candidates
        ],
        "summary": {"completed": 0, "failed": 0, "pending": len(candidates)},
    }
    path = _progress_path(args.batch_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    print(json.dumps(progress, ensure_ascii=False, indent=2))
    return 0


def cmd_update(args):
    """更新候选人状态。"""
    path = _progress_path(args.batch_id)
    if not os.path.exists(path):
        print(f"错误: 进度文件不存在: {args.batch_id}", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        progress = json.load(f)

    updated = False
    for cand in progress["candidates"]:
        if cand["id"] == args.candidate_id:
            cand["status"] = args.status
            cand["result"] = args.result
            updated = True
            break

    if not updated:
        print(f"错误: 候选人 {args.candidate_id} 不在进度文件中", file=sys.stderr)
        return 1

    # 更新摘要
    completed = sum(1 for c in progress["candidates"] if c["status"] == "completed")
    failed = sum(1 for c in progress["candidates"] if c["status"] == "failed")
    pending = sum(1 for c in progress["candidates"] if c["status"] in ("pending", "in_progress"))
    progress["summary"] = {"completed": completed, "failed": failed, "pending": pending}

    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

    print(json.dumps(progress, ensure_ascii=False, indent=2))
    return 0


def cmd_get(args):
    """获取进度。"""
    path = _progress_path(args.batch_id)
    if not os.path.exists(path):
        print(f"错误: 进度文件不存在: {args.batch_id}", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        print(json.dumps(json.load(f), ensure_ascii=False, indent=2))
    return 0


def cmd_list(args):
    """列出所有进度文件。"""
    results = []
    for fname in _list_progress_files():
        path = os.path.join(SESSION_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            progress = json.load(f)
        results.append({
            "batch_id": progress.get("batch_id", ""),
            "started_at": progress.get("started_at", ""),
            "summary": progress.get("summary", {}),
        })
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def cmd_resume(args):
    """获取断点恢复信息。"""
    path = _progress_path(args.batch_id)
    if not os.path.exists(path):
        print(json.dumps({"resumable": False}))
        return 0

    with open(path, "r", encoding="utf-8") as f:
        progress = json.load(f)

    # 找到需要恢复的候选人
    remaining = [
        c for c in progress["candidates"]
        if c["status"] in ("pending", "in_progress")
    ]

    if not remaining:
        print(json.dumps({"resumable": False, "message": "批次已完成"}))
        return 0

    print(json.dumps({
        "resumable": True,
        "batch_id": args.batch_id,
        "completed": progress["summary"]["completed"],
        "total": len(progress["candidates"]),
        "remaining": [{"id": c["id"], "status": c["status"]} for c in remaining],
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批次进度管理 CLI")
    subparsers = parser.add_subparsers(dest="command")

    create_p = subparsers.add_parser("create", help="创建进度文件")
    create_p.add_argument("--batch-id", required=True)
    create_p.add_argument("--candidates", required=True, help="候选人 JSON 数组")

    update_p = subparsers.add_parser("update", help="更新候选人状态")
    update_p.add_argument("--batch-id", required=True)
    update_p.add_argument("--candidate-id", required=True)
    update_p.add_argument("--status", required=True, choices=["pending", "in_progress", "completed", "failed", "not_found"])
    update_p.add_argument("--result", default=None)

    get_p = subparsers.add_parser("get", help="获取进度")
    get_p.add_argument("--batch-id", required=True)

    subparsers.add_parser("list", help="列出所有进度")

    resume_p = subparsers.add_parser("resume", help="获取断点恢复信息")
    resume_p.add_argument("batch_id", help="批次 ID")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "create": cmd_create,
        "update": cmd_update,
        "get": cmd_get,
        "list": cmd_list,
        "resume": cmd_resume,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
