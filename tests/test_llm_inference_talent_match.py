import json
from pathlib import Path

from scripts import llm_inference_talent_match as matcher
from scripts.talent_models import Candidate, CandidateDetail, PageResult


def _bundle(
    *,
    candidate: Candidate,
    detail: CandidateDetail | None = None,
) -> matcher.CandidateBundle:
    return matcher.CandidateBundle(candidate=candidate, detail=detail, sources=[])


def test_score_bundle_recommends_deep_llm_inference_profile() -> None:
    candidate = Candidate(
        id=1,
        name="强推候选人",
        current_company="字节跳动",
        current_title="大模型推理引擎工程师",
        education="上海交通大学 硕士",
        work_years=5,
        skill_tags=("vLLM", "SGLang", "GPU"),
    )
    detail = CandidateDetail(
        candidate_id=1,
        work_experience=[
            {
                "company": "字节跳动",
                "title": "大模型推理引擎工程师",
                "description": (
                    "负责 vLLM scheduler、continuous batching、KV Cache、"
                    "Prefill Decode、CUDA Graph、FP8 量化、TTFT TPOT、"
                    "高并发 SLA P99 监控和 GPU 利用率优化。"
                ),
            }
        ],
        education_experience=[{"school": "上海交通大学", "description": "硕士 985"}],
    )

    result = matcher.score_bundle(_bundle(candidate=candidate, detail=detail))

    assert result["recommendation_label"] == "强推荐"
    assert result["score"] >= 82
    assert result["dimensions"]["framework_depth"] >= 12
    assert result["dimensions"]["performance_cost"] >= 8


def test_score_bundle_flags_application_only_candidate() -> None:
    candidate = Candidate(
        id=2,
        name="应用层候选人",
        current_company="普通应用公司",
        current_title="大模型应用开发工程师",
        education="本科",
        work_years=4,
        skill_tags=("RAG", "Agent", "Prompt", "MCP"),
    )
    detail = CandidateDetail(
        candidate_id=2,
        project_experience=[
            {
                "name": "智能体平台",
                "description": "基于 Dify、RAG、Agent、Prompt 和 MCP 搭建业务应用。没有推理框架二开经验。",
            }
        ],
    )

    result = matcher.score_bundle(_bundle(candidate=candidate, detail=detail))

    assert result["recommendation_label"] not in {"强推荐", "推荐"}
    assert "偏应用层/Agent/RAG，推理系统深度不足" in result["risks"]
    assert "推理框架二开证据不足" in result["gaps"]


def test_company_score_uses_company_fields_not_model_mentions() -> None:
    candidate = Candidate(
        id=5,
        name="模型部署候选人",
        current_company="普通科技公司",
        current_title="推理服务工程师",
        education="本科",
        work_years=5,
        skill_tags=("vLLM",),
    )
    detail = CandidateDetail(
        candidate_id=5,
        work_experience=[
            {
                "company": "普通科技公司",
                "title": "推理服务工程师",
                "description": "负责 DeepSeek 和 Qwen 的 vLLM 部署、KV Cache 调优和线上 SLA。",
            }
        ],
    )

    result = matcher.score_bundle(_bundle(candidate=candidate, detail=detail))

    assert result["dimensions"]["company"] == 0
    assert result["evidence"]["company_tier"] == "非目标公司"


def test_markdown_table_escapes_pipe_characters() -> None:
    ranked = [
        {
            "candidate_id": 6,
            "name": "Pipe User",
            "score": 80,
            "recommendation_label": "推荐",
            "current_company": "公司A|公司B",
            "current_title": "AI技术专家 | 大模型解决方案架构师",
            "city": "上海",
            "work_years": 6,
            "education": "本科",
            "hunting_status": "",
            "data_level": "detailed",
            "dimensions": {},
            "evidence": {},
            "highlights": ["大厂AI Infra背景：公司A|公司B"],
            "gaps": [],
            "risks": [],
            "work_experience": [],
            "education_experience": [],
            "project_experience": [],
            "source_profiles": [],
        }
    ]

    markdown = matcher.render_markdown(ranked, Path("profile.md"), top_n=1, all_count=1)

    assert "公司A\\|公司B" in markdown
    assert "AI技术专家 \\| 大模型解决方案架构师" in markdown


def test_score_bundle_marks_years_over_target_as_risk() -> None:
    candidate = Candidate(
        id=3,
        name="超年限候选人",
        current_company="百度",
        current_title="推理框架架构师",
        education="清华大学 硕士",
        work_years=12,
        skill_tags=("vLLM", "TensorRT-LLM", "CUDA"),
    )
    detail = CandidateDetail(
        candidate_id=3,
        work_experience=[
            {
                "company": "百度",
                "title": "推理框架架构师",
                "description": "深度参与 vLLM、TensorRT-LLM、KV Cache、Prefill Decode、量化、吞吐和 SLA 优化。",
            }
        ],
    )

    result = matcher.score_bundle(_bundle(candidate=candidate, detail=detail))

    assert "年限超过1-7年目标" in result["risks"]
    assert result["evidence"]["years_label"] == "超过目标年限"
    assert result["recommendation_label"] == "观察"


def test_run_exports_read_only_report_without_match_score_write(
    tmp_path: Path, monkeypatch
) -> None:
    profile = tmp_path / "profile.md"
    profile.write_text("# profile\n", encoding="utf-8")
    out_md = tmp_path / "match.md"
    out_json = tmp_path / "match.json"

    candidate = Candidate(
        id=4,
        name="只读候选人",
        current_company="MiniMax",
        current_title="LLM serving 工程师",
        education="浙江大学 硕士",
        work_years=6,
        skill_tags=("vLLM", "KV Cache"),
    )

    class FakeTalentDB:
        def __init__(self, db_path: str | Path) -> None:
            self.db_path = db_path

        def search(self, **kwargs) -> PageResult:
            return PageResult(items=[candidate], total=1, page=1, page_size=1)

        def get_detail(self, candidate_id: int) -> CandidateDetail:
            return CandidateDetail(
                candidate_id=candidate_id,
                work_experience=[
                    {
                        "company": "MiniMax",
                        "title": "LLM serving 工程师",
                        "description": "vLLM KV Cache Prefill Decode 量化 高并发 SLA 监控",
                    }
                ],
            )

        def get_sources(self, candidate_id: int) -> list:
            return []

        def save_match_score(self, *args, **kwargs) -> None:
            raise AssertionError("run() must not write match_scores")

        def close(self) -> None:
            pass

    monkeypatch.setattr(matcher, "TalentDB", FakeTalentDB)

    result = matcher.run(
        db_path=tmp_path / "talent.db",
        profile_path=profile,
        out_md=out_md,
        out_json=out_json,
        limit=20,
        top_n=5,
    )

    data = json.loads(out_json.read_text(encoding="utf-8-sig"))
    assert result["scanned"] == 1
    assert data["read_only"] is True
    assert data["summary"]["total_scored"] == 1
    assert out_md.read_text(encoding="utf-8-sig").startswith("# LLM 大模型推理岗位人才库推荐报告")
