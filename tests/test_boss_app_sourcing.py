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


def _contact_candidate_for_executor(tmp_path: Path) -> tuple[Path, str]:
    manifest = boss_app_sourcing.init_campaign(
        campaign_id="boss-executor-artifacts",
        filters_text="AI Infra",
        out_base=tmp_path,
    )
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "陶先生",
        "current_company": "上海华为技术有限公司",
        "current_title": "博士后研究员-大模型方向",
        "age": "34岁",
        "work_years": "4年",
        "education": "博士",
        "expected_salary": "50-80K",
        "screenshot_hash": "sha256:detail",
    })
    boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {
            "profile_header": "陶先生；华为 · 博士后研究员-大模型方向",
            "contact_button_text": "立即沟通",
        },
        "contact",
        90,
        ["华为目标公司", "大模型推理框架方向匹配"],
        ["在职-暂不考虑"],
    )
    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "dry_run", True, False)
    return root, candidate["candidate_key"]


def test_record_approved_contact_queue_item_and_current_intent(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)

    queue_item = boss_app_sourcing.record_approved_contact_queue_item(root, candidate_key)
    assert queue_item["schema"] == "boss_approved_contact_queue_v1"
    assert queue_item["candidate_key"] == candidate_key
    assert queue_item["approval_status"] == "approved_for_auto_contact"
    assert queue_item["button_seen"] == "立即沟通"

    queue_rows = boss_app_sourcing.load_jsonl(root / "structured/approved-contact-queue.jsonl")
    assert len(queue_rows) == 1
    assert queue_rows[0]["candidate_key"] == candidate_key

    intent = boss_app_sourcing.write_current_contact_intent(
        root,
        candidate_key,
        now_text="2026-06-02T10:00:00+08:00",
    )
    assert intent["schema"] == "boss_current_contact_intent_v1"
    assert intent["intent_id"].startswith("20260602T100000-")
    assert intent["expected_button"] == "立即沟通"
    assert intent["display_name"] == "陶先生"
    assert intent["current_company"] == "上海华为技术有限公司"
    assert intent["current_title"] == "博士后研究员-大模型方向"
    assert intent["current_page"] == "candidate_detail"
    assert intent["score"] == 90
    assert intent["reasons"] == ["华为目标公司", "大模型推理框架方向匹配"]
    assert intent["risks"] == ["在职-暂不考虑"]
    assert intent["created_by"] == "codex_screening_loop"
    assert intent["expires_at"] == "2026-06-02T10:10:00+08:00"
    assert read_json(root / "state/current-contact-intent.json")["candidate_key"] == candidate_key


@pytest.mark.parametrize(
    ("card", "missing_field"),
    [
        (
            {
                "display_name": "缺公司先生",
                "current_title": "推理框架工程师",
            },
            "current_company",
        ),
        (
            {
                "display_name": "缺职位先生",
                "current_company": "目标公司",
            },
            "current_title",
        ),
    ],
)
def test_write_current_contact_intent_requires_candidate_payload_fields(
    tmp_path: Path,
    card: dict,
    missing_field: str,
) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-executor-missing-payload", "AI Infra", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, card)
    boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {"contact_button_text": "立即沟通"},
        "contact",
        90,
        ["方向匹配"],
    )
    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "dry_run", True, False)

    with pytest.raises(ValueError, match=missing_field):
        boss_app_sourcing.write_current_contact_intent(root, candidate["candidate_key"])

    assert not (root / "state/current-contact-intent.json").exists()


def test_approved_contact_queue_rejects_non_contact_candidate(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-executor-reject", "AI Infra", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "张先生",
        "current_company": "普通公司",
        "current_title": "测试经理",
    })
    boss_app_sourcing.record_detail_update(root, candidate["candidate_key"], {}, "skip", 20, ["方向不匹配"])

    with pytest.raises(ValueError, match="detail recommendation contact"):
        boss_app_sourcing.record_approved_contact_queue_item(root, candidate["candidate_key"])


def test_approved_contact_queue_rejects_non_immediate_contact_button(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-executor-paid-button", "AI Infra", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "钱先生",
        "current_company": "目标公司",
        "current_title": "推理框架工程师",
    })
    boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {"contact_button_text": "立即联系牛人"},
        "contact",
        90,
        ["方向匹配"],
    )
    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "dry_run", True, False)

    with pytest.raises(ValueError, match="立即沟通"):
        boss_app_sourcing.record_approved_contact_queue_item(root, candidate["candidate_key"])


