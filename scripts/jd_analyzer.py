"""JD 分析器: 用 LLM 从 JD 文本中提取结构化信息"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scripts.pipeline_utils import (
    call_llm_with_retry,
    compute_jd_hash,
    read_cache,
    write_cache,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_INJECTION_PATTERNS = re.compile(
    r"(ignore|disregard|forget|overlook)\s+(all\s+)?"
    r"(previous|above|prior)?\s*(instructions?|rules?|prompts?)",
    re.IGNORECASE,
)

JD_ANALYSIS_PROMPT = """你是一位资深猎头助手。请分析以下职位描述(JD)，提取结构化信息。

## 输出要求
请严格按以下 JSON 格式输出，不要添加任何其他内容：

```json
{{
  "core_skills": ["技能1", "技能2", ...],
  "supplement_skills": ["补充技能1", ...],
  "position_type": "职位类型",
  "experience_range": [最低年限, 最高年限],
  "education_requirement": "学历要求",
  "industry_preference": ["行业1", ...],
  "exclusion_criteria": ["排除条件1", ...]
}}
```

## 提取规则
1. **core_skills**: JD 中明确要求的硬技能（如 "agent", "langchain", "rag", "python", "产品规划"），3-8 个
2. **supplement_skills**: JD 中提到但非核心的技能（如 "数据分析", "项目管理"），0-5 个
3. **position_type**: 职位类型（如 "AI产品经理", "后端工程师", "数据分析师"）
4. **experience_range**: 经验要求范围，单位年。JD 未明确时上限用 99
5. **education_requirement**: 学历要求（如 "本科以上", "硕士", "不限"）
6. **industry_preference**: 偏好行业（如 "AI", "互联网", "金融"），从 JD 上下文推断
7. **exclusion_criteria**: 不适合的候选人类型（如 "纯算法", "应届生"），从 JD 语气推断

## JD 内容

{jd_text}"""


@dataclass(frozen=True)
class JDAnalysis:
    """JD 分析结果（不可变）。"""
    core_skills: list[str]
    supplement_skills: list[str]
    position_type: str
    experience_range: tuple[int, int]
    education_requirement: str
    industry_preference: list[str]
    exclusion_criteria: list[str]
    raw_jd: str
    jd_hash: str


def from_dict(data: dict) -> JDAnalysis | None:
    """从 dict 构造 JDAnalysis，校验不通过返回 None。"""
    core_skills = data.get("core_skills", [])
    if not core_skills or not isinstance(core_skills, list):
        return None

    exclusion = data.get("exclusion_criteria", [])
    for item in exclusion:
        if _INJECTION_PATTERNS.search(str(item)):
            logger.warning("检测到 prompt injection 尝试，已拒绝: %s", item)
            return None

    exp_range = data.get("experience_range", [0, 99])
    try:
        exp_tuple = (int(exp_range[0]), int(exp_range[1]))
    except (TypeError, ValueError, IndexError):
        exp_tuple = (0, 99)

    return JDAnalysis(
        core_skills=list(core_skills),
        supplement_skills=list(data.get("supplement_skills", [])),
        position_type=str(data.get("position_type", "")),
        experience_range=exp_tuple,
        education_requirement=str(data.get("education_requirement", "不限")),
        industry_preference=list(data.get("industry_preference", [])),
        exclusion_criteria=list(exclusion),
        raw_jd=str(data.get("raw_jd", "")),
        jd_hash=str(data.get("jd_hash", "")),
    )


def validate_analysis(analysis: JDAnalysis) -> list[str]:
    """校验 JDAnalysis，返回错误列表。"""
    errors: list[str] = []
    if not analysis.core_skills:
        errors.append("core_skills 不能为空")
    if analysis.experience_range[0] < 0:
        errors.append(f"experience 下限不能为负数: {analysis.experience_range[0]}")
    if analysis.experience_range[0] > analysis.experience_range[1]:
        errors.append(
            f"经验下限 {analysis.experience_range[0]} > 上限 {analysis.experience_range[1]}"
        )
    return errors


def analyze_jd(
    client: Any,
    jd_text: str,
    model: str = "claude-sonnet-4-6",
    max_retries: int = 3,
) -> JDAnalysis | None:
    """用 LLM 分析 JD 文本，返回结构化结果。"""
    jd_hash = compute_jd_hash(jd_text)
    prompt = JD_ANALYSIS_PROMPT.format(jd_text=jd_text)
    messages = [{"role": "user", "content": prompt}]

    for attempt in range(max_retries):
        try:
            response_text = call_llm_with_retry(
                client, model, messages, max_tokens=2048, max_retries=1,
            )
            json_match = re.search(
                r"```json\s*(.*?)\s*```", response_text, re.DOTALL
            )
            json_str = json_match.group(1) if json_match else response_text
            data = json.loads(json_str)

            data["raw_jd"] = jd_text
            data["jd_hash"] = jd_hash
            data["schema_version"] = SCHEMA_VERSION

            analysis = from_dict(data)
            if analysis is None:
                logger.warning(
                    "JD 分析结果校验失败 (第 %d 次): %s",
                    attempt + 1,
                    json_str[:200],
                )
                continue

            errors = validate_analysis(analysis)
            if errors:
                logger.warning("JD 分析校验错误: %s", errors)
                continue

            return analysis

        except json.JSONDecodeError as e:
            logger.warning(
                "JD 分析 JSON 解析失败 (第 %d 次): %s", attempt + 1, e
            )
        except (EnvironmentError, ConnectionError):
            raise

    logger.error("JD 分析失败，已重试 %d 次", max_retries)
    return None


def load_or_analyze(
    jd_text: str,
    jd_hash: str,
    cache_dir: Path,
    client: Any | None = None,
    model: str = "claude-sonnet-4-6",
) -> JDAnalysis | None:
    """加载缓存或执行 JD 分析。"""
    analysis_path = cache_dir / "analysis.json"
    cached = read_cache(analysis_path)

    if cached and cached.get("jd_hash") == jd_hash:
        if cached.get("schema_version") == SCHEMA_VERSION:
            analysis = from_dict(cached)
            if analysis is not None:
                logger.info("使用缓存的 JD 分析结果")
                return analysis
        else:
            logger.info("缓存 schema_version 不匹配 (%d vs %d)，重新分析",
                        cached.get("schema_version"), SCHEMA_VERSION)

    if client is None:
        from scripts.pipeline_utils import create_llm_client
        client = create_llm_client()

    logger.info("开始 JD 分析...")
    analysis = analyze_jd(client, jd_text, model)

    if analysis:
        data = asdict(analysis)
        data["schema_version"] = SCHEMA_VERSION
        write_cache(analysis_path, data)
        logger.info("JD 分析完成，结果已缓存")

    return analysis


def load_jd_from_file(jd_path: Path) -> str | None:
    """从 JD JSON 文件加载 JD 描述文本。"""
    try:
        with open(jd_path, encoding="utf-8") as f:
            data = json.load(f)
        description = data.get("description", "")
        if not description:
            logger.error("JD 文件缺少 description 字段: %s", jd_path)
            return None
        requirements = data.get("requirements", {})
        if requirements:
            req_text = "\n".join(
                f"- {k}: {v}" for k, v in requirements.items()
            )
            description = f"{description}\n\n【补充要求】\n{req_text}"
        return description
    except (json.JSONDecodeError, OSError) as e:
        logger.error("JD 文件读取失败: %s: %s", jd_path, e)
        return None
