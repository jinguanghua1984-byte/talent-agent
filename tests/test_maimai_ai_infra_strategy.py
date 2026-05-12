import json
from pathlib import Path

from scripts.maimai_ai_infra_rank import score_candidate
from scripts.maimai_ai_infra_search_plan import generate_batches, load_strategy
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
            education="本科",
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
            education="本科",
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
        ),
    )
    assert generic_with_strong_tech["grade"] == "B"
    assert generic_with_strong_tech["evidence"]["title_level"] == "generic"
    assert "company_not_targeted" not in generic_with_strong_tech["risk_flags"]
