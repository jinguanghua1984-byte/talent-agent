from pathlib import Path


SKILL = Path("skills/jd-talent-delivery/SKILL.md")


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_frontmatter_and_semantic_triggers() -> None:
    text = _text()

    assert "name: jd-talent-delivery" in text
    assert "description: Use when" in text
    for token in [
        "按 JD 做人才库推荐",
        "基于这个 JD 生成岗位画像和 Top30 人才推荐",
        "把 JD 推荐结果推送到飞书 JD需求交付",
        "用本地人才库匹配这个岗位",
        "生成岗位画像、人才推荐报告和外联表",
    ]:
        assert token in text


def test_skill_declares_output_root_and_artifacts() -> None:
    text = _text()

    for token in [
        "data/output/<jd-slug>-<YYYY-MM-DD>/",
        "source/jd.md",
        "profile/role-deep-dive.md",
        "profile/role-profile.json",
        "scoring/scorecard.json",
        "scoring/coarse-screen.json",
        "scoring/detailed-rank.json",
        "reports/talent-recommendation.md",
        "reports/outreach-queue.csv",
        "feishu/publish-manifest.json",
    ]:
        assert token in text


def test_skill_declares_defaults_and_handoff() -> None:
    text = _text()

    for token in [
        "top_n=30",
        "publish_feishu=true",
        "wiki_space_id=7642607697183001542",
        "agents/workflows/jd-talent-delivery/AGENT.md",
        "hr-talent",
        "docs/business-requirements/2026-05-21-llm-inference-role-deep-dive.md",
    ]:
        assert token in text


def test_skill_requires_scorecard_consistency_and_read_only_db() -> None:
    text = _text()

    for token in [
        "粗筛和精排必须引用同一个 `scorecard.json`",
        "data/talent.db 默认只读",
        "不写 `match_scores`",
        "不发起新的脉脉搜索",
        "不上传 SQLite DB、sync zip、raw search、raw detail、raw capture",
    ]:
        assert token in text


def test_skill_feishu_publish_boundary() -> None:
    text = _text()

    for token in [
        "默认真实发布",
        "lark-cli doctor",
        "lark-cli auth status",
        "drive +import --type docx",
        "drive +import --type sheet",
        "wiki +move",
        "不依赖 `sheets +append --file`",
    ]:
        assert token in text
