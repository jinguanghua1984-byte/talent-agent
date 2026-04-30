"""评分 Pipeline 编排入口

运行方式: python -m scripts.score_pipeline <command> [options]

Usage:
    python scripts/score_pipeline.py run --jd-id <id> --source boss --search-keyword <keyword> [options]
    python scripts/score_pipeline.py resume --jd-id <id> --search-keyword <keyword>
    python scripts/score_pipeline.py report --jd-id <id>
    python scripts/score_pipeline.py list-jds
    python scripts/score_pipeline.py status --jd-id <id>
    python scripts/score_pipeline.py clear-cache --jd-id <id>
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

from scripts.jd_analyzer import load_jd_from_file, load_or_analyze
from scripts.coarse_screener import screen_candidates
from scripts.llm_ranker import RankScore, rank_candidates, calibration_round
from scripts.report_generator import generate_report, save_report
from scripts.data_converter import batch_convert
from scripts.pipeline_utils import (
    CACHE_DIR,
    DATA_DIR,
    compute_jd_hash,
    create_llm_client,
    ensure_cache_dir,
    read_cache,
    validate_jd_id,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_COARSE_LIMIT = 50
DEFAULT_FINAL_TOP = 10
DEFAULT_BATCH_SIZE = 10


def find_jd_file(jd_id: str | None, jds_dir: Path | None = None) -> Path | list[Path] | None:
    """查找 JD 文件。

    jd_id 为 None 时列出所有 JD 文件。
    jd_id 非 None 时精确查找对应文件。
    """
    if jds_dir is None:
        jds_dir = DATA_DIR / "jds"

    if jd_id:
        if not validate_jd_id(jd_id):
            print(f"错误: 无效的 jd-id 格式: {jd_id!r}", file=sys.stderr)
            return None
        path = jds_dir / f"{jd_id}.json"
        if path.exists():
            return path
        print(
            f"错误: JD 文件不存在: {path}\n"
            f"提示: 使用 'score_pipeline list-jds' 查看可用 JD",
            file=sys.stderr,
        )
        return None

    if jds_dir.exists():
        return sorted(jds_dir.glob("jd-*.json"))

    return None


def find_search_file(
    keyword: str,
    search_dir: Path | None = None,
    source: str = "boss",
) -> Path | None:
    """查找搜索结果文件，先精确匹配，再模糊匹配。"""
    if search_dir is None:
        search_dir = DATA_DIR / f"{source}-search"

    exact = search_dir / f"search-{keyword}.json"
    if exact.exists():
        return exact

    for f in search_dir.glob(f"search-*{keyword}*.json"):
        return f

    print(
        f"错误: 搜索结果文件不存在 (keyword={keyword}, source={source})\n"
        f"查找目录: {search_dir}",
        file=sys.stderr,
    )
    return None


def load_candidates_from_search(
    search_file: Path,
    source: str = "boss",
) -> list[dict]:
    """从搜索结果文件加载并转换候选人为统一 schema。"""
    with open(search_file, encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    if not items:
        print(f"警告: 搜索结果为空: {search_file}", file=sys.stderr)
        return []

    candidates = batch_convert(items, source)
    print(f"加载了 {len(candidates)} 个候选人 (来源: {search_file.name})", file=sys.stderr)
    return candidates


def run_pipeline(
    jd_id: str,
    jd_text: str,
    candidates: list[dict],
    coarse_limit: int = DEFAULT_COARSE_LIMIT,
    final_top: int = DEFAULT_FINAL_TOP,
    batch_size: int = DEFAULT_BATCH_SIZE,
    model: str = DEFAULT_MODEL,
    cache_dir: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """执行完整的评分 pipeline: JD 分析 → 粗筛 → LLM 精排 → 校准 → 报告。"""
    start_time = time.time()
    jd_hash = compute_jd_hash(jd_text)

    if cache_dir is None:
        cache_dir = ensure_cache_dir(jd_id)

    client = create_llm_client()

    # --- Step 1: JD 分析 ---
    print("\n[1/4] JD 分析...", file=sys.stderr)
    analysis = load_or_analyze(
        jd_text, jd_hash, cache_dir,
        client=client, model=model,
    )
    if analysis is None:
        raise RuntimeError("JD 分析失败，请检查 JD 内容或 LLM 配置")

    print(f"  职位类型: {analysis.position_type}", file=sys.stderr)
    print(f"  核心技能: {analysis.core_skills}", file=sys.stderr)
    print(f"  排除条件: {analysis.exclusion_criteria}", file=sys.stderr)

    # --- Step 2: 粗筛 ---
    print(f"\n[2/4] 粗筛 ({len(candidates)} → Top {coarse_limit})...", file=sys.stderr)
    coarse_results = screen_candidates(
        candidates, analysis, coarse_limit=coarse_limit,
    )
    print(f"  粗筛完成: {len(coarse_results)} 人进入精排", file=sys.stderr)

    if not coarse_results:
        print("警告: 粗筛后无候选人", file=sys.stderr)
        return {"jd_id": jd_id, "analysis": analysis, "coarse": [], "ranked": [], "report": ""}

    # --- Step 3: LLM 精排 ---
    print(f"\n[3/4] LLM 精排 ({len(coarse_results)} 人, 每批 {batch_size} 人)...", file=sys.stderr)
    coarse_ids = {s.candidate_id for s in coarse_results}
    coarse_candidates = [c for c in candidates if c.get("id", "") in coarse_ids]
    candidates_map = {c.get("id", ""): c for c in candidates}

    ranked = rank_candidates(
        client, jd_text, coarse_candidates,
        batch_size=batch_size,
        keywords=analysis.core_skills,
        model=model,
        cache_dir=cache_dir,
    )

    # --- Step 4: 校准轮 ---
    if len(ranked) >= 3:
        print(f"\n[4/4] 校准轮 (Top {min(len(ranked), 15)} 人)...", file=sys.stderr)
        ranked = calibration_round(
            client, jd_text, ranked, candidates_map,
            batch_size=batch_size, model=model,
        )

    elapsed = time.time() - start_time
    print(f"\nPipeline 完成，耗时 {elapsed:.1f}s", file=sys.stderr)

    report = generate_report(
        ranked=ranked,
        candidates_map=candidates_map,
        jd_text=jd_text,
        jd_id=jd_id,
        top_n=final_top,
    )

    return {
        "jd_id": jd_id,
        "analysis": analysis,
        "coarse_count": len(coarse_results),
        "ranked_count": len(ranked),
        "ranked": ranked,
        "report": report,
        "elapsed_seconds": round(elapsed, 1),
    }


def cmd_run(args: argparse.Namespace) -> None:
    """run 子命令: 执行完整评分 pipeline。"""
    jd_file = find_jd_file(args.jd_id)
    if jd_file is None:
        sys.exit(1)

    jd_text = load_jd_from_file(jd_file)
    if jd_text is None:
        sys.exit(1)

    search_file = find_search_file(args.search_keyword, source=args.source)
    if search_file is None:
        sys.exit(1)

    candidates = load_candidates_from_search(search_file, args.source)
    if not candidates:
        sys.exit(1)

    result = run_pipeline(
        jd_id=args.jd_id,
        jd_text=jd_text,
        candidates=candidates,
        coarse_limit=args.coarse_limit,
        final_top=args.final_top,
        batch_size=args.batch_size,
        model=args.model,
        force=args.force,
    )

    report_path = save_report(result["report"], args.jd_id)
    print(f"\n报告已保存: {report_path}", file=sys.stderr)

    top_results = []
    for score in result["ranked"][:args.final_top]:
        top_results.append({
            "rank": len(top_results) + 1,
            "candidate_id": score.candidate_id,
            "total_score": score.total_score,
            "reason": score.reason,
            "gap": score.gap,
            "dimensions": score.dimensions,
        })

    output = {
        "status": "ok",
        "jd_id": args.jd_id,
        "coarse_count": result["coarse_count"],
        "ranked_count": result["ranked_count"],
        "elapsed_seconds": result["elapsed_seconds"],
        "top_candidates": top_results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_resume(args: argparse.Namespace) -> None:
    """resume 子命令: 断点续传，利用已有缓存继续评分。"""
    jd_file = find_jd_file(args.jd_id)
    if jd_file is None:
        sys.exit(1)

    jd_text = load_jd_from_file(jd_file)
    if jd_text is None:
        sys.exit(1)

    if not args.search_keyword:
        print("错误: 断点续传需要 --search-keyword 来重新加载候选人数据", file=sys.stderr)
        sys.exit(1)

    search_file = find_search_file(args.search_keyword, source=args.source)
    if search_file is None:
        sys.exit(1)

    candidates = load_candidates_from_search(search_file, args.source)
    if not candidates:
        sys.exit(1)

    result = run_pipeline(
        jd_id=args.jd_id,
        jd_text=jd_text,
        candidates=candidates,
        coarse_limit=args.coarse_limit,
        final_top=args.final_top,
        batch_size=args.batch_size,
        model=args.model,
        force=False,
    )

    report_path = save_report(result["report"], args.jd_id)
    print(f"\n报告已保存: {report_path}", file=sys.stderr)

    output = {
        "status": "ok",
        "jd_id": args.jd_id,
        "coarse_count": result["coarse_count"],
        "ranked_count": result["ranked_count"],
        "elapsed_seconds": result["elapsed_seconds"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_report(args: argparse.Namespace) -> None:
    """report 子命令: 从缓存重新生成报告。"""
    cache_dir = CACHE_DIR / args.jd_id
    rank_dir = cache_dir / "rank"

    if not rank_dir.exists():
        print("错误: 无评分缓存", file=sys.stderr)
        sys.exit(1)

    ranked = []
    for f in rank_dir.glob("*.json"):
        cached = read_cache(f)
        if cached:
            ranked.append(RankScore(
                candidate_id=cached["candidate_id"],
                total_score=cached["total_score"],
                dimensions=cached.get("dimensions", {}),
                reason=cached.get("reason", ""),
                gap=cached.get("gap", ""),
            ))

    ranked.sort(key=lambda r: r.total_score, reverse=True)

    jd_file = find_jd_file(args.jd_id)
    jd_text = load_jd_from_file(jd_file) if jd_file else "JD 文本不可用"

    report = generate_report(
        ranked=ranked,
        candidates_map={},
        jd_text=jd_text,
        jd_id=args.jd_id,
        top_n=args.final_top,
    )
    print(report)


def cmd_list_jds(jds_dir: Path | None = None) -> None:
    """列出所有可用的 JD 文件。"""
    if jds_dir is None:
        jds_dir = DATA_DIR / "jds"

    if not jds_dir.exists():
        print("无可用 JD", file=sys.stderr)
        return

    jds = sorted(jds_dir.glob("jd-*.json"))
    if not jds:
        print("无可用 JD", file=sys.stderr)
        return

    print(f"可用 JD ({len(jds)} 个):\n")
    for jd_file in jds:
        with open(jd_file, encoding="utf-8") as f:
            data = json.load(f)
        print(f"  {data.get('id', jd_file.stem):<40} {data.get('title', '')} - {data.get('company', '')}")


def cmd_status(args: argparse.Namespace) -> None:
    """status 子命令: 查询 pipeline 各步骤进度。"""
    cache_dir = CACHE_DIR / args.jd_id

    if not cache_dir.exists():
        print(f"Pipeline 未开始: {args.jd_id}", file=sys.stderr)
        return

    analysis = read_cache(cache_dir / "analysis.json")
    if analysis:
        print(f"[已完成] JD 分析: {analysis.get('position_type', '')}")
    else:
        print("[待执行] JD 分析")

    coarse_dir = cache_dir / "coarse"
    coarse_count = len(list(coarse_dir.glob("*.json"))) if coarse_dir.exists() else 0
    print(f"[{'已完成' if coarse_count > 0 else '待执行'}] 粗筛: {coarse_count} 人已评分")

    rank_dir = cache_dir / "rank"
    rank_count = len(list(rank_dir.glob("*.json"))) if rank_dir.exists() else 0
    print(f"[{'已完成' if rank_count > 0 else '待执行'}] 精排: {rank_count} 人已评分")

    cal = read_cache(cache_dir / "calibration.json")
    if cal:
        print("[已完成] 校准轮")
    else:
        print("[待执行] 校准轮")


def cmd_clear_cache(args: argparse.Namespace, cache_dir: Path | None = None) -> None:
    """清除指定 JD 的 pipeline 缓存。"""
    if cache_dir is None:
        cache_dir = CACHE_DIR / args.jd_id

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print(f"已清除缓存: {cache_dir}", file=sys.stderr)
    else:
        print(f"缓存不存在: {cache_dir}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JD 驱动的两阶段候选人评分 Pipeline"
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="执行评分 pipeline")
    run_parser.add_argument("--jd-id", required=True)
    run_parser.add_argument("--source", default="boss", choices=["boss", "maimai"])
    run_parser.add_argument("--search-keyword", required=True)
    run_parser.add_argument("--coarse-limit", type=int, default=DEFAULT_COARSE_LIMIT)
    run_parser.add_argument("--final-top", type=int, default=DEFAULT_FINAL_TOP)
    run_parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    run_parser.add_argument("--model", default=DEFAULT_MODEL)
    run_parser.add_argument("--force", action="store_true")

    resume_parser = subparsers.add_parser("resume", help="断点续传")
    resume_parser.add_argument("--jd-id", required=True)
    resume_parser.add_argument("--search-keyword", required=True)
    resume_parser.add_argument("--source", default="boss", choices=["boss", "maimai"])
    resume_parser.add_argument("--coarse-limit", type=int, default=DEFAULT_COARSE_LIMIT)
    resume_parser.add_argument("--final-top", type=int, default=DEFAULT_FINAL_TOP)
    resume_parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    resume_parser.add_argument("--model", default=DEFAULT_MODEL)

    report_parser = subparsers.add_parser("report", help="生成报告")
    report_parser.add_argument("--jd-id", required=True)
    report_parser.add_argument("--final-top", type=int, default=DEFAULT_FINAL_TOP)

    subparsers.add_parser("list-jds", help="列出所有可用 JD")

    status_parser = subparsers.add_parser("status", help="查询 pipeline 进度")
    status_parser.add_argument("--jd-id", required=True)

    clear_parser = subparsers.add_parser("clear-cache", help="清除缓存")
    clear_parser.add_argument("--jd-id", required=True)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if args.command == "run":
        cmd_run(args)
    elif args.command == "resume":
        cmd_resume(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "list-jds":
        cmd_list_jds()
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "clear-cache":
        cmd_clear_cache(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
