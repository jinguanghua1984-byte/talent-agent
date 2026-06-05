import csv
import json
import sqlite3
from pathlib import Path

import pytest

from scripts import jd_talent_delivery_match as match
from scripts.talent_models import Candidate, CandidateDetail, PageResult, SourceProfile


def _scorecard() -> dict:
    return {
        "schema": "jd_talent_delivery_scorecard_v1",
        "role_id": "demo",
        "version": "v1",
        "target_role": "大模型推理系统工程师",
        "dimensions": [
            {"id": "company_context", "label": "公司与业务上下文", "weight": 16},
            {"id": "title_focus", "label": "岗位方向", "weight": 16},
            {"id": "must_have", "label": "核心能力", "weight": 28},
            {"id": "nice_to_have", "label": "加分能力", "weight": 14},
            {"id": "seniority", "label": "资历匹配", "weight": 10},
            {"id": "education", "label": "教育背景", "weight": 8},
            {"id": "risk", "label": "风险扣分", "weight": 8},
        ],
        "terms": {
            "must_have": ["vLLM", "KV Cache", "Prefill", "Decode"],
            "nice_to_have": ["SGLang", "CUDA Graph", "量化"],
            "title_aliases": ["推理框架工程师", "模型服务工程师"],
            "exclusion_terms": ["销售"],
            "risk_rules": ["求职状态偏低"],
        },
        "company_pools": {"目标公司": ["字节跳动", "MiniMax"]},
        "label_thresholds": {"strong_recommend": 82, "recommend": 72, "observe": 60},
    }


def _broad_scorecard() -> dict:
    scorecard = _scorecard()
    scorecard["terms"]["must_have"] = [
        "大模型",
        "后训练",
        "数据策略",
        "数据质量",
        "数据标注",
        "数据合成",
        "数据交付",
        "质检",
        "SFT",
        "RLHF",
        "评测",
        "人机协同",
        "供应商管理",
        "语料",
        "多模态",
        "产品化",
    ]
    scorecard["terms"]["nice_to_have"] = ["飞书", "指标体系", "预算管理", "专家评审"]
    scorecard["terms"]["title_aliases"] = ["数据产品负责人", "数据策略负责人"]
    scorecard["company_pools"] = {"目标公司": ["腾讯混元"]}
    scorecard["target_role"] = "大模型数据产品负责人"
    return scorecard


def _candidate() -> Candidate:
    return Candidate(
        id=101,
        name="候选人A",
        current_company="字节跳动",
        current_title="推理框架工程师",
        education="上海交通大学 硕士",
        work_years=5,
        skill_tags=("vLLM", "KV Cache"),
        hunting_status="在职观望",
    )


def _candidate_with_work_years(work_years: int | None) -> Candidate:
    candidate = _candidate()
    return Candidate(
        id=candidate.id,
        name=candidate.name,
        current_company=candidate.current_company,
        current_title=candidate.current_title,
        education=candidate.education,
        work_years=work_years,
        skill_tags=candidate.skill_tags,
        hunting_status=candidate.hunting_status,
    )


def _data_product_candidate() -> Candidate:
    return Candidate(
        id=202,
        name="候选人B",
        current_company="腾讯",
        current_title="数据产品负责人",
        education="复旦大学 本科",
        work_years=8,
        skill_tags=("大模型", "数据质量", "数据标注", "后训练"),
        hunting_status="在职观望",
    )


def _sparse_product_candidate() -> Candidate:
    return Candidate(
        id=303,
        name="候选人C",
        current_company="腾讯",
        current_title="数据产品负责人",
        education="复旦大学 本科",
        work_years=8,
        skill_tags=("大模型",),
        hunting_status="在职观望",
    )