def test_approved_contact_queue_requires_dry_run_decision_artifact(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-executor-no-dry-run", "AI Infra", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "孙先生",
        "current_company": "目标公司",
        "current_title": "推理框架工程师",
    })
    updated = boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {"contact_button_text": "立即沟通"},
        "contact",
        90,
        ["方向匹配"],
    )
    updated["contact"] = dict(updated["contact"])
    updated["contact"]["would_contact"] = True
    updated["contact"]["contact_button_seen"] = True
    boss_app_sourcing.append_jsonl(root / "structured/candidates.jsonl", updated)

    with pytest.raises(ValueError, match="dry-run would-contact"):
        boss_app_sourcing.record_approved_contact_queue_item(root, candidate["candidate_key"])


def test_consume_executor_sent_result_updates_contact_and_real_name(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    intent = boss_app_sourcing.write_current_contact_intent(
        root,
        candidate_key,
        now_text="2026-06-02T10:00:00+08:00",
    )
    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "campaign_id": root.name,
        "candidate_key": candidate_key,
        "result": "sent",
        "button_before_click": "立即沟通",
        "message_template_id": "boss-current-preset",
        "message_status": "送达",
        "real_name": "陶壮",
        "communication_page_text": "沟通页顶部：陶壮；AI Infra训练与推理研发；状态：送达",
        "next_action_for_codex": "record_contact_return_to_list_and_continue",
        "stopped_reason": None,
        "started_at": "2026-06-02T10:00:02+08:00",
        "finished_at": "2026-06-02T10:00:08+08:00",
    })

    consumed = boss_app_sourcing.consume_executor_result(root)
    assert consumed["result"] == "sent"

    latest = boss_app_sourcing.latest_candidate(root, candidate_key)
    assert latest["real_name"] == "陶壮"
    assert latest["real_name_source"] == "communication_page_after_external_executor"
    assert latest["contact"]["contacted"] is True
    assert latest["contact"]["contact_mode"] == "external_executor"

    decisions = boss_app_sourcing.load_jsonl(root / "structured/contact-decisions.jsonl")
    assert decisions[-1]["mode"] == "external_executor"
    assert decisions[-1]["message_status"] == "送达"
    assert decisions[-1]["preset_message_auto_sent"] is True


def test_consume_and_validate_sent_result_require_current_intent(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    intent = boss_app_sourcing.write_current_contact_intent(
        root,
        candidate_key,
        now_text="2026-06-02T10:00:00+08:00",
    )
    (root / "state/current-contact-intent.json").unlink()
    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "campaign_id": root.name,
        "candidate_key": candidate_key,
        "result": "sent",
        "button_before_click": "立即沟通",
        "message_template_id": "boss-current-preset",
        "message_status": "送达",
        "real_name": "陶壮",
        "communication_page_text": "沟通页顶部：陶壮；状态：送达",
    })
    before_decision_count = len(boss_app_sourcing.load_jsonl(root / "structured/contact-decisions.jsonl"))

    with pytest.raises(ValueError, match="current contact intent"):
        boss_app_sourcing.consume_executor_result(root)

    latest = boss_app_sourcing.latest_candidate(root, candidate_key)
    assert latest["contact"]["contacted"] is False
    assert latest["real_name"] is None
    assert len(boss_app_sourcing.load_jsonl(root / "structured/contact-decisions.jsonl")) == before_decision_count
    assert not boss_app_sourcing.load_jsonl(root / "raw/executor-contact-attempts.jsonl")

    validation = boss_app_sourcing.validate_executor_artifacts(root)
    assert validation["status"] == "failed"
    assert "current_intent.missing" in validation["issues"]


