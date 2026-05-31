import json
from pathlib import Path

import pytest

from scripts import boss_app_sourcing


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_slugify_keeps_chinese_and_ascii_word_chars() -> None:
    assert boss_app_sourcing.slugify("大模型 产品 / 北京") == "大模型-产品-北京"
    assert boss_app_sourcing.slugify(" !@# ") == "boss-app-sourcing"


def test_screen_hash_is_stable_and_prefixed() -> None:
    assert boss_app_sourcing.screen_hash("张先生|产品经理") == boss_app_sourcing.screen_hash("张先生|产品经理")
    assert boss_app_sourcing.screen_hash("张先生|产品经理").startswith("sha256:")


def test_build_candidate_key_uses_visible_fields_and_hash() -> None:
    card = {
        "display_name": "张先生",
        "current_company": "字节跳动",
        "current_title": "产品经理",
        "education": "硕士",
        "city": "北京",
        "expected_salary": "40-60K",
        "screenshot_hash": "sha256:abc",
    }
    key = boss_app_sourcing.build_candidate_key(card)
    assert key.startswith("boss-app:")
    assert key == boss_app_sourcing.build_candidate_key(dict(card))


def test_build_candidate_key_uses_list_batch_and_position() -> None:
    card = {
        "display_name": "张先生",
        "current_company": "字节跳动",
        "current_title": "产品经理",
        "education": "硕士",
        "city": "北京",
        "expected_salary": "40-60K",
        "screenshot_hash": "sha256:abc",
        "list_scroll_batch": 1,
        "card_position": 2,
    }

    moved_card = dict(card)
    moved_card["card_position"] = 3

    assert boss_app_sourcing.build_candidate_key(card) != boss_app_sourcing.build_candidate_key(moved_card)


def test_init_campaign_creates_contract_tree(tmp_path: Path) -> None:
    result = boss_app_sourcing.init_campaign(
        campaign_id="boss-app-test",
        filters_text="优先 AI 产品，985 本科以上，年龄 28-35",
        out_base=tmp_path,
        date_text="2026-05-31",
    )

    root = Path(result["campaign_root"])
    assert root == tmp_path / "boss-app-test"
    for relative in [
        "requirements.json",
        "strategy.json",
        "run-policy.json",
        "campaign-manifest.json",
        "raw/list-cards.jsonl",
        "raw/detail-pages.jsonl",
        "raw/communication-pages.jsonl",
        "raw/screen-hashes.jsonl",
        "state/events.jsonl",
        "state/processed-cards.jsonl",
        "state/continuation-plan.json",
        "structured/candidates.jsonl",
        "structured/contact-decisions.jsonl",
        "reports/sourcing-summary.md",
        "reports/sourcing-summary.json",
    ]:
        assert (root / relative).exists(), relative

    policy = read_json(root / "run-policy.json")
    assert policy["execution_surface"] == "boss_app_computer_use"
    assert policy["contact_mode"] == "dry_run"
    assert policy["allow_live_contact_test"] is False
    assert policy["live_contact_test_limit"] == 0

    requirements = read_json(root / "requirements.json")
    assert requirements["filters_text"] == "优先 AI 产品，985 本科以上，年龄 28-35"
    assert requirements["input_mode"] == "post_jd_recommendation_filters"


