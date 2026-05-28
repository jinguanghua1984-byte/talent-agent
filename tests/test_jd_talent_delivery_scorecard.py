import json
from pathlib import Path

from scripts.jd_talent_delivery_scorecard import (
    DEFAULT_LABEL_THRESHOLDS,
    build_scorecard,
    validate_scorecard,
)


def _profile() -> dict:
    return {
        "target_role": "大模型推理系统工程师",
        "must_have": ["vLLM", "SGLang", "KV Cache", "Prefill", "Decode"],
        "nice_to_have": ["TensorRT-LLM", "CUDA Graph", "量化", "SLA"],
        "company_pools": {
            "基模公司": ["MiniMax", "月之暗面", "DeepSeek"],
            "大厂AI平台": ["字节跳动", "百度", "阿里云"],
        },
        "title_aliases": ["推理框架工程师", "模型服务工程师", "AI Infra"],
        "exclusion_terms": ["纯前端", "销售", "招聘"],
        "risk_rules": ["求职状态偏低", "只有应用层 RAG 经验"],
    }


def test_build_scorecard_has_required_schema() -> None:
    scorecard = build_scorecard(_profile(), role_id="llm-inference", version="v1")

    assert scorecard["schema"] == "jd_talent_delivery_scorecard_v1"
    assert scorecard["role_id"] == "llm-inference"
    assert scorecard["version"] == "v1"
    assert scorecard["label_thresholds"] == DEFAULT_LABEL_THRESHOLDS
    assert [item["id"] for item in scorecard["dimensions"]] == [
        "company_context",
        "title_focus",
        "must_have",
        "nice_to_have",
        "seniority",
        "education",
        "risk",
    ]
    assert sum(item["weight"] for item in scorecard["dimensions"]) == 100


def test_build_scorecard_can_enable_young_high_potential_policy() -> None:
    scorecard = build_scorecard(
        _profile(),
        role_id="jiukun-product",
        version="v2-young-high-potential",
        young_high_potential=True,
        max_preferred_work_years=5,
    )

    weights = {item["id"]: item["weight"] for item in scorecard["dimensions"]}
    assert weights == {
        "company_context": 14,
        "title_focus": 16,
        "must_have": 24,
        "nice_to_have": 12,
        "seniority": 18,
        "education": 10,
        "risk": 6,
    }
    assert scorecard["seniority_policy"] == {
        "mode": "young_high_potential",
        "preferred_max_work_years": 5,
        "soft_max_work_years": 8,
        "description": "优先推荐 5 年以内年轻高潜候选人；6-8 年保留观察，8 年以上仅作补位。",
    }
    assert any("年轻高潜" in item for item in scorecard["terms"]["risk_rules"])
    assert sum(weights.values()) == 100


def test_validate_scorecard_rejects_missing_dimension_weight() -> None:
    scorecard = build_scorecard(_profile(), role_id="demo", version="v1")
    scorecard["dimensions"][0].pop("weight")

    try:
        validate_scorecard(scorecard)
    except ValueError as exc:
        assert "dimension missing weight" in str(exc)
    else:
        raise AssertionError("validate_scorecard should fail")


def test_validate_scorecard_rejects_invalid_dimension_weight() -> None:
    scorecard = build_scorecard(_profile(), role_id="demo", version="v1")
    scorecard["dimensions"][0]["weight"] = []

    try:
        validate_scorecard(scorecard)
    except ValueError as exc:
        assert "dimension invalid weight" in str(exc)
        assert "company_context" in str(exc)
    else:
        raise AssertionError("validate_scorecard should fail")


def test_cli_writes_scorecard_json(tmp_path: Path) -> None:
    profile_path = tmp_path / "role-profile.json"
    out_path = tmp_path / "scorecard.json"
    profile_path.write_text(json.dumps(_profile(), ensure_ascii=False), encoding="utf-8")

    from scripts.jd_talent_delivery_scorecard import main

    code = main(
        [
            "--profile-json",
            str(profile_path),
            "--role-id",
            "llm-inference",
            "--version",
            "v1",
            "--out",
            str(out_path),
        ]
    )

    assert code == 0
    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert data["role_id"] == "llm-inference"
    assert data["terms"]["must_have"] == ["vLLM", "SGLang", "KV Cache", "Prefill", "Decode"]


def test_cli_writes_young_high_potential_policy(tmp_path: Path) -> None:
    profile_path = tmp_path / "role-profile.json"
    out_path = tmp_path / "scorecard.json"
    profile_path.write_text(json.dumps(_profile(), ensure_ascii=False), encoding="utf-8")

    from scripts.jd_talent_delivery_scorecard import main

    code = main(
        [
            "--profile-json",
            str(profile_path),
            "--role-id",
            "jiukun-product",
            "--version",
            "v2-young-high-potential",
            "--young-high-potential",
            "--max-preferred-work-years",
            "5",
            "--out",
            str(out_path),
        ]
    )

    assert code == 0
    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert data["seniority_policy"]["mode"] == "young_high_potential"
    assert data["seniority_policy"]["preferred_max_work_years"] == 5