@pytest.mark.parametrize(
    ("override", "error_match"),
    [
        ({"button_before_click": "继续沟通"}, "button_before_click"),
        ({"real_name": ""}, "real_name"),
        ({"message_status": "发送中"}, "message_status"),
        ({"campaign_id": "other-campaign"}, "current contact intent"),
        ({"candidate_key": "boss-app:other"}, "current contact intent"),
    ],
)
def test_consume_executor_rejects_invalid_sent_protocol_without_contacting(
    tmp_path: Path,
    override: dict,
    error_match: str,
) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    intent = boss_app_sourcing.write_current_contact_intent(
        root,
        candidate_key,
        now_text="2026-06-02T10:00:00+08:00",
    )
    result = {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "campaign_id": root.name,
        "candidate_key": candidate_key,
        "result": "sent",
        "button_before_click": "立即沟通",
        "message_template_id": "boss-current-preset",
        "message_status": "送达",
        "real_name": "陶壮",
        "communication_page_text": "沟通页顶部：陶壮；状态：送达",
        "next_action_for_codex": "record_contact_return_to_list_and_continue",
        "stopped_reason": None,
    }
    result.update(override)
    boss_app_sourcing.write_json(root / "state/executor-result.json", result)
    before_decision_count = len(boss_app_sourcing.load_jsonl(root / "structured/contact-decisions.jsonl"))

    with pytest.raises(ValueError, match=error_match):
        boss_app_sourcing.consume_executor_result(root)

    latest = boss_app_sourcing.latest_candidate(root, candidate_key)
    assert latest["contact"]["contacted"] is False
    assert latest["real_name"] is None
    decisions = boss_app_sourcing.load_jsonl(root / "structured/contact-decisions.jsonl")
    assert len(decisions) == before_decision_count
    assert not boss_app_sourcing.load_jsonl(root / "raw/executor-contact-attempts.jsonl")


def test_consume_executor_continue_chat_and_stopped_paths(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    intent = boss_app_sourcing.write_current_contact_intent(
        root,
        candidate_key,
        now_text="2026-06-02T10:00:00+08:00",
    )

    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "candidate_key": candidate_key,
        "result": "skipped_continue_chat",
        "button_before_click": "继续沟通",
        "next_action_for_codex": "record_skip_return_to_list_and_continue",
        "stopped_reason": None,
    })
    skipped = boss_app_sourcing.consume_executor_result(root)
    assert skipped["result"] == "skipped_continue_chat"
    skipped_decision = boss_app_sourcing.load_jsonl(root / "structured/contact-decisions.jsonl")[-1]
    assert skipped_decision["skip_reason"] == "continue_chat"
    assert skipped_decision["already_contacted"] is True
    skipped_candidate = boss_app_sourcing.latest_candidate(root, candidate_key)
    assert skipped_candidate["contact"]["already_contacted"] is True
    assert skipped_candidate["contact"]["contacted"] is False

    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "candidate_key": candidate_key,
        "result": "sent_unverified",
        "button_before_click": "立即沟通",
        "next_action_for_codex": "write_interruption_and_stop",
        "stopped_reason": "communication_result_missing",
    })
    unverified = boss_app_sourcing.consume_executor_result(root)
    assert unverified["result"] == "sent_unverified"
    unverified_plan = read_json(root / "state/continuation-plan.json")
    assert unverified_plan["stage"] == "external_executor"
    assert unverified_plan["reason"] == "communication_result_missing"
    assert list((root / "reports").glob("interruption-executor-communication_result_missing-*.json"))

    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "candidate_key": candidate_key,
        "result": "stopped",
        "button_before_click": "立即联系牛人",
        "next_action_for_codex": "write_interruption_and_stop",
        "stopped_reason": "paid_search_chat_card",
    })
    stopped = boss_app_sourcing.consume_executor_result(root)
    assert stopped["result"] == "stopped"
    plan = read_json(root / "state/continuation-plan.json")
    assert plan["stage"] == "external_executor"
    assert plan["reason"] == "paid_search_chat_card"
    assert list((root / "reports").glob("interruption-executor-paid_search_chat_card-*.json"))
    summary = boss_app_sourcing.summarize_executor_results(root)
    assert summary["skipped_continue_chat_count"] == 1
    assert summary["stopped_count"] == 2
    assert summary["result_distribution"] == {
        "sent_unverified": 1,
        "skipped_continue_chat": 1,
        "stopped": 1,
    }