class FakeTalentDB:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path

    def search(self, **kwargs) -> PageResult:
        return PageResult(items=[_candidate()], total=1, page=1, page_size=1)

    def get_detail(self, candidate_id: int) -> CandidateDetail:
        return CandidateDetail(
            candidate_id=candidate_id,
            work_experience=[
                {
                    "company": "字节跳动",
                    "title": "推理框架工程师",
                    "description": "负责 vLLM KV Cache Prefill Decode SGLang 量化和 CUDA Graph 优化。",
                }
            ],
            education_experience=[{"school": "上海交通大学", "description": "硕士"}],
        )

    def get_sources(self, candidate_id: int) -> list:
        return [
            type(
                "Source",
                (),
                {
                    "platform": "maimai",
                    "platform_id": "p101",
                    "profile_url": "https://maimai.cn/profile/detail?dstu=p101",
                    "fetched_at": "2026-05-23",
                },
            )()
        ]

    def save_match_score(self, *args, **kwargs) -> None:
        raise AssertionError("matching must be read-only")

    def close(self) -> None:
        pass


class SparseCoarseTalentDB(FakeTalentDB):
    def search(self, **kwargs) -> PageResult:
        return PageResult(items=[_sparse_product_candidate()], total=1, page=1, page_size=1)

    def get_detail(self, candidate_id: int) -> CandidateDetail:
        return CandidateDetail(
            candidate_id=candidate_id,
            work_experience=[
                {
                    "company": "腾讯",
                    "title": "数据产品负责人",
                    "description": "负责混元大模型后训练数据策略、数据标注、数据质量、SFT 和交付体系。",
                }
            ],
            education_experience=[{"school": "复旦大学", "description": "本科"}],
        )


class TrackingUrlTalentDB(FakeTalentDB):
    def get_sources(self, candidate_id: int) -> list:
        return [
            type(
                "Source",
                (),
                {
                    "platform": "maimai",
                    "platform_id": "p101",
                    "profile_url": (
                        "https://maimai.cn/profile/detail?dstu=p101&"
                        "trackable_token=secret-token&show_tip=0"
                    ),
                    "fetched_at": "2026-05-23",
                },
            )()
        ]


