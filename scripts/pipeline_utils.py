"""pipeline 共享工具: LLM 客户端, 缓存, 校验, 截断"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache" / "pipeline"
RULES_DIR = PROJECT_ROOT / "rules"
SKILLS_RULES_DIR = PROJECT_ROOT / ".claude" / "skills" / "platform-match" / "rules"


def compute_jd_hash(jd_text: str) -> str:
    """计算 JD 文本的 SHA-256 hash，用于缓存失效检测。"""
    return hashlib.sha256(jd_text.encode("utf-8")).hexdigest()


_JD_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_jd_id(jd_id: str) -> bool:
    """校验 jd-id 格式，只允许字母数字下划线连字符。"""
    return bool(_JD_ID_PATTERN.match(jd_id))


def load_scoring_config() -> dict[str, Any]:
    """加载评分配置。优先从 CWD 下的 scoring-config.json，然后 rules/ 目录。"""
    # 优先 CWD 下直接查找（支持测试 monkeypatch.chdir）
    cwd_config = Path.cwd() / "scoring-config.json"
    if cwd_config.exists():
        with open(cwd_config, encoding="utf-8") as f:
            return json.load(f)
    # CWD 下的 rules 目录
    cwd_rules_config = Path.cwd() / "rules" / "scoring-config.json"
    if cwd_rules_config.exists():
        with open(cwd_rules_config, encoding="utf-8") as f:
            return json.load(f)
    # 回退到项目根目录
    config_path = RULES_DIR / "scoring-config.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    return _default_scoring_config()


def load_company_aliases() -> dict[str, list[str]]:
    """加载公司别名映射。合并 skills 和 rules 目录的配置。"""
    aliases: dict[str, list[str]] = {}
    for path in [SKILLS_RULES_DIR / "company-aliases.json",
                 RULES_DIR / "company-aliases.json"]:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                for company, alias_list in data.items():
                    if company in aliases:
                        aliases[company] = list(set(aliases[company] + alias_list))
                    else:
                        aliases[company] = alias_list
    return aliases


def _default_scoring_config() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "top_companies": [],
        "ai_companies": [],
        "coarse_weights": {
            "core_skill_hit": 3,
            "supplement_skill_hit": 1,
            "exclusion_penalty": 20,
            "company_bonus": 5,
        },
        "rank_dimensions": [
            {"name": "岗位匹配度", "weight": 30},
            {"name": "技能覆盖率", "weight": 25},
            {"name": "经验深度", "weight": 20},
            {"name": "行业背景", "weight": 15},
            {"name": "稳定性", "weight": 10},
        ],
        "calibration": {"top_per_batch": 3, "max_candidates": 15},
    }


def ensure_cache_dir(base: str | Path) -> Path:
    """创建 pipeline 缓存目录结构。

    当传入 str 时，作为 jd_id 校验后拼接到 CACHE_DIR。
    当传入 Path 时，直接作为基础路径创建子目录。
    """
    if isinstance(base, Path):
        target = base
    else:
        if not validate_jd_id(base):
            raise ValueError(f"无效的 jd-id: {base!r}")
        target = CACHE_DIR / base

    for sub in ["coarse", "rank"]:
        (target / sub).mkdir(parents=True, exist_ok=True)
    return target


def read_cache(path: Path) -> dict | None:
    """读取缓存文件，失败返回 None。"""
    try:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("缓存读取失败 %s: %s", path, e)
    return None


def write_cache(path: Path, data: dict) -> Path:
    """原子写入缓存文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def create_llm_client() -> Any:
    """创建 Anthropic 客户端。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "未设置 ANTHROPIC_API_KEY。请在 .env 文件中配置，参考 .env.example"
        )
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def call_llm_with_retry(
    client: Any,
    model: str,
    messages: list[dict],
    max_tokens: int = 4096,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> str:
    """带重试和错误处理的 LLM 调用。"""
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            error_str = str(e).lower()
            last_error = e

            if "api_key" in error_str or "authentication" in error_str:
                raise EnvironmentError(
                    "API Key 无效或缺失，请检查 .env 中的 ANTHROPIC_API_KEY"
                ) from e
            if "rate_limit" in error_str or "429" in error_str:
                wait = retry_delay * (2 ** attempt)
                logger.warning("速率限制，等待 %.1fs 后重试 (第 %d 次)", wait, attempt + 1)
                time.sleep(wait)
                continue
            if "timeout" in error_str or "connection" in error_str:
                raise ConnectionError(
                    f"LLM 调用超时或网络错误: {e}"
                ) from e
            raise

    raise ConnectionError(
        f"LLM 调用失败，已重试 {max_retries} 次: {last_error}"
    )


def truncate_text_by_relevance(
    text: str,
    keywords: list[str],
    max_length: int = 500,
) -> str:
    """按 JD 相关性优先截断文本。"""
    if len(text) <= max_length:
        return text

    sentences = re.split(r"(?<=[。！？；\n])", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return text[:max_length]

    keywords_lower = [k.lower() for k in keywords]

    def relevance(s: str) -> tuple[int, int]:
        s_lower = s.lower()
        hits = sum(1 for k in keywords_lower if k in s_lower)
        return (-hits, sentences.index(s))

    sorted_sentences = sorted(sentences, key=relevance)

    result_parts: list[str] = []
    total_len = 0
    for s in sorted_sentences:
        if total_len + len(s) > max_length:
            break
        result_parts.append(s)
        total_len += len(s)

    if total_len + sum(len(s) for s in sorted_sentences[len(result_parts):]) <= max_length:
        return text

    return "".join(result_parts) + "..."