def test_init_campaign_rejects_existing_campaign_without_overwrite(tmp_path: Path) -> None:
    result = boss_app_sourcing.init_campaign(
        campaign_id="boss-app-existing",
        filters_text="初始筛选条件",
        out_base=tmp_path,
    )
    requirements_path = Path(result["campaign_root"]) / "requirements.json"
    requirements_path.write_text('{"custom": true}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="already exists"):
        boss_app_sourcing.init_campaign(
            campaign_id="boss-app-existing",
            filters_text="新筛选条件",
            out_base=tmp_path,
        )

    assert read_json(requirements_path) == {"custom": True}


def test_init_campaign_rejects_non_empty_directory_without_manifest(tmp_path: Path) -> None:
    root = tmp_path / "boss-app-partial"
    root.mkdir()
    requirements_path = root / "requirements.json"
    requirements_path.write_text('{"custom": true}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="already exists"):
        boss_app_sourcing.init_campaign(
            campaign_id="boss-app-partial",
            filters_text="新筛选条件",
            out_base=tmp_path,
        )

    assert read_json(requirements_path) == {"custom": True}


def test_init_campaign_rejects_live_contact_without_real_contact(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allow_real_contact"):
        boss_app_sourcing.init_campaign(
            campaign_id="bad",
            filters_text="AI 产品",
            out_base=tmp_path,
            allow_live_contact_test=True,
            live_contact_test_limit=1,
        )


def test_init_campaign_allows_live_contact_when_real_contact_enabled(tmp_path: Path) -> None:
    result = boss_app_sourcing.init_campaign(
        campaign_id="boss-app-live-test",
        filters_text="看 AI 产品和 985",
        out_base=tmp_path,
        allow_real_contact=True,
        allow_live_contact_test=True,
        live_contact_test_limit=2,
    )

    policy = read_json(Path(result["campaign_root"]) / "run-policy.json")
    assert policy["allow_real_contact"] is True
    assert policy["allow_live_contact_test"] is True
    assert policy["live_contact_test_limit"] == 2
    assert policy["contact_mode"] == "live_test"


def test_init_campaign_rejects_live_contact_without_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="live_contact_test_limit"):
        boss_app_sourcing.init_campaign(
            campaign_id="bad-limit",
            filters_text="AI 产品",
            out_base=tmp_path,
            allow_real_contact=True,
            allow_live_contact_test=True,
            live_contact_test_limit=0,
        )


def test_init_campaign_rejects_non_integer_live_contact_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="live_contact_test_limit"):
        boss_app_sourcing.init_campaign(
            campaign_id="bad-limit-type",
            filters_text="AI 产品",
            out_base=tmp_path,
            allow_real_contact=True,
            allow_live_contact_test=True,
            live_contact_test_limit="1",  # type: ignore[arg-type]
        )


def test_validate_run_policy_rejects_direct_live_test_without_live_test_flags() -> None:
    with pytest.raises(ValueError, match="allow_real_contact|live_contact_test"):
        boss_app_sourcing.validate_run_policy({"contact_mode": "live_test"})


def test_validate_run_policy_accepts_consistent_direct_live_test_policy() -> None:
    policy = boss_app_sourcing.validate_run_policy({
        "contact_mode": "live_test",
        "allow_real_contact": True,
        "allow_live_contact_test": True,
        "live_contact_test_limit": 1,
    })

    assert policy["contact_mode"] == "live_test"


def test_validate_run_policy_rejects_non_boolean_safety_flags() -> None:
    with pytest.raises(ValueError, match="allow_real_contact"):
        boss_app_sourcing.validate_run_policy({"allow_real_contact": "false"})

    with pytest.raises(ValueError, match="allow_live_contact_test"):
        boss_app_sourcing.validate_run_policy({"allow_live_contact_test": "false"})


def test_validate_run_policy_rejects_non_integer_live_test_limit() -> None:
    with pytest.raises(ValueError, match="live_contact_test_limit"):
        boss_app_sourcing.validate_run_policy({"live_contact_test_limit": "1"})

    with pytest.raises(ValueError, match="live_contact_test_limit"):
        boss_app_sourcing.validate_run_policy({"live_contact_test_limit": True})


def test_init_cli_prints_manifest_json(tmp_path: Path, capsys) -> None:
    exit_code = boss_app_sourcing.main([
        "init",
        "--campaign-id",
        "boss-app-cli",
        "--filters-text",
        "看 AI 产品和 985",
        "--out-base",
        str(tmp_path),
        "--date",
        "2026-05-31",
        "--allow-real-contact",
        "--allow-live-contact-test",
        "--live-contact-test-limit",
        "2",
    ])

    assert exit_code == 0
    manifest = json.loads(capsys.readouterr().out)
    root = Path(manifest["campaign_root"])
    assert root == tmp_path / "boss-app-cli"
    policy = read_json(root / "run-policy.json")
    assert policy["allow_real_contact"] is True
    assert policy["allow_live_contact_test"] is True
    assert policy["live_contact_test_limit"] == 2


def test_jsonl_append_loads_all_rows_without_truncating(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    boss_app_sourcing.append_jsonl(path, {"stage": "init"})
    boss_app_sourcing.append_jsonl(path, {"stage": "preflight"})

    assert boss_app_sourcing.load_jsonl(path) == [
        {"stage": "init"},
        {"stage": "preflight"},
    ]


def test_jsonl_append_repairs_missing_trailing_newline(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"stage": "init"}', encoding="utf-8")

    boss_app_sourcing.append_jsonl(path, {"stage": "preflight"})

    assert boss_app_sourcing.load_jsonl(path) == [
        {"stage": "init"},
        {"stage": "preflight"},
    ]


def test_load_jsonl_reports_malformed_json_with_file_and_line(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="broken\\.jsonl.*line 1.*invalid JSON"):
        boss_app_sourcing.load_jsonl(path)


def test_record_list_card_appends_candidate_and_processed_key(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-card", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    card = {
        "display_name": "张先生",
        "current_company": "某大厂",
        "current_title": "AI 产品经理",
        "education": "硕士",
        "city": "北京",
        "expected_salary": "40-60K",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-1"),
        "list_scroll_batch": 1,
        "card_position": 1,
    }

    candidate = boss_app_sourcing.record_list_card(root, card)

    assert candidate["candidate_key"].startswith("boss-app:")
    assert candidate["display_name"] == "张先生"
    assert candidate["real_name"] is None
    assert candidate["real_name_status"] == "not_available_dry_run"
    candidates = boss_app_sourcing.load_jsonl(root / "structured/candidates.jsonl")
    processed = boss_app_sourcing.load_jsonl(root / "state/processed-cards.jsonl")
    assert candidates[-1]["candidate_key"] == candidate["candidate_key"]
    assert processed[-1]["candidate_key"] == candidate["candidate_key"]


def test_record_detail_update_merges_detail_sections(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-detail", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "李女士",
        "current_title": "产品负责人",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-2"),
    })

    updated = boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {
            "work_experience": [{"company": "A 公司", "title": "产品负责人"}],
            "education_experience": [{"school": "清华大学", "degree": "硕士"}],
        },
        recommendation="contact",
        score=86,
        reasons=["AI 产品经验强"],
    )

    assert updated["screening"]["detail_decision"] == "contact"
    assert updated["screening"]["score"] == 86
    assert updated["detail_sections"]["work_experience"][0]["company"] == "A 公司"


