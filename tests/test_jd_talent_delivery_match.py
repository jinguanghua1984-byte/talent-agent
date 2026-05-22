import csv
import json
import sqlite3
from pathlib import Path

import pytest

from scripts import jd_talent_delivery_match as match
from scripts.talent_models import Candidate, CandidateDetail, PageResult


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
    assert (out_dir / "reports" / "talent-recommendation.md").exists()
    assert (out_dir / "reports" / "talent-recommendation.json").exists()
    assert (out_dir / "reports" / "outreach-queue.csv").exists()
    assert (out_dir / "reports" / "outreach-queue.md").exists()

    with (
        out_dir / "reports" / "outreach-queue.csv"
    ).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["candidate_id"] == "101"
    assert rows[0]["priority"] in {"P0", "P1"}
    assert rows[0]["grade"]
    assert rows[0]["profile_url"].startswith("https://maimai.cn/profile/detail")
    assert result["ranked"][0]["grade"]

    report = (out_dir / "reports" / "talent-recommendation.md").read_text(
        encoding="utf-8-sig"
    )
    assert "strong_recommend" in report
    assert "82" in report


def test_coarse_and_detailed_share_dimension_ids() -> None:
    scorecard = _scorecard()
    bundle = match.CandidateBundle(candidate=_candidate(), detail=None, sources=[])

    coarse = match.score_candidate(bundle, scorecard, mode="coarse")
    detailed = match.score_candidate(bundle, scorecard, mode="detailed")

    assert set(coarse["dimensions"]) == set(detailed["dimensions"])


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
