from __future__ import annotations

import argparse
import json
import re
from datetime import date
from itertools import count
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "jd_talent_delivery_run_manifest_v1"


def slugify(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value, flags=re.UNICODE).strip("-._")
    return slug or "jd"


def _is_missing_or_empty_dir(path: Path) -> bool:
    if not path.exists():
        return True
    if not path.is_dir():
        return False
    return not any(path.iterdir())


def _next_output_dir(output_base: Path, slug: str, date_text: str) -> Path:
    base_dir = output_base / f"{slug}-{date_text}"
    if _is_missing_or_empty_dir(base_dir):
        return base_dir

    for run_number in count(2):
        candidate = output_base / f"{slug}-{date_text}-run-{run_number:03d}"
        if _is_missing_or_empty_dir(candidate):
            return candidate

    raise RuntimeError("unreachable output directory allocation state")


def prepare_workspace(jd_path: str | Path, output_base: str | Path, date_text: str, top_n: int) -> dict[str, Any]:
    source_path = Path(jd_path)
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    slug = slugify(source_path.stem)
    output_dir = _next_output_dir(Path(output_base), slug, date_text)
    for child in ["source", "profile", "scoring", "reports", "feishu"]:
        (output_dir / child).mkdir(parents=True, exist_ok=True)

    jd_text = source_path.read_text(encoding="utf-8-sig")
    (output_dir / "source" / "jd.md").write_text(jd_text, encoding="utf-8-sig")

    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "source_jd_path": str(source_path),
        "output_dir": str(output_dir),
        "top_n": top_n,
        "date": date_text,
    }
    (output_dir / "run-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JD talent delivery workspace helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--jd-path", required=True)
    prepare_parser.add_argument("--output-base", default="data/output")
    prepare_parser.add_argument("--date", default=date.today().isoformat())
    prepare_parser.add_argument("--top-n", type=int, default=30)

    args = parser.parse_args(argv)
    if args.command == "prepare":
        manifest = prepare_workspace(
            jd_path=args.jd_path,
            output_base=args.output_base,
            date_text=args.date,
            top_n=args.top_n,
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
