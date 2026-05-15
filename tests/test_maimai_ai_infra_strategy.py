import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.maimai_ai_infra_rank import score_candidate
from scripts.maimai_ai_infra_search_plan import build_search_units, generate_batches, load_strategy
from scripts.talent_models import Candidate, CandidateDetail


def test_strategy_config_contains_required_sections():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    assert strategy["strategy_version"] == "ai-infra-v1"
    assert strategy["human_gates"]["strategy_confirmed"] is False
    assert strategy["human_gates"]["auto_apply_after_clean_dry_run"] is False
    assert strategy["limits"]["pages_per_batch"] == 3
    assert strategy["limits"]["page_size"] == 30
    assert strategy["limits"]["max_batches_per_day"] <= 80
    assert strategy["company_tiers"]["tier1"]
    assert strategy["company_aliases"]["字节跳动"]
    assert strategy["title_batches"]["precision"]
    assert strategy["keyword_packs"]["framework"]
    assert "HR" in strategy["exclude_titles"]
    assert "大专" in strategy["exclude_education"]


def test_generate_batches_prioritizes_tier1_and_keeps_one_position_per_batch():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    batches = generate_batches(strategy)

    assert batches
    assert len(batches) <= strategy["limits"]["max_batches_per_day"]
    assert batches[0]["tier"] == "tier1"
    assert batches[0]["priority"] > batches[-1]["priority"]
    for batch in batches:
        assert set(["batch_id", "company", "position", "query", "priority", "max_pages"]) <= set(batch)
        assert isinstance(batch["position"], str)
        assert "," not in batch["position"]
        assert batch["max_pages"] == strategy["limits"]["pages_per_batch"]
        assert batch["page_size"] == strategy["limits"]["page_size"]
    generic_batches = [batch for batch in batches if batch["title_group"] == "generic"]
    assert generic_batches
    assert all(batch["keyword_pack"] in {"inference", "cluster", "opensource"} for batch in generic_batches)


def test_generate_batches_marks_confirmed_search_filters_including_age_range():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    batch = generate_batches(strategy)[0]

    patch_policy = batch["search_body_patch"]
    assert "search.query_relation" in patch_policy["verified_fields"]
    assert patch_policy["confirmed_filter_fields"] == [
        "search.allcompanies",
        "search.degrees",
        "search.degrees_min",
        "search.degrees_max",
        "search.only_bachelor_degree",
        "search.min_only_bachelor_degree",
        "search.max_only_bachelor_degree",
        "search.positions",
        "search.worktimes",
        "search.worktimes_min",
        "search.worktimes_max",
        "search.min_age",
        "search.max_age",
        "search.schools",
        "search.major",
    ]
    assert "age" not in patch_policy["local_filter_only"]


def _minimal_v2_strategy() -> dict:
    return {
        "strategy_version": "ai-infra-v2",
        "human_gates": {
            "strategy_confirmed": False,
            "auto_apply_after_clean_dry_run": False,
        },
        "limits": {
            "pages_per_batch": 3,
            "page_size": 30,
            "max_contacts_per_batch": 90,
            "max_batches_per_day": 500,
        },
        "company_tiers": {
            "tier1": ["字节跳动"],
            "tier2_priority": ["华为"],
        },
        "company_aliases": {
            "字节跳动": ["字节"],
            "华为": ["昇腾"],
        },
        "title_batches": {
            "precision": ["大模型训练"],
            "technical": ["异构计算"],
            "generic": ["算法工程师"],
        },
        "keyword_packs": {
            "framework": ["AI Infra", "机器学习", "推理框架"],
            "training": ["分布式训练", "训练框架", "GPU"],
            "inference": ["推理", "算子", "加速"],
            "cluster": ["智算", "GPU", "集群"],
            "opensource": ["vLLM", "SGLang", "Triton"],
        },
        "exclude_titles": [],
        "exclude_education": [],
        "v2": {
            "wave_size_units": 2,
            "unit_quotas": {
                "P1_core_precision": 1,
                "P2_technical": 1,
                "P3_generic_with_strong_query": 1,
                "P4_gap_fill": 0,
            },
            "default_filters": {
                "degrees": "1,2,3",
                "worktimes_min": "2",
                "worktimes_max": "10",
                "min_age": "24",
                "max_age": "40",
            },
            "school_gate": {
                "allow_tags": ["985", "211"],
                "reject_tags": ["unknown_school_quality"],
            },
            "age_bands": {
                "best_min": 24,
                "best_max": 35,
                "secondary_max": 40,
            },
        },
    }