def test_run_match_outputs_reports_and_outreach(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(match, "TalentDB", FakeTalentDB)
    scorecard_path = tmp_path / "scorecard.json"
    scorecard_path.write_text(
        json.dumps(_scorecard(), ensure_ascii=False), encoding="utf-8"
    )
    out_dir = tmp_path / "delivery"

    result = match.run_match(
        db_path=tmp_path / "talent.db",
        scorecard_path=scorecard_path,
        out_dir=out_dir,
        top_n=1,
        limit=10,
    )

    assert result["read_only"] is True
    assert result["summary"]["total_scored"] == 1
    assert result["top_n"] == 1
    assert (out_dir / "scoring" / "coarse-screen.json").exists()
    assert (out_dir / "scoring" / "detailed-rank.json").exists()
    assert (out_dir / "scoring" / "coarse-screen.md").exists()
    assert (out_dir / "scoring" / "detailed-rank.md").exists()
    assert (out_dir / "reports" / "talent-recommendation.md").exists()
    assert (out_dir / "reports" / "talent-recommendation.json").exists()
    assert (out_dir / "reports" / "outreach-queue.csv").exists()
    assert (out_dir / "reports" / "outreach-queue.md").exists()

    with (
        out_dir / "reports" / "outreach-queue.csv"
    ).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_feedback_fields = [
        "feedback_label",
        "feedback_stage",
        "reason_codes",
        "hunter_note",
        "contacted",
        "submitted_to_client",
        "interviewed",
        "offer",
    ]
    for field in expected_feedback_fields:
        assert field in rows[0]
        assert rows[0][field] == ""
    assert rows[0]["candidate_id"] == "101"
    assert rows[0]["priority"] in {"P0", "P1"}
    assert rows[0]["grade"]
    assert rows[0]["profile_url"].startswith("https://maimai.cn/profile/detail")
    assert result["ranked"][0]["grade"]
    assert (out_dir / "reports" / "quality-gates.json").exists()

    report = (out_dir / "reports" / "talent-recommendation.md").read_text(
        encoding="utf-8-sig"
    )
    assert "strong_recommend" in report
    assert "82" in report
    assert "101" in (out_dir / "scoring" / "coarse-screen.md").read_text(encoding="utf-8-sig")
    assert "101" in (out_dir / "scoring" / "detailed-rank.md").read_text(encoding="utf-8-sig")


def test_score_candidate_caps_broad_must_have_dilution_and_expands_company_aliases() -> None:
    scorecard = _broad_scorecard()
    detail = CandidateDetail(
        candidate_id=202,
        work_experience=[
            {
                "company": "腾讯",
                "title": "数据产品负责人",
                "description": "负责混元大模型后训练数据策略、数据标注、数据质量和交付体系。",
            }
        ],
    )
    bundle = match.CandidateBundle(candidate=_data_product_candidate(), detail=detail, sources=[])

    scored = match.score_candidate(bundle, scorecard, mode="detailed")

    assert scored["recommendation_label"] in {"强推荐", "推荐"}
    assert scored["dimensions"]["must_have"] >= 20
    assert scored["dimensions"]["company_context"] == 16
    assert scored["evidence"]["title_level"] == "precision"
    assert "腾讯" in scored["evidence"]["company_matches"]
    assert scored["evidence"]["key_evidence"]


def test_score_candidate_recommends_precise_title_with_four_broad_must_have_hits() -> None:
    scorecard = _broad_scorecard()
    detail = CandidateDetail(
        candidate_id=202,
        work_experience=[
            {
                "company": "腾讯",
                "title": "数据产品负责人",
                "description": "负责混元大模型数据策略、数据标注和数据质量体系。",
            }
        ],
    )
    candidate = _data_product_candidate()
    candidate = Candidate(
        id=candidate.id,
        name=candidate.name,
        current_company=candidate.current_company,
        current_title=candidate.current_title,
        education=candidate.education,
        work_years=candidate.work_years,
        skill_tags=("大模型",),
        hunting_status=candidate.hunting_status,
    )
    bundle = match.CandidateBundle(candidate=candidate, detail=detail, sources=[])

    scored = match.score_candidate(bundle, scorecard, mode="detailed")

    assert scored["matched_terms_by_dimension"]["must_have"] == [
        "大模型",
        "数据策略",
        "数据质量",
        "数据标注",
    ]
    assert scored["recommendation_label"] in {"强推荐", "推荐"}


def test_run_match_sends_sparse_but_relevant_coarse_candidate_to_detailed_rank(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(match, "TalentDB", SparseCoarseTalentDB)
    scorecard_path = tmp_path / "scorecard.json"
    scorecard_path.write_text(
        json.dumps(_broad_scorecard(), ensure_ascii=False), encoding="utf-8"
    )
    out_dir = tmp_path / "delivery"

    result = match.run_match(
        db_path=tmp_path / "talent.db",
        scorecard_path=scorecard_path,
        out_dir=out_dir,
        top_n=1,
        limit=10,
    )

    assert result["summary"]["total_scored"] == 1
    assert result["ranked"][0]["candidate_id"] == 303
    assert result["ranked"][0]["recommendation_label"] in {"强推荐", "推荐"}


def test_outreach_url_retains_profile_token_and_angle_keeps_company_and_title(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(match, "TalentDB", TrackingUrlTalentDB)
    scorecard_path = tmp_path / "scorecard.json"
    scorecard_path.write_text(
        json.dumps(_scorecard(), ensure_ascii=False), encoding="utf-8"
    )
    out_dir = tmp_path / "delivery"

    match.run_match(
        db_path=tmp_path / "talent.db",
        scorecard_path=scorecard_path,
        out_dir=out_dir,
        top_n=1,
        limit=10,
    )

    with (out_dir / "reports" / "outreach-queue.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["profile_url"] == (
        "https://maimai.cn/profile/detail?dstu=p101&trackable_token=secret-token"
    )
    assert result_url(out_dir / "reports" / "talent-recommendation.json") == rows[0]["profile_url"]
    assert "show_tip" not in rows[0]["profile_url"]
    assert "字节跳动" in rows[0]["suggested_outreach_angle"]
    assert "推理框架工程师" in rows[0]["suggested_outreach_angle"]


def test_source_url_prefers_openable_maimai_profile_url() -> None:
    candidate = Candidate(
        id=1,
        name="陶壮",
        current_company="华为技术有限公司",
        current_title="大模型推理工程师",
    )
    bundle = match.CandidateBundle(
        candidate=candidate,
        detail=None,
        sources=[
            SourceProfile(
                id=1,
                candidate_id=1,
                platform="boss_app",
                platform_id="boss-001",
                profile_url="boss://candidate/boss-001",
            ),
            SourceProfile(
                id=2,
                candidate_id=1,
                platform="maimai",
                platform_id="mm-001",
                profile_url=(
                    "https://maimai.cn/profile/detail?dstu=mm-001&"
                    "trackable_token=tok&show_tip=1&utm_source=test"
                ),
            ),
        ],
    )

    assert match._source_url(bundle) == (
        "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok"
    )


def result_url(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data["ranked"][0]["profile_url"]


def test_quality_gate_allows_profile_url_trackable_token(tmp_path: Path) -> None:
    root = tmp_path / "delivery"
    root.mkdir()
    ranked = [
        {
            "candidate_id": 1,
            "name": "候选人1",
            "grade": "A",
            "recommendation_label": "强推荐",
            "score": 91,
            "current_company": "公司",
            "current_title": "职位",
            "profile_url": (
                "https://maimai.cn/profile/detail?dstu=1&trackable_token=secret-token"
            ),
            "evidence": {"key_evidence": ["评分证据：数据质量"]},
        }
    ]
    (root / "reports").mkdir()
    (root / "reports" / "outreach-queue.csv").write_text(
        "candidate_id,name,company,title,score,grade,suggested_outreach_angle,profile_url\n"
        "1,候选人1,公司,职位,91,A,围绕 公司 的 职位 经历确认岗位匹配深度.,"
        "https://maimai.cn/profile/detail?dstu=1&trackable_token=secret-token\n",
        encoding="utf-8-sig",
    )

    quality = match.validate_delivery_outputs(root, ranked=ranked, top_n=1)

    assert quality["status"] == "passed"
    assert quality["critical_issues"] == []


def test_quality_gate_rejects_trackable_token_outside_profile_url(tmp_path: Path) -> None:
    root = tmp_path / "delivery"
    root.mkdir()
    ranked = [
        {
            "candidate_id": 1,
            "name": "候选人1",
            "grade": "A",
            "recommendation_label": "强推荐",
            "score": 91,
            "current_company": "公司",
            "current_title": "职位",
            "profile_url": (
                "https://maimai.cn/profile/detail?dstu=1&trackable_token=secret-token"
            ),
            "evidence": {"key_evidence": ["评分证据：数据质量"]},
        }
    ]
    (root / "reports").mkdir()
    (root / "reports" / "outreach-queue.csv").write_text(
        "candidate_id,name,company,title,score,grade,suggested_outreach_angle,profile_url,note\n"
        "1,候选人1,公司,职位,91,A,围绕 公司 的 职位 经历确认岗位匹配深度.,"
        "https://maimai.cn/profile/detail?dstu=1&trackable_token=secret-token,"
        "trackable_token=secret-token\n",
        encoding="utf-8-sig",
    )

    quality = match.validate_delivery_outputs(root, ranked=ranked, top_n=1)

    assert quality["status"] == "blocked"
    assert any("trackable_token" in issue for issue in quality["critical_issues"])


def test_validate_delivery_outputs_blocks_all_c_topn(tmp_path: Path) -> None:
    root = tmp_path / "delivery"
    root.mkdir()
    ranked = [
        {
            "candidate_id": index,
            "name": f"候选人{index}",
            "grade": "C",
            "recommendation_label": "观察",
            "score": 61,
            "current_company": "公司",
            "current_title": "职位",
            "profile_url": f"https://maimai.cn/profile/detail?dstu={index}",
            "evidence": {"key_evidence": ["评分证据：数据质量"]},
        }
        for index in range(1, 4)
    ]
    (root / "reports").mkdir()
    (root / "reports" / "outreach-queue.csv").write_text(
        "candidate_id,name,company,title,suggested_outreach_angle,profile_url\n"
        "1,候选人1,公司,职位,围绕 公司 的 职位 经历确认岗位匹配深度。,"
        "https://maimai.cn/profile/detail?dstu=1\n",
        encoding="utf-8-sig",
    )

    quality = match.validate_delivery_outputs(root, ranked=ranked, top_n=3)

    assert "top_n_all_low_confidence" in quality["critical_issues"]
    assert quality["status"] == "blocked"


def test_coarse_and_detailed_share_dimension_ids() -> None:
    scorecard = _scorecard()
    bundle = match.CandidateBundle(candidate=_candidate(), detail=None, sources=[])

    coarse = match.score_candidate(bundle, scorecard, mode="coarse")
    detailed = match.score_candidate(bundle, scorecard, mode="detailed")

    assert set(coarse["dimensions"]) == set(detailed["dimensions"])


def test_young_high_potential_policy_prefers_five_year_candidates() -> None:
    scorecard = _scorecard()
    for dimension in scorecard["dimensions"]:
        if dimension["id"] == "seniority":
            dimension["weight"] = 18
        elif dimension["id"] == "risk":
            dimension["weight"] = 0
    scorecard["seniority_policy"] = {
        "mode": "young_high_potential",
        "preferred_max_work_years": 5,
        "soft_max_work_years": 8,
    }
    detail = CandidateDetail(
        candidate_id=101,
        work_experience=[
            {
                "company": "字节跳动",
                "title": "推理框架工程师",
                "description": "负责 vLLM KV Cache Prefill Decode SGLang 量化和 CUDA Graph 优化。",
            }
        ],
    )

    young = match.score_candidate(
        match.CandidateBundle(
            candidate=_candidate_with_work_years(5),
            detail=detail,
            sources=[],
        ),
        scorecard,
        mode="detailed",
    )
    above_preferred = match.score_candidate(
        match.CandidateBundle(
            candidate=_candidate_with_work_years(7),
            detail=detail,
            sources=[],
        ),
        scorecard,
        mode="detailed",
    )
    senior = match.score_candidate(
        match.CandidateBundle(
            candidate=_candidate_with_work_years(10),
            detail=detail,
            sources=[],
        ),
        scorecard,
        mode="detailed",
    )

    assert young["dimensions"]["seniority"] == 18
    assert above_preferred["dimensions"]["seniority"] == 9
    assert senior["dimensions"]["seniority"] == 0
    assert "seniority_above_preferred:7>5" in above_preferred["risk_flags"]
    assert "seniority_above_soft_max:10>8" in senior["risk_flags"]
    assert young["score"] > above_preferred["score"] > senior["score"]


def test_education_score_recognizes_c9_schools() -> None:
    assert match._education_score("南京大学 金融学 本科", 8) == 8
    assert match._education_score("中国科学技术大学 硕士", 8) == 8
    assert match._education_score("哈尔滨工业大学 本科", 8) == 8
    assert match._education_score("西安交通大学 本科", 8) == 8


def test_load_bundles_uses_talentdb_read_methods_only(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[tuple[str, object]] = []

    class TrackingTalentDB:
        def __init__(self, db_path: str | Path) -> None:
            calls.append(("init", Path(db_path).name))

        def search(self, **kwargs) -> PageResult:
            calls.append(("search", kwargs))
            assert kwargs["page"] == 1
            assert kwargs["page_size"] == 3
            assert isinstance(kwargs["sort"], match.SortSpec)
            return PageResult(items=[_candidate()], total=1, page=1, page_size=3)

        def get_detail(self, candidate_id: int) -> CandidateDetail:
            calls.append(("get_detail", candidate_id))
            return CandidateDetail(candidate_id=candidate_id)

        def get_sources(self, candidate_id: int) -> list:
            calls.append(("get_sources", candidate_id))
            return []

        def close(self) -> None:
            calls.append(("close", None))

        def save_match_score(self, *args, **kwargs) -> None:
            raise AssertionError("matching must not call TalentDB write APIs")

        def update_candidate(self, *args, **kwargs) -> None:
            raise AssertionError("matching must not call TalentDB write APIs")

    monkeypatch.setattr(match, "TalentDB", TrackingTalentDB)

    bundles = match._load_bundles(tmp_path / "talent.db", limit=3)

    assert [bundle.candidate.id for bundle in bundles] == [101]
    assert [name for name, _ in calls] == [
        "init",
        "search",
        "get_detail",
        "get_sources",
        "close",
    ]


def test_load_bundles_real_talentdb_uses_temporary_readonly_copy(
    tmp_path: Path, monkeypatch
) -> None:
    source_db = tmp_path / "source.db"
    copy_db = tmp_path / "copy.db"
    events: list[tuple[str, Path | int]] = []

    class FakeCopyContext:
        def __enter__(self) -> Path:
            events.append(("copy_enter", copy_db))
            return copy_db

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append(("copy_exit", copy_db))

    def fake_copy(db_path: str | Path) -> FakeCopyContext:
        events.append(("copy_source", Path(db_path)))
        return FakeCopyContext()

    def fake_load(db_path: str | Path, limit: int) -> list[match.CandidateBundle]:
        events.append(("load", Path(db_path)))
        events.append(("limit", limit))
        return [match.CandidateBundle(candidate=_candidate(), detail=None, sources=[])]

    monkeypatch.setattr(match, "TalentDB", match._REAL_TALENT_DB)
    monkeypatch.setattr(match, "_temporary_readonly_db_copy", fake_copy)
    monkeypatch.setattr(match, "_load_bundles_from_talentdb", fake_load)

    bundles = match._load_bundles(source_db, limit=7)

    assert [bundle.candidate.id for bundle in bundles] == [101]
    assert events == [
        ("copy_source", source_db),
        ("copy_enter", copy_db),
        ("load", copy_db),
        ("limit", 7),
        ("copy_exit", copy_db),
    ]


def test_temporary_readonly_db_copy_closes_handles_before_cleanup(
    tmp_path: Path,
) -> None:
    source_db = tmp_path / "source.db"
    source_conn = sqlite3.connect(source_db)
    try:
        source_conn.execute("CREATE TABLE demo (value TEXT NOT NULL)")
        source_conn.execute("INSERT INTO demo (value) VALUES ('ok')")
        source_conn.commit()
    finally:
        source_conn.close()

    yielded_copy: Path | None = None
    temp_dir: Path | None = None
    with match._temporary_readonly_db_copy(source_db) as copy_path:
        yielded_copy = copy_path
        temp_dir = copy_path.parent
        assert copy_path.exists()
        read_conn = sqlite3.connect(copy_path)
        try:
            assert read_conn.execute("SELECT value FROM demo").fetchone()[0] == "ok"
        finally:
            read_conn.close()

    assert yielded_copy is not None
    assert temp_dir is not None
    assert not temp_dir.exists()


def test_score_candidate_rejects_bad_scorecard_weight() -> None:
    scorecard = _scorecard()
    scorecard["dimensions"][0]["weight"] = []
    bundle = match.CandidateBundle(candidate=_candidate(), detail=None, sources=[])

    with pytest.raises(ValueError, match="dimension invalid weight"):
        match.score_candidate(bundle, scorecard, mode="coarse")


def test_score_candidate_rejects_bad_label_threshold() -> None:
    scorecard = _scorecard()
    scorecard["label_thresholds"]["strong_recommend"] = []
    bundle = match.CandidateBundle(candidate=_candidate(), detail=None, sources=[])

    with pytest.raises(ValueError, match="invalid label threshold.*strong_recommend"):
        match.score_candidate(bundle, scorecard, mode="coarse")


def test_run_match_rejects_non_positive_top_n_and_limit(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(match, "TalentDB", FakeTalentDB)
    scorecard_path = tmp_path / "scorecard.json"
    scorecard_path.write_text(
        json.dumps(_scorecard(), ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="top_n must be positive"):
        match.run_match(
            db_path=tmp_path / "talent.db",
            scorecard_path=scorecard_path,
            out_dir=tmp_path / "out-top",
            top_n=0,
            limit=10,
        )

    with pytest.raises(ValueError, match="limit must be positive"):
        match.run_match(
            db_path=tmp_path / "talent.db",
            scorecard_path=scorecard_path,
            out_dir=tmp_path / "out-limit",
            top_n=1,
            limit=0,
        )
