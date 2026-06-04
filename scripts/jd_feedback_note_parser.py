from __future__ import annotations

import json
import re
from typing import Any

from scripts.jd_delivery_feedback import (
    VALID_FEEDBACK_LABELS,
    VALID_FEEDBACK_STAGES,
    VALID_REASON_CODES,
)
from scripts.pipeline_utils import call_llm_with_retry, create_llm_client


DEFAULT_MODEL = "intelligence"
LOW_CONFIDENCE_THRESHOLD = 0.7


def build_feedback_prompt(feedback_note: str) -> str:
    labels = "、".join(sorted(VALID_FEEDBACK_LABELS))
    stages = "、".join(sorted(VALID_FEEDBACK_STAGES))
    reason_codes = "\n".join(f"- {code}" for code in sorted(VALID_REASON_CODES))
    return f"""你是 JD 推荐反馈解析助手。请把业务人员填写的自然语言反馈解析成严格 JSON。

字段含义：
- feedback_label：总体判断，只能是 {labels}。
- feedback_stage：问题或判断所属阶段，只能是 {stages}。
- reason_codes：原因码数组，只能从下列代码中选择；没有明确原因时返回空数组。
{reason_codes}
- hunter_note：保留给人工复盘的一句中文说明，应忠实概括原反馈。
- parse_confidence：0 到 1 的数字，表示你对解析结果的置信度。

只返回 JSON 对象，不要返回 Markdown 或解释文字。JSON 形状：
{{
  "feedback_label": "认可|待定|不认可",
  "feedback_stage": "画像|评分卡|匹配|报告|候选人状态",
  "reason_codes": ["reason_code"],
  "hunter_note": "中文备注",
  "parse_confidence": 0.0
}}

原始反馈：
{feedback_note}
"""


def extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return _loads_object(fenced.group(1))

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return _loads_object(stripped)

    start = text.find("{")
    while start != -1:
        candidate = _balanced_json_slice(text, start)
        if candidate is not None:
            return _loads_object(candidate)
        start = text.find("{", start + 1)
    raise ValueError("LLM response did not contain a JSON object")


def parse_feedback_note(
    feedback_note: str,
    *,
    client: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    resolved_client = client or create_llm_client(provider=provider, model=model)
    resolved_model = model or _client_model(resolved_client) or DEFAULT_MODEL
    messages = [{"role": "user", "content": build_feedback_prompt(feedback_note)}]

    try:
        response = call_llm_with_retry(
            resolved_client,
            resolved_model,
            messages,
            max_tokens=1024,
        )
        parsed = extract_json_object(response)
    except Exception:
        return _fallback_result(feedback_note)

    return _normalize_result(parsed, feedback_note)


def _loads_object(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON response must be an object")
    return data


def _balanced_json_slice(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _client_model(client: Any) -> str | None:
    settings = getattr(client, "settings", None)
    model = getattr(settings, "model", None)
    return model if isinstance(model, str) and model else None


def _fallback_result(feedback_note: str) -> dict[str, Any]:
    return {
        "feedback_label": "待定",
        "feedback_stage": "匹配",
        "reason_codes": [],
        "hunter_note": feedback_note,
        "feedback_note": feedback_note,
        "parse_source": "llm",
        "parse_confidence": 0.0,
        "review_required": True,
        "review_reasons": ["llm_error"],
    }


def _normalize_result(parsed: dict[str, Any], feedback_note: str) -> dict[str, Any]:
    review_reasons: list[str] = []

    label = parsed.get("feedback_label")
    if label not in VALID_FEEDBACK_LABELS:
        label = "待定"
        review_reasons.append("invalid_feedback_label")

    stage = parsed.get("feedback_stage")
    if stage not in VALID_FEEDBACK_STAGES:
        stage = "匹配"
        review_reasons.append("invalid_feedback_stage")

    raw_reason_codes = parsed.get("reason_codes")
    if not isinstance(raw_reason_codes, list):
        reason_codes: list[str] = []
        review_reasons.append("invalid_reason_codes")
    else:
        reason_codes = [
            code for code in raw_reason_codes if isinstance(code, str) and code in VALID_REASON_CODES
        ]
        if len(reason_codes) != len(raw_reason_codes):
            review_reasons.append("invalid_reason_codes")

    confidence = parsed.get("parse_confidence")
    confidence_is_valid = True
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or confidence < 0
        or confidence > 1
    ):
        confidence = 0.0
        confidence_is_valid = False
        review_reasons.append("invalid_parse_confidence")

    if confidence_is_valid and confidence < LOW_CONFIDENCE_THRESHOLD:
        review_reasons.append("low_confidence")

    if "invalid_feedback_label" in review_reasons:
        confidence = 0.0

    hunter_note = parsed.get("hunter_note")
    if not isinstance(hunter_note, str) or not hunter_note.strip():
        hunter_note = feedback_note

    return {
        "feedback_label": label,
        "feedback_stage": stage,
        "reason_codes": reason_codes,
        "hunter_note": hunter_note,
        "feedback_note": feedback_note,
        "parse_source": "llm",
        "parse_confidence": confidence,
        "review_required": bool(review_reasons),
        "review_reasons": review_reasons,
    }
