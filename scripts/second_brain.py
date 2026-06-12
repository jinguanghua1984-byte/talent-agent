"""CLI for Talent-Agent second-brain P0 artifacts."""

from __future__ import annotations

from pathlib import Path
import argparse
import json

from scripts.second_brain_case import prepare_case
from scripts.second_brain_evaluation import evaluate_replay, render_report
from scripts.second_brain_gbrain import export_bundle, import_gbrain
from scripts.second_brain_models import write_json
from scripts.second_brain_query import build_historical_calibration


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _cmd_init(args: argparse.Namespace) -> None:
    repo = Path(args.repo_root)
    for rel in [
        "data/second-brain",
        "data/second-brain/private-cases",
        "data/second-brain/evaluations",
        "data/second-brain/reports",
        "data/second-brain/state",
        "docs/second-brain/cases",
    ]:
        (repo / rel).mkdir(parents=True, exist_ok=True)
    _print_json({"status": "initialized", "repo_root": str(repo)})


def _cmd_prepare_case(args: argparse.Namespace) -> None:
    _print_json(
        prepare_case(
            run_root=args.run_root,
            repo_root=args.repo_root,
            client_id=args.client,
            jd_family=args.jd_family,
        )
    )


def _cmd_export(args: argparse.Namespace) -> None:
    bundle = export_bundle(repo_root=args.repo_root, out_path=args.out)
    _print_json({"status": "exported", "bundle": str(bundle)})


def _cmd_import(args: argparse.Namespace) -> None:
    _print_json(
        import_gbrain(
            repo_root=args.repo_root,
            bundle_path=args.bundle,
            brain_name=args.brain,
            gbrain_bin=args.gbrain_bin,
        )
    )


def _cmd_query(args: argparse.Namespace) -> None:
    _print_json(
        build_historical_calibration(
            repo_root=args.repo_root,
            jd_path=args.jd,
            client_id=args.client,
            jd_family=args.jd_family,
            out_dir=args.out,
            gbrain_results=[],
        )
    )


def _cmd_evaluate(args: argparse.Namespace) -> None:
    calibration_files = [Path(path) for path in args.calibration]
    _print_json(evaluate_replay(calibration_files=calibration_files, out_path=args.out))


def _cmd_report(args: argparse.Namespace) -> None:
    evaluation = json.loads(Path(args.evaluation).read_text(encoding="utf-8"))
    report = render_report(evaluation, args.out)
    _print_json({"status": "reported", "report": str(report)})


def _cmd_rebuild(args: argparse.Namespace) -> None:
    bundle = export_bundle(repo_root=args.repo_root, out_path=args.bundle)
    _print_json(
        import_gbrain(
            repo_root=args.repo_root,
            bundle_path=bundle,
            brain_name=args.brain,
            gbrain_bin=args.gbrain_bin,
        )
    )


def _cmd_taxonomy_suggest(args: argparse.Namespace) -> None:
    payload = {
        "schema_version": "second_brain_taxonomy_suggestions_v1",
        "suggestions": [],
        "source": str(args.events),
    }
    write_json(args.out, payload)
    _print_json({"status": "written", "out": str(args.out)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Second-brain P0 artifact CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--repo-root", default=".")
    init.set_defaults(func=_cmd_init)

    prepare = sub.add_parser("prepare-case")
    prepare.add_argument("--repo-root", default=".")
    prepare.add_argument("--run-root", required=True)
    prepare.add_argument("--client", required=True)
    prepare.add_argument("--jd-family", required=True)
    prepare.set_defaults(func=_cmd_prepare_case)

    export = sub.add_parser("export")
    export.add_argument("--repo-root", default=".")
    export.add_argument("--out", required=True)
    export.set_defaults(func=_cmd_export)

    import_cmd = sub.add_parser("import")
    import_cmd.add_argument("--repo-root", default=".")
    import_cmd.add_argument("--bundle", required=True)
    import_cmd.add_argument("--brain", required=True)
    import_cmd.add_argument("--gbrain-bin", default="gbrain")
    import_cmd.set_defaults(func=_cmd_import)

    query = sub.add_parser("query")
    query.add_argument("--repo-root", default=".")
    query.add_argument("--jd", required=True)
    query.add_argument("--client", required=True)
    query.add_argument("--jd-family", required=True)
    query.add_argument("--out", required=True)
    query.set_defaults(func=_cmd_query)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--calibration", nargs="+", required=True)
    evaluate.add_argument("--out", required=True)
    evaluate.set_defaults(func=_cmd_evaluate)

    report = sub.add_parser("report")
    report.add_argument("--evaluation", required=True)
    report.add_argument("--out", required=True)
    report.set_defaults(func=_cmd_report)

    rebuild = sub.add_parser("rebuild")
    rebuild.add_argument("--repo-root", default=".")
    rebuild.add_argument("--bundle", required=True)
    rebuild.add_argument("--brain", required=True)
    rebuild.add_argument("--gbrain-bin", default="gbrain")
    rebuild.set_defaults(func=_cmd_rebuild)

    taxonomy = sub.add_parser("taxonomy-suggest")
    taxonomy.add_argument("--events", default="data/second-brain/events.jsonl")
    taxonomy.add_argument("--out", required=True)
    taxonomy.set_defaults(func=_cmd_taxonomy_suggest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