def test_validate_and_summarize_executor_artifacts(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    boss_app_sourcing.record_approved_contact_queue_item(root, candidate_key)
    intent = boss_app_sourcing.write_current_contact_intent(
        root,
        candidate_key,
        now_text="2026-06-02T10:00:00+08:00",
    )
    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "campaign_id": root.name,
        "candidate_key": candidate_key,
        "result": "sent",
        "button_before_click": "立即沟通",
        "message_template_id": "boss-current-preset",
        "message_status": "送达",
        "real_name": "陶壮",
        "communication_page_text": "沟通页顶部：陶壮；状态：送达",
        "next_action_for_codex": "record_contact_return_to_list_and_continue",
        "stopped_reason": None,
    })
    boss_app_sourcing.consume_executor_result(root)

    validation = boss_app_sourcing.validate_executor_artifacts(root)
    assert validation["status"] == "passed"
    assert validation["approved_queue_count"] == 1
    assert validation["attempt_count"] == 1
    assert validation["issues"] == []

    summary = boss_app_sourcing.summarize_executor_results(root)
    assert summary["approved_queue_count"] == 1
    assert summary["sent_count"] == 1
    assert summary["skipped_continue_chat_count"] == 0
    assert summary["stopped_count"] == 0
    assert summary["result_distribution"] == {"sent": 1}
    summary_md = root / "reports/executor-summary.md"
    assert summary_md.exists()
    summary_text = summary_md.read_text(encoding="utf-8")
    assert "approved_queue_count: 1" in summary_text
    assert "attempt_count: 1" in summary_text
    assert "sent_count: 1" in summary_text
    assert "skipped_continue_chat_count: 0" in summary_text
    assert "stopped_count: 0" in summary_text
    assert "- sent: 1" in summary_text


def test_validate_executor_artifacts_reports_intent_result_and_lock_issues(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    boss_app_sourcing.record_approved_contact_queue_item(root, candidate_key)
    intent = boss_app_sourcing.write_current_contact_intent(
        root,
        candidate_key,
        now_text="2026-06-02T10:00:00+08:00",
    )
    bad_intent = dict(intent)
    bad_intent.update({
        "schema": "bad_schema",
        "approval_status": "pending_review",
        "expected_button": "继续沟通",
        "current_page": "candidate_list",
    })
    boss_app_sourcing.write_json(root / "state/current-contact-intent.json", bad_intent)
    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "candidate_key": candidate_key,
        "result": "sent",
    })
    boss_app_sourcing.write_json(root / "state/executor.lock", {
        "schema": "boss_executor_lock_v1",
        "intent_id": intent["intent_id"],
        "candidate_key": candidate_key,
        "status": "unknown",
    })

    validation = boss_app_sourcing.validate_executor_artifacts(root)

    assert validation["status"] == "failed"
    assert "current_intent.schema" in validation["issues"]
    assert "current_intent.approval_status" in validation["issues"]
    assert "current_intent.expected_button" in validation["issues"]
    assert "current_intent.current_page" in validation["issues"]
    assert "executor_result.missing_attempt" in validation["issues"]
    assert "executor_result.sent_missing_external_executor_decision" in validation["issues"]
    assert "executor_lock.status" in validation["issues"]


def test_validate_executor_artifacts_reports_invalid_sent_protocol(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    boss_app_sourcing.record_approved_contact_queue_item(root, candidate_key)
    intent = boss_app_sourcing.write_current_contact_intent(
        root,
        candidate_key,
        now_text="2026-06-02T10:00:00+08:00",
    )
    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "campaign_id": "other-campaign",
        "candidate_key": "boss-app:other",
        "result": "sent",
        "button_before_click": "继续沟通",
        "message_template_id": "boss-current-preset",
        "message_status": "发送中",
        "real_name": "",
    })

    validation = boss_app_sourcing.validate_executor_artifacts(root)

    assert validation["status"] == "failed"
    assert "executor_result.sent_invalid_button" in validation["issues"]
    assert "executor_result.sent_missing_real_name" in validation["issues"]
    assert "executor_result.sent_invalid_message_status" in validation["issues"]
    assert "executor_result.intent_mismatch" in validation["issues"]


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


def test_candidate_signature_ignores_screen_position_batch_and_hash() -> None:
    card = {
        "display_name": "王先生",
        "current_company": "腾讯",
        "current_title": "技术总监",
        "age": "38岁",
        "work_years": "10年以上",
        "education": "本科",
        "city": "上海",
        "expected_salary": "90-110K",
        "screenshot_hash": "sha256:a",
        "list_scroll_batch": 1,
        "card_position": 2,
    }
    moved_card = dict(card)
    moved_card.update({
        "screenshot_hash": "sha256:b",
        "list_scroll_batch": 9,
        "card_position": 4,
    })

    assert boss_app_sourcing.build_candidate_signature(card).startswith("boss-app-signature:")
    assert boss_app_sourcing.build_candidate_signature(card) == boss_app_sourcing.build_candidate_signature(moved_card)
    assert boss_app_sourcing.build_candidate_key(card) != boss_app_sourcing.build_candidate_key(moved_card)