def test_record_contact_dry_run_never_marks_contacted(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-contact", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "王先生",
        "current_title": "算法产品",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-3"),
    })

    decision = boss_app_sourcing.record_contact_decision(
        root,
        candidate["candidate_key"],
        mode="dry_run",
        button_seen=True,
        action_confirmed=False,
    )

    assert decision["would_contact"] is True
    assert decision["contacted"] is False
    assert decision["action_confirmed"] is False
    updated = boss_app_sourcing.latest_candidate(root, candidate["candidate_key"])
    assert updated["contact"]["would_contact"] is True
    assert updated["contact"]["contacted"] is False


def test_live_contact_requires_policy_limit_and_confirmation(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign(
        "boss-live",
        "看 AI 产品",
        out_base=tmp_path,
        allow_real_contact=True,
        allow_live_contact_test=True,
        live_contact_test_limit=1,
    )
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "赵女士",
        "current_title": "AI PM",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-4"),
    })
    boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {"work_experience": [{"company": "A 公司", "title": "AI PM"}]},
        recommendation="contact",
        score=88,
        reasons=["详情匹配"],
    )
    boss_app_sourcing.record_contact_decision(
        root,
        candidate["candidate_key"],
        mode="dry_run",
        button_seen=True,
        action_confirmed=False,
    )

    with pytest.raises(ValueError, match="action confirmation"):
        boss_app_sourcing.record_contact_decision(
            root,
            candidate["candidate_key"],
            mode="live_test",
            button_seen=True,
            action_confirmed=False,
        )

    decision = boss_app_sourcing.record_contact_decision(
        root,
        candidate["candidate_key"],
        mode="live_test",
        button_seen=True,
        action_confirmed=True,
        preset_message_auto_sent=True,
    )

    assert decision["contacted"] is True
    assert decision["preset_message_auto_sent"] is True

    with pytest.raises(ValueError, match="live contact test limit"):
        boss_app_sourcing.record_contact_decision(
            root,
            candidate["candidate_key"],
            mode="live_test",
            button_seen=True,
            action_confirmed=True,
        )


