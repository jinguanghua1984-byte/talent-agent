"""猎聘 Campaign DB 到主库同步的安全 handoff 报告。

该模块只导出 campaign-local TalentDB bundle、校验 bundle，并对目标主库做
dry-run import plan；不执行主库 apply。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_campaign import atomic_write_json, ensure_campaign  # noqa: E402
from scripts.talent_sync import export_bundle, plan_import, verify_bundle  # noqa: E402
from scripts.talent_sync_models import CONFIRM_SYNC_TEXT  # noqa: E402


SCHEMA = "liepin_main_db_sync_handoff_v1"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(plan: dict[str, Any], key: str) -> dict[str, int]:
    value = plan.get(key)
    return value if isinstance(value, dict) else {}


def _markdown(summary: dict[str, Any]) -> str:
    bundle = summary["bundle"]
    dry_run = summary["dry_run"]
    lines = [
        "# 猎聘 Campaign DB 主库同步 handoff",
        "",
        f"- campaign：{summary['campaign_id']}",
        f"- source db：{summary['source_db']}",
        f"- target main db：{summary['target_main_db']}",
        f"- bundle：{bundle['path']}",
        f"- bundle sha256：{bundle['sha256']}",
        f"- bundle verified：{str(bundle['verified']).lower()}",
        f"- candidates in bundle：{bundle['tables'].get('candidates', 0)}",
        f"- source profiles in bundle：{bundle['tables'].get('source_profiles', 0)}",
        f"- details in bundle：{bundle['tables'].get('candidate_details', 0)}",
        "",
        "## Dry-run 结果",
        "",
        f"- created candidates：{dry_run['created'].get('candidates', 0)}",
        f"- merged candidates：{dry_run['merged'].get('candidates', 0)}",
        f"- conflict candidates：{dry_run['conflicts'].get('candidates', 0)}",
        f"- skipped candidates：{dry_run['skipped'].get('candidates', 0)}",
        "",
        "## 边界",
        "",
        "- no main db write：true",
        "- apply requires separate confirmation：true",
        "- 本报告只用于人工主库同步前置验收，不执行 `talent_sync.py import --apply`。",
        f"- apply 确认文本：`{CONFIRM_SYNC_TEXT}`",
    ]
    return "\n".join(lines) + "\n"


def write_main_db_sync_handoff(
    campaign_root: str | Path,
    *,
    main_db_path: str | Path = "data/talent.db",
) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    campaign_db = paths.root / "talent.db"
    if not campaign_db.exists():
        raise RuntimeError("campaign db does not exist; run import-search-apply first")

    exports_dir = paths.root / "exports"
    bundle_path = exports_dir / f"talent-sync-{paths.campaign_id}-{_timestamp()}.zip"
    export_summary = export_bundle(campaign_db, bundle_path, mode="full")
    verification = verify_bundle(bundle_path)
    if not verification["ok"]:
        raise RuntimeError("exported bundle failed verification: " + "; ".join(verification["errors"]))

    target_main_db = Path(main_db_path)
    dry_run_plan = plan_import(bundle_path, target_main_db)
    bundle_file = Path(export_summary["bundle_path"])
    summary: dict[str, Any] = {
        "schema": SCHEMA,
        "campaign_id": paths.campaign_id,
        "source_db": campaign_db.as_posix(),
        "target_main_db": target_main_db.as_posix(),
        "bundle": {
            "path": bundle_file.as_posix(),
            "sha256": _sha256(bundle_file),
            "size_bytes": bundle_file.stat().st_size,
            "verified": True,
            "tables": export_summary.get("tables", {}),
            "source_node_id": export_summary.get("source_node_id"),
        },
        "dry_run": {
            "bundle_id": dry_run_plan.get("bundle_id"),
            "source_node_id": dry_run_plan.get("source_node_id"),
            "mode": dry_run_plan.get("mode"),
            "created": _counts(dry_run_plan, "created"),
            "merged": _counts(dry_run_plan, "merged"),
            "conflicts": _counts(dry_run_plan, "conflicts"),
            "skipped": _counts(dry_run_plan, "skipped"),
            "deleted": _counts(dry_run_plan, "deleted"),
            "tombstoned": _counts(dry_run_plan, "tombstoned"),
        },
        "no_main_db_write": True,
        "apply_requires_separate_confirmation": True,
        "apply_confirmation_text": CONFIRM_SYNC_TEXT,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    atomic_write_json(paths.reports_dir / "main-db-sync-handoff.json", summary)
    (paths.reports_dir / "main-db-sync-handoff.md").write_text(_markdown(summary), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成猎聘 Campaign DB 主库同步 handoff。")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--main-db", default="data/talent.db")
    args = parser.parse_args(argv)
    summary = write_main_db_sync_handoff(args.campaign_root, main_db_path=args.main_db)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