def test_build_search_units_compiles_v2_units_with_confirmed_filters():
    strategy = _minimal_v2_strategy()

    units = build_search_units(strategy)

    assert [unit["unit_id"] for unit in units] == ["unit-000001", "unit-000002", "unit-000003"]
    assert len(units) == 3
    assert [unit["wave_id"] for unit in units] == ["wave-001", "wave-001", "wave-002"]
    assert [unit["batch_type"] for unit in units] == [
        "P1_core_precision",
        "P2_technical",
        "P3_generic_with_strong_query",
    ]
    for unit in units:
        filters = unit["search_filters"]
        assert "age" not in filters
        assert unit["max_pages"] <= 3
        assert unit["page_size"] == 30
        assert filters["degrees"] == "1,2,3"
        assert filters["min_age"] == "24"
        assert filters["max_age"] == "40"


def test_build_search_units_rejects_unconfirmed_age_filter():
    strategy = _minimal_v2_strategy()
    strategy["v2"]["default_filters"]["age"] = "24,40"

    try:
        build_search_units(strategy)
    except ValueError as error:
        assert str(error) == "unconfirmed V2 search filter fields: age"
    else:
        raise AssertionError("expected ValueError for unconfirmed age filter")


def test_v2_strategy_config_builds_declared_unit_quotas():
    strategy = load_strategy(Path("configs/maimai-ai-infra-v2-cold-start-strategy.json"))

    units = build_search_units(strategy)
    counts = Counter(unit["batch_type"] for unit in units)

    assert counts == strategy["v2"]["unit_quotas"]
    assert len(units) == 450
    assert units[-1]["batch_type"] == "P4_gap_fill"
    for unit in units:
        filters = unit["search_filters"]
        assert "age" not in filters
        assert "age_min" not in filters
        assert "age_max" not in filters


def test_build_search_units_rejects_incomplete_v2_quotas():
    strategy = _minimal_v2_strategy()
    del strategy["v2"]["unit_quotas"]["P4_gap_fill"]

    with pytest.raises(ValueError, match="v2\\.unit_quotas\\.P4_gap_fill"):
        build_search_units(strategy)


def test_build_search_units_rejects_invalid_wave_size():
    for wave_size in (0, "2"):
        strategy = _minimal_v2_strategy()
        strategy["v2"]["wave_size_units"] = wave_size

        with pytest.raises(ValueError, match="v2\\.wave_size_units"):
            build_search_units(strategy)


def test_search_plan_cli_outputs_v2_units_jsonl(tmp_path: Path):
    from scripts.maimai_ai_infra_search_plan import main

    out_path = tmp_path / "plan.json"
    units_path = tmp_path / "units.jsonl"

    assert main([
        "--config",
        "configs/maimai-ai-infra-v2-cold-start-strategy.json",
        "--out",
        str(out_path),
        "--out-units",
        str(units_path),
    ]) == 0

    lines = units_path.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 450
    first = json.loads(lines[0])
    assert first["unit_id"] == "unit-000001"
    assert any(json.loads(line)["batch_type"] == "P4_gap_fill" for line in lines)


def test_search_plan_cli_outputs_json(tmp_path: Path):
    from scripts.maimai_ai_infra_search_plan import main

    out_path = tmp_path / "plan.json"

    assert main([
        "--config",
        "configs/maimai-ai-infra-search-strategy.json",
        "--out",
        str(out_path),
    ]) == 0

    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert data["strategy_version"] == "ai-infra-v1"
    assert data["batches"]