def test_live_contact_requires_detail_contact_and_would_contact(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign(
        "boss-live-preconditions",
        "看 AI 产品",
        out_base=tmp_path,
        allow_real_contact=True,
        allow_live_contact_test=True,
        live_contact_test_limit=1,
    )
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "钱女士",
        "current_title": "AI PM",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-4c"),
    })

    with pytest.raises(ValueError, match="detail recommendation"):
        boss_app_sourcing.record_contact_decision(
            root,
            candidate["candidate_key"],
            mode="live_test",
            button_seen=True,
            action_confirmed=True,
        )

    boss_app_sourcing.record_detail_update(root, candidate["candidate_key"], {}, "contact", 80, ["详情匹配"])

    with pytest.raises(ValueError, match="would_contact"):
        boss_app_sourcing.record_contact_decision(
            root,
            candidate["candidate_key"],
            mode="live_test",
            button_seen=True,
            action_confirmed=True,
        )


def test_live_contact_is_disabled_by_default(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-live-disabled", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "孙先生",
        "current_title": "AI PM",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-4b"),
    })

    with pytest.raises(ValueError, match="not enabled"):
        boss_app_sourcing.record_contact_decision(
            root,
            candidate["candidate_key"],
            mode="live_test",
            button_seen=True,
            action_confirmed=True,
        )


def test_backfill_real_name_preserves_display_name(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-real-name", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "张先生",
        "current_title": "产品经理",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-5"),
    })

    updated = boss_app_sourcing.backfill_real_name(
        root,
        candidate["candidate_key"],
        real_name="张 XX",
        source="manual_opened_communication_page",
    )

    assert updated["display_name"] == "张先生"
    assert updated["real_name"] == "张 XX"
    assert updated["real_name_source"] == "manual_opened_communication_page"
    assert updated["real_name_status"] == "captured"


def test_repeated_list_card_does_not_reset_latest_candidate_state(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-repeat-card", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    card = {
        "display_name": "周先生",
        "current_title": "AI PM",
        "screenshot_hash": boss_app_sourcing.screen_hash("repeat-card"),
    }
    candidate = boss_app_sourcing.record_list_card(root, card)
    boss_app_sourcing.record_detail_update(root, candidate["candidate_key"], {}, "contact", 82, ["详情匹配"])
    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "dry_run", True, False)
    boss_app_sourcing.backfill_real_name(root, candidate["candidate_key"], "周 XX", "manual_opened_communication_page")

    repeated = boss_app_sourcing.record_list_card(root, card)

    assert repeated["screening"]["detail_decision"] == "contact"
    assert repeated["contact"]["would_contact"] is True
    assert repeated["real_name"] == "周 XX"
    assert boss_app_sourcing.latest_candidate(root, candidate["candidate_key"])["real_name_status"] == "captured"


