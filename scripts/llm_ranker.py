"""LLM 精排器: 对 Top N 候选人做 LLM 结构化评分"""

from __future__ import annotations

import json
import logging
import os
import re as _re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.pipeline_utils import (
    call_llm_with_retry,
    load_scoring_config,
    read_cache,
    truncate_text_by_relevance,
    write_cache,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("LLM_MODEL", "intelligence")

RANK_PROMPT_TEMPLATE = """你是一位资深猎头，专注 AI/大模型方向的人才评估。

## 任务
根据以下 JD 对候选人列表按匹配度评分。请对每个候选人独立评分。

## JD 内容
{jd_text}

## 评分维度 (总分 100)
1. 岗位匹配度 (30分): 当前职位/期望职位 vs JD 目标角色
2. 技能覆盖率 (25分): 技能标签 vs JD 核心技能要求
3. 经验深度 (20分): 工作年限 + 行业经验 + 公司背景
4. 行业背景 (15分): 行业相关性 + 名企/AI 公司经历
5. 稳定性 (10分): 学历匹配 + 活跃度 + 跳槽频率

## 输出要求
严格按 JSON 数组格式输出，每个候选人一个对象：

```json
[
  {{
    "candidate_id": "候选人ID",
    "total_score": 0-100,
    "维度分": {{
      "岗位匹配度": 0-30,
      "技能覆盖率": 0-25,
      "经验深度": 0-20,
      "行业背景": 0-15,
      "稳定性": 0-10
    }},
    "排序理由": "一句话说明为什么排这个分数",
    "差距分析": "与 JD 要求的主要差距"
  }}
]
```

## 候选人列表
{candidates_text}"""


CALIBRATION_PROMPT_TEMPLATE = """你是一位资深猎头。以下是从多个批次中选出的最优秀候选人。

请对这些人做最终对比排序，确保评分一致。

## JD 内容
{jd_text}

## 评分维度 (总分 100)
1. 岗位匹配度 (30分)
2. 技能覆盖率 (25分)
3. 经验深度 (20分)
4. 行业背景 (15分)
5. 稳定性 (10分)

## 候选人
{candidates_text}

## 输出格式
同上 JSON 数组格式。"""


@dataclass(frozen=True)
class RankScore:
    candidate_id: str
    total_score: float
    dimensions: dict[str, float]
    reason: str
    gap: str


def _format_candidate(c: dict, keywords: list[str]) -> str:
    parts = [f"### {c.get('name', '未知')} (ID: {c.get('id', '未知')})"]

    if c.get("current_title") or c.get("current_company"):
        parts.append(f"- 当前: {c.get('current_company', '')} {c.get('current_title', '')}")

    if c.get("expected_title"):
        parts.append(f"- 期望: {c.get('expected_title', '')}")

    if c.get("work_years"):
        parts.append(f"- 工作年限: {c['work_years']}年")

    if c.get("education"):
        parts.append(f"- 学历: {c.get('education', '')}")

    if c.get("skill_tags"):
        parts.append(f"- 技能: {', '.join(c['skill_tags'])}")

    if c.get("active_state"):
        parts.append(f"- 活跃度: {c.get('active_state', '')}")

    work_exp = c.get("work_experience", [])
    if work_exp:
        exp_parts = []
        for exp in work_exp:
            desc = truncate_text_by_relevance(
                exp.get("description", ""), keywords, max_length=200
            )
            exp_parts.append(
                f"  - {exp.get('company', '')} {exp.get('title', '')} {desc}"
            )
        parts.append("- 工作经历:\n" + "\n".join(exp_parts))

    desc_raw = c.get("_desc_raw", "")
    if desc_raw:
        truncated = truncate_text_by_relevance(desc_raw, keywords, max_length=300)
        parts.append(f"- 个人描述: {truncated}")

    return "\n".join(parts)


def build_rank_prompt(
    jd_text: str,
    candidates: list[dict],
    keywords: list[str] | None = None,
) -> str:
    if keywords is None:
        keywords = []
    candidates_text = "\n\n".join(
        _format_candidate(c, keywords) for c in candidates
    )
    return RANK_PROMPT_TEMPLATE.format(
        jd_text=jd_text, candidates_text=candidates_text
    )


def parse_rank_response(
    response_text: str,
    expected_ids: list[str],
) -> list[RankScore]:
    try:
        json_match = _re.search(
            r"```json\s*(.*?)\s*```", response_text, _re.DOTALL
        )
        json_str = json_match.group(1) if json_match else response_text
        data = json.loads(json_str)
    except (json.JSONDecodeError, AttributeError):
        logger.warning("精排响应 JSON 解析失败")
        return []

    if not isinstance(data, list):
        data = [data]

    results: list[RankScore] = []
    for item in data:
        cand_id = item.get("candidate_id", "")
        if cand_id not in expected_ids:
            continue

        total = float(item.get("total_score", 0))
        if not (0 <= total <= 100):
            logger.warning("候选人 %s 评分 %s 超出范围，已 clamp", cand_id, total)
            total = max(0, min(100, total))

        dimensions = item.get("维度分", {})
        reason = str(item.get("排序理由", ""))
        gap = str(item.get("差距分析", ""))

        results.append(RankScore(
            candidate_id=cand_id,
            total_score=round(total, 1),
            dimensions={k: float(v) for k, v in dimensions.items()},
            reason=reason,
            gap=gap,
        ))

    return results


def rank_single_batch(
    client: Any,
    jd_text: str,
    candidates: list[dict],
    keywords: list[str] | None = None,
    model: str = DEFAULT_MODEL,
) -> list[RankScore]:
    expected_ids = [c.get("id", "") for c in candidates]
    prompt = build_rank_prompt(jd_text, candidates, keywords)
    messages = [{"role": "user", "content": prompt}]
    response_text = call_llm_with_retry(client, model, messages, max_tokens=4096)
    return parse_rank_response(response_text, expected_ids)


def load_or_rank(
    candidate_id: str,
    candidate: dict,
    jd_text: str,
    cache_dir: Path,
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
    keywords: list[str] | None = None,
    force: bool = False,
) -> RankScore | None:
    cache_file = cache_dir / "rank" / f"{candidate_id}.json"

    if not force:
        cached = read_cache(cache_file)
        if cached:
            return RankScore(
                candidate_id=cached["candidate_id"],
                total_score=cached["total_score"],
                dimensions=cached.get("dimensions", {}),
                reason=cached.get("reason", ""),
                gap=cached.get("gap", ""),
            )

    if client is None:
        from scripts.pipeline_utils import create_llm_client
        client = create_llm_client()

    results = rank_single_batch(client, jd_text, [candidate], keywords=keywords, model=model)

    if results:
        score = results[0]
        write_cache(cache_file, {
            "candidate_id": score.candidate_id,
            "total_score": score.total_score,
            "dimensions": score.dimensions,
            "reason": score.reason,
            "gap": score.gap,
        })
        return score

    return None


def rank_candidates(
    client: Any,
    jd_text: str,
    candidates: list[dict],
    batch_size: int = 10,
    keywords: list[str] | None = None,
    model: str = DEFAULT_MODEL,
    cache_dir: Path | None = None,
) -> list[RankScore]:
    all_results: list[RankScore] = []
    scored_ids: set[str] = set()

    if cache_dir:
        rank_dir = cache_dir / "rank"
        if rank_dir.exists():
            for f in rank_dir.glob("*.json"):
                cached = read_cache(f)
                if cached and cached.get("candidate_id"):
                    all_results.append(RankScore(
                        candidate_id=cached["candidate_id"],
                        total_score=cached["total_score"],
                        dimensions=cached.get("dimensions", {}),
                        reason=cached.get("reason", ""),
                        gap=cached.get("gap", ""),
                    ))
                    scored_ids.add(cached["candidate_id"])

    unscored = [c for c in candidates if c.get("id", "") not in scored_ids]

    if not unscored:
        logger.info("所有候选人已有缓存评分")
    else:
        logger.info(
            "开始精排: %d 人已缓存, %d 人待评分, 每批 %d 人",
            len(scored_ids), len(unscored), batch_size,
        )

        for i in range(0, len(unscored), batch_size):
            batch = unscored[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(unscored) + batch_size - 1) // batch_size
            logger.info("精排批次 %d/%d: %d 人", batch_num, total_batches, len(batch))

            try:
                results = rank_single_batch(
                    client, jd_text, batch, keywords=keywords, model=model
                )
                all_results.extend(results)

                if cache_dir:
                    for score in results:
                        cache_file = cache_dir / "rank" / f"{score.candidate_id}.json"
                        write_cache(cache_file, {
                            "candidate_id": score.candidate_id,
                            "total_score": score.total_score,
                            "dimensions": score.dimensions,
                            "reason": score.reason,
                            "gap": score.gap,
                        })
            except Exception as e:
                logger.error("精排批次 %d 失败: %s", batch_num, e)

    all_results.sort(key=lambda r: r.total_score, reverse=True)
    return all_results


def calibration_round(
    client: Any,
    jd_text: str,
    ranked: list[RankScore],
    candidates_map: dict[str, dict],
    batch_size: int = 10,
    top_per_batch: int = 3,
    model: str = DEFAULT_MODEL,
) -> list[RankScore]:
    config = load_scoring_config()
    cal_config = config.get("calibration", {})
    top_n = cal_config.get("top_per_batch", top_per_batch)
    max_cand = cal_config.get("max_candidates", 15)

    # 按批次分组，每批取 top N，确保跨批次多样性
    calibration_ids: list[str] = []
    for i in range(0, len(ranked), batch_size):
        batch = ranked[i:i + batch_size]
        for score in batch[:top_n]:
            calibration_ids.append(score.candidate_id)
        if len(calibration_ids) >= max_cand:
            break

    calibration_ids = calibration_ids[:max_cand]
    if len(calibration_ids) < 3:
        logger.info("候选人数不足，跳过校准轮")
        return ranked

    cal_dicts = []
    for cid in calibration_ids:
        cand = candidates_map.get(cid, {})
        if cand:
            cal_dicts.append(cand)

    if not cal_dicts:
        return ranked

    logger.info("开始校准轮: %d 人", len(cal_dicts))

    candidates_text = "\n\n".join(
        _format_candidate(c, []) for c in cal_dicts
    )
    prompt = CALIBRATION_PROMPT_TEMPLATE.format(
        jd_text=jd_text, candidates_text=candidates_text
    )
    messages = [{"role": "user", "content": prompt}]

    try:
        response_text = call_llm_with_retry(client, model, messages, max_tokens=4096)
        expected_ids = [c.get("id", "") for c in cal_dicts]
        cal_results = parse_rank_response(response_text, expected_ids)

        if cal_results:
            cal_ids = {r.candidate_id for r in cal_results}
            remaining = [r for r in ranked if r.candidate_id not in cal_ids]
            return cal_results + remaining

    except Exception as e:
        logger.error("校准轮失败，使用原始排名: %s", e)

    return ranked