def test_record_list_card_stores_stable_signature(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-signature", "全部进入详情", out_base=tmp_path)
    root = Path(manifest["campaign_root"])

    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "王先生",
        "current_company": "腾讯",
        "current_title": "技术总监",
        "age": "38岁",
        "work_years": "10年以上",
        "education": "本科",
        "expected_salary": "90-110K",
        "screenshot_hash": boss_app_sourcing.screen_hash("signature-card"),
    })

    raw = boss_app_sourcing.load_jsonl(root / "raw/list-cards.jsonl")[-1]
    assert candidate["candidate_signature"].startswith("boss-app-signature:")
    assert raw["candidate_signature"] == candidate["candidate_signature"]


def test_validate_campaign_flags_missing_detail_and_contact_then_passes(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-validate", "全部进入详情", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "李先生",
        "current_company": "腾讯",
        "current_title": "测试开发",
        "screenshot_hash": boss_app_sourcing.screen_hash("validate-card"),
    })

    first = boss_app_sourcing.validate_campaign(root)
    assert first["status"] == "failed"
    assert first["missing_detail_candidate_keys"] == [candidate["candidate_key"]]

    boss_app_sourcing.record_detail_update(root, candidate["candidate_key"], {}, "contact", 100, ["全部匹配"])
    second = boss_app_sourcing.validate_campaign(root)
    assert second["status"] == "failed"
    assert second["missing_contact_candidate_keys"] == [candidate["candidate_key"]]

    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "dry_run", True, False)
    final = boss_app_sourcing.validate_campaign(root)
    assert final["status"] == "passed"
    assert final["missing_detail_candidate_keys"] == []
    assert final["missing_contact_candidate_keys"] == []


def test_campaign_stats_reports_distributions(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-stats", "全部进入详情", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    boss_app_sourcing.record_list_card(root, {
        "display_name": "张先生",
        "current_company": "阿里",
        "current_title": "大模型算法",
        "education": "硕士",
        "work_years": "8年",
        "expected_salary": "50-80K",
    })
    boss_app_sourcing.record_list_card(root, {
        "display_name": "李女士",
        "current_company": "腾讯",
        "current_title": "技术总监",
        "education": "本科",
        "work_years": "10年以上",
        "expected_salary": "90-110K",
    })

    stats = boss_app_sourcing.campaign_stats(root)

    assert stats["candidate_count"] == 2
    assert stats["education_distribution"] == {"本科": 1, "硕士": 1}
    assert stats["current_title_distribution"] == {"大模型算法": 1, "技术总监": 1}
    assert stats["expected_salary_distribution"] == {"50-80K": 1, "90-110K": 1}


def test_record_cli_commands_accept_json_payloads_and_complete(tmp_path: Path, capsys) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-record-cli", "全部进入详情", out_base=tmp_path)
    root = Path(manifest["campaign_root"])

    assert boss_app_sourcing.main([
        "record-list-card",
        "--campaign-root",
        str(root),
        "--json",
        json.dumps({"display_name": "王先生", "current_company": "腾讯", "current_title": "技术总监"}),
    ]) == 0
    candidate = json.loads(capsys.readouterr().out)

    assert boss_app_sourcing.main([
        "record-detail",
        "--campaign-root",
        str(root),
        "--candidate-key",
        candidate["candidate_key"],
        "--json",
        json.dumps({
            "detail_sections": {"work_experience": "腾讯技术管理"},
            "recommendation": "contact",
            "score": 100,
            "reasons": ["全部匹配"],
        }, ensure_ascii=False),
    ]) == 0
    capsys.readouterr()

    assert boss_app_sourcing.main([
        "record-dry-run-contact",
        "--campaign-root",
        str(root),
        "--candidate-key",
        candidate["candidate_key"],
        "--button-seen",
    ]) == 0
    capsys.readouterr()

    assert boss_app_sourcing.main([
        "complete",
        "--campaign-root",
        str(root),
        "--reason",
        "已完成 dry-run",
        "--next-action",
        "汇报 summary",
    ]) == 0
    plan = read_json(root / "state/continuation-plan.json")
    assert plan["status"] == "completed_after_dry_run"