def test_live_contact_rejects_same_candidate_twice_and_dry_run_does_not_downgrade(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign(
        "boss-repeat-live",
        "看 AI 产品",
        out_base=tmp_path,
        allow_real_contact=True,
        allow_live_contact_test=True,
        live_contact_test_limit=2,
    )
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "吴女士",
        "current_title": "AI PM",
        "screenshot_hash": boss_app_sourcing.screen_hash("repeat-live"),
    })
    boss_app_sourcing.record_detail_update(root, candidate["candidate_key"], {}, "contact", 90, ["详情匹配"])
    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "dry_run", True, False)
    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "live_test", True, True, True)

    with pytest.raises(ValueError, match="already contacted"):
        boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "live_test", True, True, True)

    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "dry_run", True, False)
    latest = boss_app_sourcing.latest_candidate(root, candidate["candidate_key"])
    assert latest["contact"]["contacted"] is True
    assert latest["contact"]["live_contact_test"] is True
    assert latest["contact"]["preset_message_auto_sent"] is True


def test_backfill_real_name_requires_valid_source_state_and_rejects_overwrite(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-real-name-source", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "郑女士",
        "current_title": "AI PM",
        "screenshot_hash": boss_app_sourcing.screen_hash("real-source"),
    })

    with pytest.raises(ValueError, match="live contacted"):
        boss_app_sourcing.backfill_real_name(
            root,
            candidate["candidate_key"],
            "郑 XX",
            "communication_page_after_live_contact_test",
        )

    boss_app_sourcing.backfill_real_name(root, candidate["candidate_key"], "郑 XX", "manual_opened_communication_page")

    with pytest.raises(ValueError, match="already captured"):
        boss_app_sourcing.backfill_real_name(root, candidate["candidate_key"], "李 XX", "manual_opened_communication_page")


def test_raw_detail_and_communication_records_include_recovery_fields(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-raw-recovery", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "冯先生",
        "current_title": "AI PM",
        "screenshot_hash": boss_app_sourcing.screen_hash("raw-card"),
    })

    boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {"work_experience": [{"company": "A 公司"}]},
        recommendation="hold",
        score=70,
        reasons=["信息不足"],
        risks=["缺少学历"],
    )
    boss_app_sourcing.backfill_real_name(
        root,
        candidate["candidate_key"],
        "冯 XX",
        "manual_opened_communication_page",
        page_text="冯 XX\n沟通页标题",
        screenshot_hash=boss_app_sourcing.screen_hash("communication-page"),
    )

    detail = boss_app_sourcing.load_jsonl(root / "raw/detail-pages.jsonl")[-1]
    communication = boss_app_sourcing.load_jsonl(root / "raw/communication-pages.jsonl")[-1]
    assert detail["reasons"] == ["信息不足"]
    assert detail["risks"] == ["缺少学历"]
    assert communication["page_text"] == "冯 XX\n沟通页标题"
    assert communication["screenshot_hash"].startswith("sha256:")