def test_ai_infra_score_grades_common_candidate_shapes():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))
    detail = CandidateDetail(
        candidate_id=1,
        work_experience=[
            {
                "company": "字节跳动",
                "title": "大模型训练框架工程师",
                "description": "负责分布式训练、训练框架、GPU 调度和 vLLM 推理优化",
            }
        ],
        education_experience=[{"school": "清华大学", "description": "硕士"}],
    )

    high = score_candidate(
        Candidate(
            id=1,
            name="Alice",
            current_company="字节跳动",
            current_title="大模型训练框架工程师",
            education="硕士",
            work_years=5,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        detail,
        mode="detailed",
    )
    assert high["grade"] == "A"
    assert high["score"] >= 80
    assert not high["risk_flags"]

    hr = score_candidate(
        Candidate(id=2, name="Bob", current_company="字节跳动", current_title="HR", education="本科"),
        strategy,
        None,
    )
    assert hr["grade"] == "淘汰"
    assert "excluded_title" in hr["risk_flags"]

    junior_college = score_candidate(
        Candidate(
            id=3,
            name="Cindy",
            current_company="字节跳动",
            current_title="AI Infra 工程师",
            education="大专",
        ),
        strategy,
        None,
    )
    assert junior_college["grade"] == "淘汰"
    assert "excluded_education" in junior_college["risk_flags"]

    weak_company = score_candidate(
        Candidate(id=4, name="Dan", current_company="普通公司", current_title="大模型训练工程师"),
        strategy,
        None,
    )
    assert weak_company["grade"] == "淘汰"
    assert "company_not_targeted" in weak_company["risk_flags"]

    tier2_technical = score_candidate(
        Candidate(
            id=5,
            name="Eve",
            current_company="DeepSeek",
            current_title="推理引擎工程师",
            education="211 重点本科",
            work_years=4,
            skill_tags=("推理", "CUDA", "vLLM", "TensorRT"),
        ),
        strategy,
        CandidateDetail(
            candidate_id=5,
            work_experience=[
                {
                    "company": "DeepSeek",
                    "title": "推理引擎工程师",
                    "description": "负责推理框架、算子优化、CUDA 加速和 vLLM 服务化",
                }
            ],
            education_experience=[{"school": "北京邮电大学", "description": "211"}],
        ),
    )
    assert tier2_technical["grade"] in {"A", "B"}
    assert tier2_technical["tier"] == "tier2_priority"
    assert tier2_technical["evidence"]["title_level"] == "precision"

    generic_with_strong_tech = score_candidate(
        Candidate(
            id=6,
            name="Frank",
            current_company="字节跳动",
            current_title="后端开发工程师",
            education="211 重点本科",
            work_years=6,
            skill_tags=("分布式", "GPU", "SGLang", "推理平台"),
        ),
        strategy,
        CandidateDetail(
            candidate_id=6,
            work_experience=[
                {
                    "company": "字节跳动",
                    "title": "后端开发工程师",
                    "description": "建设大模型推理平台、GPU 调度、SGLang 和 Token 调度链路",
                }
            ],
            education_experience=[{"school": "上海交通大学", "description": "211"}],
        ),
    )
    assert generic_with_strong_tech["grade"] in {"A", "B"}
    assert generic_with_strong_tech["evidence"]["title_level"] == "generic"
    assert "company_not_targeted" not in generic_with_strong_tech["risk_flags"]


def test_score_candidate_list_mode_without_detail_returns_list_mode():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    result = score_candidate(
        Candidate(
            id=100,
            name="List Mode",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="清华大学 985",
            work_years=6,
            age=30,
            skill_tags=("GPU",),
        ),
        strategy,
        None,
        mode="list",
    )

    assert result["score_mode"] == "list"
    assert result["grade"] in {"A", "B", "C", "淘汰"}
    assert "missing_detail_for_detailed_score" not in result["risk_flags"]


def test_score_candidate_list_mode_rejects_non_priority_school():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    result = score_candidate(
        Candidate(
            id=101,
            name="School Gate",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="普通本科",
            work_years=6,
            age=29,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        None,
        mode="list",
    )

    assert result["grade"] == "淘汰"
    assert "school_not_priority" in result["risk_flags"]


def test_score_candidate_age_35_to_40_is_second_tier():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    result = score_candidate(
        Candidate(
            id=102,
            name="Age Band",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="211 重点本科",
            work_years=9,
            age=37,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        None,
        mode="list",
    )

    assert result["age_band"] == "secondary_35_40"
    assert result["grade"] in {"B", "C", "淘汰"}
    assert result["grade"] != "A"


def test_score_candidate_age_over_40_is_rejected():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    result = score_candidate(
        Candidate(
            id=103,
            name="Too Old",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="985 重点本科",
            work_years=12,
            age=41,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        None,
        mode="list",
    )

    assert result["grade"] == "淘汰"
    assert result["age_band"] == "over_40"
    assert "age_over_40" in result["risk_flags"]


def test_score_candidate_detailed_mode_without_detail_caps_grade():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    result = score_candidate(
        Candidate(
            id=104,
            name="Detailed Mode",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="清华大学 985",
            work_years=6,
            age=30,
            skill_tags=("GPU", "vLLM", "SGLang"),
        ),
        strategy,
        None,
        mode="detailed",
    )

    assert result["score_mode"] == "detailed"
    assert result["grade"] in {"C", "淘汰"}
    assert "missing_detail_for_detailed_score" in result["risk_flags"]


def test_score_candidate_top500_requires_context_to_pass_school_gate():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    passing = score_candidate(
        Candidate(
            id=105,
            name="Top500 Pass",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="QS Top500 university",
            work_years=6,
            age=30,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        None,
        mode="list",
    )
    failing_qs = score_candidate(
        Candidate(
            id=106,
            name="QS 900",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="QS ranking 900 university",
            work_years=6,
            age=30,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        None,
        mode="list",
    )
    failing_overseas = score_candidate(
        Candidate(
            id=107,
            name="Overseas Unknown",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="overseas unknown university",
            work_years=6,
            age=30,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        None,
        mode="list",
    )

    assert passing["grade"] != "淘汰"
    assert "school_not_priority" not in passing["risk_flags"]
    assert failing_qs["grade"] == "淘汰"
    assert "school_not_priority" in failing_qs["risk_flags"]
    assert failing_overseas["grade"] == "淘汰"
    assert "school_not_priority" in failing_overseas["risk_flags"]


def test_score_candidate_negated_985_211_text_is_rejected():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    result = score_candidate(
        Candidate(
            id=108,
            name="Negated School",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="非985 非211 普通本科",
            work_years=6,
            age=30,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        None,
        mode="list",
    )

    assert result["grade"] == "淘汰"
    assert "school_not_priority" in result["risk_flags"]


def test_score_candidate_compressed_negated_school_lists_are_rejected():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    negated_cases = [
        "非985/211本科",
        "非985、211本科",
        "非985和211本科",
        "非985与211本科",
        "非985非211本科",
        "非985不是211本科",
        "不是985也不是211本科",
        "非985也非211本科",
        "非985且非211本科",
        "非985并非211本科",
        "既不是985也不是211本科",
        "非清华大学非北京大学本科",
        "不是清华大学不是北京大学本科",
        "非清华大学且非北京大学本科",
        "not QS Top500 or overseas Top500 university",
        "not QS Top500 and overseas Top500 university",
        "neither QS Top500 nor overseas Top500 university",
        "双非（非985/211）本科",
    ]

    for idx, education in enumerate(negated_cases, start=160):
        result = score_candidate(
            Candidate(
                id=idx,
                name=f"Compressed Negation {idx}",
                current_company="Seed",
                current_title="AI Infra 工程师",
                education=education,
                work_years=6,
                age=30,
                skill_tags=("GPU", "vLLM"),
            ),
            strategy,
            None,
            mode="list",
        )

        assert result["grade"] == "淘汰", education
        assert "school_not_priority" in result["risk_flags"], education


def test_score_candidate_list_mode_ignores_detail_but_detailed_mode_uses_it():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))
    detail = CandidateDetail(
        candidate_id=109,
        education_experience=[{"school": "清华大学", "description": "985"}],
        work_experience=[
            {
                "company": "字节跳动",
                "title": "AI Infra 工程师",
                "description": "大模型训练与推理平台",
            }
        ],
    )

    list_result = score_candidate(
        Candidate(
            id=109,
            name="List Ignores Detail",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="普通本科",
            work_years=6,
            age=30,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        detail,
        mode="list",
    )
    detailed_result = score_candidate(
        Candidate(
            id=109,
            name="List Ignores Detail",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="普通本科",
            work_years=6,
            age=30,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        detail,
        mode="detailed",
    )

    assert list_result["grade"] == "淘汰"
    assert "school_not_priority" in list_result["risk_flags"]
    assert detailed_result["grade"] != "淘汰"
    assert "school_not_priority" not in detailed_result["risk_flags"]


def test_score_candidate_mixed_double_non_with_later_priority_school_passes():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    mixed_cases = [
        ("双非本科 清华大学硕士", "清华大学硕士"),
        ("双非本科，QS Top500 硕士", "QS Top500 硕士"),
        ("双非本科，211硕士", "211硕士"),
    ]

    for idx, (education, _) in enumerate(mixed_cases, start=120):
        result = score_candidate(
            Candidate(
                id=idx,
                name=f"Mixed {idx}",
                current_company="Seed",
                current_title="AI Infra 工程师",
                education=education,
                work_years=6,
                age=30,
                skill_tags=("GPU", "vLLM"),
            ),
            strategy,
            None,
            mode="list",
        )

        assert result["grade"] != "淘汰"
        assert "school_not_priority" not in result["risk_flags"]


def test_score_candidate_detailed_mode_mixed_double_non_uses_later_priority_school():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))
    detail = CandidateDetail(
        candidate_id=130,
        education_experience=[
            {"school": "双非本科", "description": "普通本科"},
            {"school": "清华大学", "description": "硕士"},
        ],
        work_experience=[
            {
                "company": "字节跳动",
                "title": "AI Infra 工程师",
                "description": "训练与推理平台",
            }
        ],
    )

    list_result = score_candidate(
        Candidate(
            id=130,
            name="Detail Mixed",
            current_company="Seed",
            current_title="AI Infra 工程师",
            education="双非本科",
            work_years=6,
            age=30,
            skill_tags=("GPU",),
        ),
        strategy,
        detail,
        mode="list",
    )
    detailed_result = score_candidate(
        Candidate(
            id=130,
            name="Detail Mixed",
            current_company="Seed",
            current_title="AI Infra 工程师",
            education="双非本科",
            work_years=6,
            age=30,
            skill_tags=("GPU",),
        ),
        strategy,
        detail,
        mode="detailed",
    )

    assert list_result["grade"] == "淘汰"
    assert "school_not_priority" in list_result["risk_flags"]
    assert detailed_result["grade"] != "淘汰"
    assert "school_not_priority" not in detailed_result["risk_flags"]


def test_score_candidate_mixed_local_negation_keeps_later_priority_school():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    mixed_cases = [
        "非985本科，985硕士",
        "非211本科，211硕士",
        "非QS Top500本科，QS Top500硕士",
        "非清华大学本科，清华大学硕士",
        "not QS Top500 university, overseas Top500 graduate",
    ]

    for idx, education in enumerate(mixed_cases, start=140):
        result = score_candidate(
            Candidate(
                id=idx,
                name=f"Local Negation {idx}",
                current_company="Seed",
                current_title="AI Infra 工程师",
                education=education,
                work_years=6,
                age=30,
                skill_tags=("GPU",),
            ),
            strategy,
            None,
            mode="list",
        )

        assert result["grade"] != "淘汰"
        assert "school_not_priority" not in result["risk_flags"]


def test_score_candidate_detailed_mode_local_negation_keeps_later_priority_school():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))
    detail = CandidateDetail(
        candidate_id=150,
        education_experience=[
            {"school": "非985本科", "description": "普通本科"},
            {"school": "清华大学硕士", "description": "硕士"},
            {"school": "211硕士", "description": "硕士"},
        ],
        work_experience=[
            {
                "company": "字节跳动",
                "title": "AI Infra 工程师",
                "description": "训练与推理平台",
            }
        ],
    )

    list_result = score_candidate(
        Candidate(
            id=150,
            name="Detail Local Negation",
            current_company="Seed",
            current_title="AI Infra 工程师",
            education="非985本科",
            work_years=6,
            age=30,
            skill_tags=("GPU",),
        ),
        strategy,
        detail,
        mode="list",
    )
    detailed_result = score_candidate(
        Candidate(
            id=150,
            name="Detail Local Negation",
            current_company="Seed",
            current_title="AI Infra 工程师",
            education="非985本科",
            work_years=6,
            age=30,
            skill_tags=("GPU",),
        ),
        strategy,
        detail,
        mode="detailed",
    )

    assert list_result["grade"] == "淘汰"
    assert "school_not_priority" in list_result["risk_flags"]
    assert detailed_result["grade"] != "淘汰"
    assert "school_not_priority" not in detailed_result["risk_flags"]


def test_score_candidate_negated_top500_and_named_school_are_rejected():
    strategy = load_strategy(Path("configs/maimai-ai-infra-search-strategy.json"))

    negated_qs = score_candidate(
        Candidate(
            id=110,
            name="Negated QS",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="非QS Top500 university",
            work_years=6,
            age=30,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        None,
        mode="list",
    )
    negated_not = score_candidate(
        Candidate(
            id=111,
            name="Not QS",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="not QS Top500 university",
            work_years=6,
            age=30,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        None,
        mode="list",
    )
    negated_c9 = score_candidate(
        Candidate(
            id=112,
            name="Negated C9",
            current_company="Seed",
            current_title="AI Infra 宸ョ▼甯?",
            education="非清华大学 普通本科",
            work_years=6,
            age=30,
            skill_tags=("GPU", "vLLM"),
        ),
        strategy,
        None,
        mode="list",
    )

    for result in (negated_qs, negated_not, negated_c9):
        assert result["grade"] == "淘汰"
        assert "school_not_priority" in result["risk_flags"]