def test_parse_list_cards_from_accessibility_text_extracts_visible_cards() -> None:
    tree_text = """
    21 文本 Description: 求职期望：测试经理, 西安交通大学·软件工程, QS前500院校, 腾讯12级，看一线二线大厂测试总监或实线TL岗位。, 李先生, 35岁  |  10年以上  |  本科  |  80-100K, 刚刚活跃, Ai评测, Java
    23 文本 Description: 腾讯 · 测试开发, Secondary Actions: Cancel
    27 文本 Description: 背景：百度/腾讯12级/字节3-2，前端/客户端出身。, 王先生, 38岁  |  10年以上  |  本科  |  90-110K, 刚刚活跃, 技术管理, React
    29 文本 Description: 腾讯 · 技术总监, Secondary Actions: Cancel
    """

    cards = boss_app_sourcing.parse_list_cards_from_accessibility_text(tree_text, list_scroll_batch=7)

    assert cards == [
        {
            "display_name": "李先生",
            "age": "35岁",
            "work_years": "10年以上",
            "education": "本科",
            "expected_salary": "80-100K",
            "active_state": "刚刚活跃",
            "current_company": "腾讯",
            "current_title": "测试开发",
            "list_scroll_batch": 7,
            "card_position": 1,
            "list_decision": "detail_for_all",
            "raw_text": "求职期望：测试经理, 西安交通大学·软件工程, QS前500院校, 腾讯12级，看一线二线大厂测试总监或实线TL岗位。, 李先生, 35岁  |  10年以上  |  本科  |  80-100K, 刚刚活跃, Ai评测, Java",
            "screen_region": "visible_card_1",
        },
        {
            "display_name": "王先生",
            "age": "38岁",
            "work_years": "10年以上",
            "education": "本科",
            "expected_salary": "90-110K",
            "active_state": "刚刚活跃",
            "current_company": "腾讯",
            "current_title": "技术总监",
            "list_scroll_batch": 7,
            "card_position": 2,
            "list_decision": "detail_for_all",
            "raw_text": "背景：百度/腾讯12级/字节3-2，前端/客户端出身。, 王先生, 38岁  |  10年以上  |  本科  |  90-110K, 刚刚活跃, 技术管理, React",
            "screen_region": "visible_card_2",
        },
    ]


def test_parse_detail_sections_from_accessibility_text_groups_sections_and_button() -> None:
    tree_text = """
    12 文本 Description: 王先生, Secondary Actions: Cancel
    14 文本 Description: 在职-考虑机会, 10年以上, 本科, 刚刚活跃, Secondary Actions: Cancel
    17 文本 Description: 求职期望, Secondary Actions: Cancel
    19 文本 Description: 互联网 · 移动互联网 · 计算机软件, 90-110K, Secondary Actions: Cancel
    20 文本 Description: 技术总监，上海, Secondary Actions: Cancel
    21 文本 Description: 工作经历, Secondary Actions: Cancel
    24 文本 Description: 腾讯视频客户端团队 技术管理工作
    Ai coding，流程改造，研发效能devops
    25 文本 Description: 腾讯科技（北京）有限公司, Secondary Actions: Cancel
    30 文本 Description: 教育经历, Secondary Actions: Cancel
    32 文本 Description: 本科 · 电子信息, Secondary Actions: Cancel
    34 文本 Description: 河南大学, Secondary Actions: Cancel
    45 按钮 Description: 立即沟通, Secondary Actions: Cancel
    """

    detail = boss_app_sourcing.parse_detail_sections_from_accessibility_text(tree_text)

    assert detail["contact_button_text"] == "立即沟通"
    assert detail["bottom_reached"] is True
    assert "王先生" in detail["profile_header"]
    assert "技术总监，上海" in detail["expectation"]
    assert "腾讯视频客户端团队" in detail["work_experience"]
    assert "河南大学" in detail["education"]


def test_build_all_match_detail_decision_keeps_contact_and_records_risks() -> None:
    detail = {
        "profile_header": "在职-暂不考虑；只看 CTO 岗位",
        "work_experience": "腾讯测试开发 TL，求测试总监岗位",
        "contact_button_text": "立即沟通",
    }

    decision = boss_app_sourcing.build_all_match_detail_decision(detail)

    assert decision["recommendation"] == "contact"
    assert decision["score"] == 100
    assert decision["reasons"] == ["无筛选条件，列表中全部人选视为匹配", "详情页已采集", "立即沟通按钮可见"]
    assert decision["risks"] == [
        "候选状态显示暂不考虑；本轮按用户要求仍只做 dry-run would-contact",
        "候选人个人描述限定 CTO 岗位，后续真实沟通前需复核岗位匹配",
        "候选人期望测试经理/测试总监，后续真实沟通前需复核岗位匹配",
    ]
