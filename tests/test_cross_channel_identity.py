from scripts.cross_channel_identity import (
    BossMaimaiTarget,
    MaimaiSearchHit,
    build_query_plan,
    decide_match,
    score_hit,
)


def _target() -> BossMaimaiTarget:
    return BossMaimaiTarget(
        target_id="target-1",
        candidate_key="boss-app:1",
        real_name="张三",
        current_company="字节跳动",
        current_title="高级 AI 产品负责人",
        city="北京",
        education="硕士",
        recent_companies=("腾讯",),
        schools=("清华大学",),
    )


def test_query_plan_orders_high_precision_before_fallback() -> None:
    plan = build_query_plan(_target())

    assert [item.level for item in plan] == [
        "name_company_title",
        "name_company_title_core",
        "name_recent_company_title",
        "name_school_title_core",
        "name_company_fallback",
    ]
    assert plan[0].text == "张三 字节跳动 高级 AI 产品负责人"
    assert plan[1].text == "张三 字节跳动 AI 产品负责人"
    assert plan[-1].text == "张三 字节跳动"
    assert [item.allow_auto_bind for item in plan] == [True, True, True, True, False]
    assert plan[-1].to_dict() == {
        "level": "name_company_fallback",
        "text": "张三 字节跳动",
        "allow_auto_bind": False,
    }


def test_build_query_plan_accepts_mapping_dict() -> None:
    plan = build_query_plan(
        {
            "target_id": "target-1",
            "candidate_key": "boss-app:1",
            "real_name": "李四",
            "current_company": "腾讯",
            "current_title": "资深后端工程师",
            "recent_companies": ["百度"],
            "schools": ["浙江大学"],
        }
    )

    assert plan[0].text == "李四 腾讯 资深后端工程师"
    assert plan[2].text == "李四 百度 后端工程师"


def test_strong_high_precision_hit_auto_binds_with_high_score() -> None:
    target = _target()
    hit = MaimaiSearchHit(
        platform_id="maimai-1",
        name="张三",
        company="字节跳动",
        title="AI 产品负责人",
        city="北京",
        education="硕士",
        schools=("清华大学",),
        profile_url="https://maimai.cn/profile/detail?dstu=maimai-1",
    )

    decision = decide_match(target, [hit], "name_company_title_core", "张三 字节跳动 AI 产品负责人")

    assert decision.match_status == "auto_bound"
    assert decision.confidence >= 95
    assert decision.target_platform_id == "maimai-1"
    assert decision.to_dict()["hit"]["platform_id"] == "maimai-1"


def test_name_company_fallback_never_auto_binds() -> None:
    target = _target()
    hit = MaimaiSearchHit(
        platform_id="maimai-1",
        name="张三",
        company="字节跳动",
        title="AI 产品负责人",
        city="北京",
        education="硕士",
        schools=("清华大学",),
    )

    decision = decide_match(target, [hit], "name_company_fallback", "张三 字节跳动")

    assert decision.match_status == "pending_confirmation"
    assert decision.confidence >= 95
    assert decision.decision_reason == "fallback_query_requires_confirmation"


def test_many_results_or_close_second_goes_pending() -> None:
    target = _target()
    best = MaimaiSearchHit(platform_id="best", name="张三", company="字节跳动", title="AI 产品负责人")
    second = MaimaiSearchHit(platform_id="second", name="张三", company="字节跳动", title="产品负责人")

    many_results = decide_match(target, [best], "name_company_title_core", "张三 字节跳动 AI 产品负责人")
    close_second = decide_match(target, [best, second], "name_company_title_core", "张三 字节跳动 AI 产品负责人")

    many_results = decide_match(
        target,
        [best, second, MaimaiSearchHit(platform_id="third", name="张三")],
        "name_company_title_core",
        "张三 字节跳动 AI 产品负责人",
    )

    assert many_results.match_status == "pending_confirmation"
    assert many_results.decision_reason == "too_many_results"
    assert close_second.match_status == "pending_confirmation"
    assert close_second.decision_reason == "second_score_gap_too_small"


def test_low_score_is_not_found() -> None:
    decision = decide_match(
        _target(),
        [MaimaiSearchHit(platform_id="other", name="王五", company="阿里", title="销售")],
        "name_company_title",
        "张三 字节跳动 高级 AI 产品负责人",
    )

    assert decision.match_status == "not_found"
    assert decision.confidence < 70


def test_score_breakdown_exposes_dimensions() -> None:
    score = score_hit(
        _target(),
        MaimaiSearchHit(
            platform_id="maimai-1",
            name="张三",
            company="腾讯",
            title="AI 产品负责人",
            city="北京",
            education="硕士",
            schools=("清华大学",),
        ),
        query_level="name_recent_company_title",
        result_count=2,
        second_score=71,
    )

    assert set(score.breakdown) == {
        "name",
        "company",
        "title",
        "city",
        "education",
        "school",
        "query_level",
        "result_count",
        "second_gap",
    }
    assert score.breakdown["name"] > 0
    assert score.breakdown["company"] > 0
    assert isinstance(score.total, int)
