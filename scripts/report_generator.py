"""报告生成: 生成 Top N 排序的 Markdown 报告"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from scripts.llm_ranker import RankScore

logger = logging.getLogger(__name__)


def format_score_table(
    score: RankScore,
    candidate: dict,
    rank: int,
) -> str:
    name = candidate.get("name", score.candidate_id)
    company = candidate.get("current_company", "")
    title = candidate.get("current_title", "")
    city = candidate.get("city", "")

    lines = [
        f"### {rank}. {name}",
        f"**总分: {score.total_score}** | {company} · {title} | {city}",
        "",
        "| 维度 | 分数 |",
        "|------|------|",
    ]
    for dim_name, dim_score in score.dimensions.items():
        lines.append(f"| {dim_name} | {dim_score} |")

    if score.reason:
        lines.append(f"\n**排序理由:** {score.reason}")
    if score.gap:
        lines.append(f"**差距分析:** {score.gap}")

    return "\n".join(lines)


def generate_report(
    ranked: list[RankScore],
    candidates_map: dict[str, dict],
    jd_text: str,
    jd_id: str,
    top_n: int = 10,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top = ranked[:top_n]

    lines = [
        f"# 候选人评分报告",
        f"",
        f"**JD ID:** {jd_id}",
        f"**生成时间:** {now}",
        f"**候选总数:** {len(ranked)}",
        f"**Top {top_n} 列表:**",
        f"",
        "---",
        "",
    ]

    for rank, score in enumerate(top, 1):
        candidate = candidates_map.get(score.candidate_id, {})
        lines.append(format_score_table(score, candidate, rank))
        lines.append("")
        lines.append("---")
        lines.append("")

    if top:
        avg_score = sum(s.total_score for s in top) / len(top)
        lines.extend([
            "## 统计摘要",
            "",
            f"- Top {len(top)} 平均分: {avg_score:.1f}",
            f"- 最高分: {top[0].total_score} ({candidates_map.get(top[0].candidate_id, {}).get('name', '')})",
            f"- 最低分: {top[-1].total_score} ({candidates_map.get(top[-1].candidate_id, {}).get('name', '')})",
        ])

    return "\n".join(lines)


def save_report(report: str, jd_id: str, output_dir: Path | None = None) -> Path:
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"score-report-{jd_id}.md"
    filepath = output_dir / filename
    filepath.write_text(report, encoding="utf-8")
    logger.info("报告已保存: %s", filepath)
    return filepath