def test_write_continuation_plan_records_next_action(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-resume", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])

    plan = boss_app_sourcing.write_continuation_plan(
        root,
        stage="S4",
        status="blocked",
        reason="ui_template_drift",
        next_action="请用户手动回到 BOSS 推荐列表页后继续",
    )

    saved = read_json(root / "state/continuation-plan.json")
    assert saved == plan
    assert saved["reason"] == "ui_template_drift"
    assert saved["next_action"] == "请用户手动回到 BOSS 推荐列表页后继续"
    events = boss_app_sourcing.load_jsonl(root / "state/events.jsonl")
    assert events[-1]["reason"] == "ui_template_drift"


def test_summarize_campaign_counts_candidates_contacts_and_real_names(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign(
        "boss-summary",
        "看 AI 产品",
        out_base=tmp_path,
        allow_real_contact=True,
        allow_live_contact_test=True,
        live_contact_test_limit=2,
    )
    root = Path(manifest["campaign_root"])
    a = boss_app_sourcing.record_list_card(root, {
        "display_name": "张先生",
        "current_title": "AI 产品",
        "screenshot_hash": boss_app_sourcing.screen_hash("a"),
    })
    b = boss_app_sourcing.record_list_card(root, {
        "display_name": "李女士",
        "current_title": "算法产品",
        "screenshot_hash": boss_app_sourcing.screen_hash("b"),
    })
    boss_app_sourcing.record_detail_update(root, a["candidate_key"], {}, "contact", 88, ["强匹配"])
    boss_app_sourcing.record_contact_decision(root, a["candidate_key"], "dry_run", True, False)
    boss_app_sourcing.record_contact_decision(root, a["candidate_key"], "live_test", True, True, True)
    boss_app_sourcing.backfill_real_name(root, a["candidate_key"], "张 XX", "communication_page_after_live_contact_test")
    boss_app_sourcing.record_detail_update(root, b["candidate_key"], {}, "skip", 42, ["学历不符"])

    summary = boss_app_sourcing.summarize_campaign(root)

    assert summary["candidate_count"] == 2
    assert summary["detail_count"] == 2
    assert summary["would_contact_count"] == 1
    assert summary["live_contact_count"] == 1
    assert summary["live_contact_remaining"] == 1
    assert summary["real_name_captured_count"] == 1
    assert summary["real_name_status_distribution"] == {
        "captured": 1,
        "not_available_dry_run": 1,
    }
    assert summary["skip_count"] == 1
    assert summary["skip_reason_distribution"] == {"学历不符": 1}
    assert [item["candidate_key"] for item in summary["manual_review_candidates"]] == [b["candidate_key"]]
    assert (root / "reports/sourcing-summary.json").exists()
    text = (root / "reports/sourcing-summary.md").read_text(encoding="utf-8")
    assert "BOSS App 寻访摘要" in text
    assert "真实姓名补全：1" in text
    assert "Live-test 剩余额度：1" in text
    assert "人工复核清单" in text


def test_summarize_campaign_uses_latest_candidate_once(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-summary-latest", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    card = {
        "display_name": "陈先生",
        "current_title": "AI 产品",
        "screenshot_hash": boss_app_sourcing.screen_hash("summary-latest"),
    }
    candidate = boss_app_sourcing.record_list_card(root, card)
    boss_app_sourcing.record_detail_update(root, candidate["candidate_key"], {}, "hold", 65, ["待补充"])
    boss_app_sourcing.record_list_card(root, card)

    summary = boss_app_sourcing.summarize_campaign(root)

    assert summary["candidate_count"] == 1
    assert summary["list_card_count"] == 2
    assert summary["detail_count"] == 1
    assert summary["manual_review_candidates"][0]["detail_decision"] == "hold"


def test_summarize_campaign_requires_readable_run_policy(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-summary-policy", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    (root / "run-policy.json").unlink()

    with pytest.raises(ValueError, match="run-policy\\.json"):
        boss_app_sourcing.summarize_campaign(root)

    (root / "run-policy.json").write_text("{bad json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="run-policy\\.json"):
        boss_app_sourcing.summarize_campaign(root)

    (root / "run-policy.json").write_text("null\n", encoding="utf-8")

    with pytest.raises(ValueError, match="run-policy\\.json"):
        boss_app_sourcing.summarize_campaign(root)


def test_summarize_cli_prints_summary_json(tmp_path: Path, capsys) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-summary-cli", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])

    exit_code = boss_app_sourcing.main(["summarize", "--campaign-root", str(root)])

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["campaign_root"] == str(root)
    assert summary["candidate_count"] == 0


def test_non_ui_flow_can_initialize_record_and_summarize(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-flow", "优先大模型产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "陈先生",
        "current_company": "大模型公司",
        "current_title": "产品经理",
        "education": "本科",
        "city": "北京",
        "expected_salary": "30-50K",
        "screenshot_hash": boss_app_sourcing.screen_hash("flow-card"),
    })
    boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {"work_experience": [{"company": "大模型公司", "title": "产品经理"}]},
        recommendation="contact",
        score=90,
        reasons=["公司和职位匹配"],
    )
    boss_app_sourcing.record_contact_decision(
        root,
        candidate["candidate_key"],
        mode="dry_run",
        button_seen=True,
        action_confirmed=False,
    )

    summary = boss_app_sourcing.summarize_campaign(root)

    assert summary["candidate_count"] == 1
    assert summary["detail_count"] == 1
    assert summary["would_contact_count"] == 1
    assert summary["live_contact_count"] == 0
