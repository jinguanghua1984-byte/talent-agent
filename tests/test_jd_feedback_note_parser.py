import json

import pytest

from scripts.jd_feedback_note_parser import (
    build_feedback_prompt,
    extract_json_object,
    parse_feedback_note,
)


class FakeClient:
    def __init__(self, response: str | Exception):
        self.response = response
        self.calls: list[dict] = []

    def complete(self, messages, model, max_tokens):
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "max_tokens": max_tokens,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _response(**overrides) -> str:
    data = {
        "feedback_label": "认可",
        "feedback_stage": "匹配",
        "reason_codes": ["strong_candidate_ranked_low"],
        "hunter_note": "候选人方向准确，可以沟通。",
        "parse_confidence": 0.91,
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def test_build_feedback_prompt_includes_field_meanings_and_note() -> None:
    prompt = build_feedback_prompt("方向匹配，有大模型平台经验，建议优先联系。")

    assert "feedback_label" in prompt
    assert "feedback_stage" in prompt
    assert "reason_codes" in prompt
    assert "hunter_note" in prompt
    assert "parse_confidence" in prompt
    assert "认可" in prompt
    assert "待定" in prompt
    assert "不认可" in prompt
    assert "方向匹配，有大模型平台经验，建议优先联系。" in prompt


@pytest.mark.parametrize(
    "text",
    [
        _response(),
        "```json\n" + _response() + "\n```",
        "解析结果如下：\n" + _response() + "\n请参考。",
    ],
)
def test_extract_json_object_accepts_common_llm_wrappers(text: str) -> None:
    result = extract_json_object(text)

    assert result["feedback_label"] == "认可"
    assert result["feedback_stage"] == "匹配"
    assert result["reason_codes"] == ["strong_candidate_ranked_low"]
    assert result["parse_confidence"] == 0.91


def test_parse_feedback_note_returns_valid_high_confidence_result() -> None:
    client = FakeClient(_response())

    result = parse_feedback_note(
        "候选人方向准确，可以沟通。", client=client, model="model-x"
    )

    assert client.calls
    assert result == {
        "feedback_label": "认可",
        "feedback_stage": "匹配",
        "reason_codes": ["strong_candidate_ranked_low"],
        "hunter_note": "候选人方向准确，可以沟通。",
        "feedback_note": "候选人方向准确，可以沟通。",
        "parse_source": "llm",
        "parse_confidence": 0.91,
        "review_required": False,
        "review_reasons": [],
    }


def test_parse_feedback_note_downgrades_invalid_fields_to_review_queue() -> None:
    client = FakeClient(
        _response(
            feedback_label="强烈认可",
            feedback_stage="外联",
            reason_codes=["strong_candidate_ranked_low", "unknown_reason"],
            parse_confidence=0.88,
        )
    )

    result = parse_feedback_note("看起来不错。", client=client, model="model-x")

    assert result["feedback_label"] == "待定"
    assert result["feedback_stage"] == "匹配"
    assert result["reason_codes"] == ["strong_candidate_ranked_low"]
    assert result["parse_confidence"] == 0.0
    assert result["review_required"] is True
    assert result["review_reasons"] == [
        "invalid_feedback_label",
        "invalid_feedback_stage",
        "invalid_reason_codes",
    ]


def test_parse_feedback_note_low_confidence_requires_review() -> None:
    client = FakeClient(_response(parse_confidence=0.69))

    result = parse_feedback_note("需要确认。", client=client, model="model-x")

    assert result["parse_confidence"] == 0.69
    assert result["review_required"] is True
    assert result["review_reasons"] == ["low_confidence"]


def test_parse_feedback_note_handles_llm_failure_as_review_required() -> None:
    client = FakeClient(RuntimeError("boom"))

    result = parse_feedback_note("原始反馈。", client=client, model="model-x")

    assert result == {
        "feedback_label": "待定",
        "feedback_stage": "匹配",
        "reason_codes": [],
        "hunter_note": "原始反馈。",
        "feedback_note": "原始反馈。",
        "parse_source": "llm",
        "parse_confidence": 0.0,
        "review_required": True,
        "review_reasons": ["llm_error"],
    }
