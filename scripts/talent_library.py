"""talent-library 统一业务入口。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_detail_targets import export_targets


def _default_detail_targets_path() -> Path:
    return Path("data") / "output" / f"maimai-detail-targets-{date.today().isoformat()}.json"


def _parse_ids(value: str) -> list[int]:
    ids: list[int] = []
    for part in value.split(","):
        text = part.strip()
        if text:
            ids.append(int(text))
    return ids


def _write_result_with_entry_metadata(path: Path, result: dict) -> dict:
    result["metadata"]["entry"] = "talent-library detail"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result


def cmd_detail(args: argparse.Namespace) -> int:
    out_path = Path(args.out) if args.out else _default_detail_targets_path()
    if args.ids:
        result = export_targets(
            db_path=args.db,
            out_path=out_path,
            candidate_ids=_parse_ids(args.ids),
        )
    else:
        recommendation_file = args.top10_file or args.recommendation_file
        result = export_targets(
            db_path=args.db,
            out_path=out_path,
            recommendation_file=recommendation_file,
        )
    result = _write_result_with_entry_metadata(out_path, result)
    print(
        "已生成脉脉批量详情目标文件：{path}\n"
        "联系人：{contacts}，缺失：{missing}\n"
        "下一步：在 maimai-scraper 的“批量详情”中导入该 JSON。".format(
            path=out_path,
            contacts=result["metadata"]["total_contacts"],
            missing=result["metadata"]["missing"],
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="talent-library 业务入口")
    subparsers = parser.add_subparsers(dest="scene", required=True)

    detail = subparsers.add_parser("detail", help="详情补全入口")
    source = detail.add_mutually_exclusive_group(required=True)
    source.add_argument("--ids", help="逗号分隔的候选人 candidate_id，例如 440,747,727")
    source.add_argument("--top10-file", help="talent-library match/search 输出的 TopN JSON 文件")
    source.add_argument("--recommendation-file", help="包含 top10/candidates/matches/results/items 的推荐 JSON 文件")
    detail.add_argument("--db", default="data/talent.db", help="人才库路径，默认 data/talent.db")
    detail.add_argument("--out", help="输出 maimai-scraper 可导入的目标 JSON")
    detail.set_defaults(func=cmd_detail)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
