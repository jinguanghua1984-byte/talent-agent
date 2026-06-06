import csv
import json
import sqlite3
from pathlib import Path

import pytest

from scripts import boss_maimai_campaign_delivery as delivery


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _candidate(
    root: Path,
    key: str,
    real_name: str,
    display_name: str,
    company: str,
    title: str,
    score: int,
) -> None:
    payload = {
        "candidate_key": key,
        "real_name": real_name,
        "real_name_status": "captured",
        "display_name": display_name,
        "current_company": company,
        "current_title": title,
        "city": "北京",
        "education": "博士",
        "contact": {
            "contacted": True,
            "message_status": "送达",
        },
        "screening": {
            "score": score,
            "reasons": [f"{real_name} 推荐理由"],
            "risks": [f"{real_name} 待确认风险"],
        },
    }
    _append_jsonl(root / "structured/candidates.jsonl", payload)
    _append_jsonl(
        root / "structured/approved-contact-queue.jsonl",
        {
            "candidate_key": key,
            "display_name": display_name,
            "current_company": company,
            "current_title": title,
            "score": score,
            "recommendation": "contact",
            "reasons": [f"{real_name} 推荐理由"],
            "risks": [f"{real_name} 待确认风险"],
            "approval_status": "approved_for_auto_contact",
        },
    )
    _append_jsonl(
        root / "structured/contact-decisions.jsonl",
        {
            "candidate_key": key,
            "contacted": True,
            "message_status": "送达",
        },
    )
    _append_jsonl(
        root / "structured/maimai-match-targets.jsonl",
        {
            "schema": "boss_maimai_match_target_v1",
            "candidate_key": key,
            "target_id": key.replace(":", "-"),
            "real_name": real_name,
            "current_company": company,
            "current_title": title,
            "city": "北京",
            "education": "博士",
            "query_plan": [
                {
                    "level": "name_company_title",
                    "text": f"{real_name} {company} {title}",
                    "allow_auto_bind": True,
                }
            ],
        },
    )


def _campaign_root(tmp_path: Path, name: str = "boss-campaign") -> Path:
    root = tmp_path / name
    (root / "structured").mkdir(parents=True)
    (root / "reports").mkdir()
    (root / "state").mkdir()
    _write_json(
        root / "reports/sourcing-summary.json",
        {
            "candidate_count": 16,
            "list_card_count": 16,
            "detail_count": 16,
            "would_contact_count": 5,
            "real_contact_count": 5,
            "external_executor_contact_count": 5,
            "real_name_captured_count": 5,
        },
    )
    _write_json(
        root / "reports/executor-summary.json",
        {
            "approved_queue_count": 5,
            "attempt_count": 5,
            "sent_count": 5,
            "message_status_distribution": {"送达": 5},
        },
    )
    _write_json(
        root / "reports/maimai-match-summary.json",
        {
            "target_count": 5,
            "selected_count": 5,
            "missing_real_name_count": 0,
        },
    )
    for key, real_name, display_name, company, title, score in [
        ("boss-app:sun", "孙同", "孙先生", "启元实验室", "大模型算法", 93),
        ("boss-app:luo", "罗力睿", "罗先生", "北京通用人工智能研究院（BIGAI）", "算法研究员", 88),
        ("boss-app:wang-jy", "汪婧昀", "汪女士", "小红书 hilab post-train", "大模型算法工程师", 95),
        ("boss-app:zhou", "周超", "周先生", "亥姆霍兹信息安全中心", "大模型算法", 90),
        ("boss-app:wang-rf", "王若帆", "王先生", "华泰证券", "算法工程师", 98),
    ]:
        _candidate(root, key, real_name, display_name, company, title, score)
    for key in ["boss-app:sun", "boss-app:luo", "boss-app:wang-jy"]:
        _append_jsonl(
            root / "state/cross-channel-identity-ledger.jsonl",
            {
                "source_candidate_key": key,
                "match_status": "no_match",
                "decision_reason": "no_hits",
                "confidence": 0,
                "target_platform_id": "",
                "target_profile_url": "",
            },
        )
    for key, name, status, platform_id in [
        ("boss-app:zhou", "周超", "confirmed_bound", "239360802"),
        ("boss-app:wang-rf", "王若帆", "auto_bound", "247772709"),
    ]:
        url = f"https://maimai.cn/profile/detail?dstu={platform_id}&trackable_token=tok"
        _append_jsonl(
            root / "state/cross-channel-identity-ledger.jsonl",
            {
                "source_candidate_key": key,
                "match_status": status,
                "decision_reason": status,
                "confidence": 100 if status == "auto_bound" else 82,
                "target_platform_id": platform_id,
                "target_profile_url": url,
                "hit": {
                    "name": name,
                    "platform_id": platform_id,
                    "profile_url": url,
                },
            },
        )
        _append_jsonl(
            root / "structured/cross-channel-bound-candidates.jsonl",
            {
                "target": {
                    "candidate_key": key,
                    "real_name": name,
                },
                "maimai_hit": {
                    "name": name,
                    "platform_id": platform_id,
                    "profile_url": url,
                },
                "decision": {
                    "source_candidate_key": key,
                    "match_status": status,
                    "target_platform_id": platform_id,
                    "target_profile_url": url,
                },
            },
        )
    _write_json(
        root / "reports/main-db-sync-result.json",
        {
            "schema": "main_db_sync_result_v1",
            "status": "applied",
            "apply_result": {
                "created": {
                    "candidates": 2,
                    "candidate_details": 2,
                    "source_profiles": 4,
                    "candidate_field_values": 14,
                },
                "merged": {"candidates": 0},
                "conflicts": {"candidates": 0},
                "skipped": {"candidates": 0},
                "deleted": {"candidates": 0},
            },
        },
    )
    return root


def _main_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE candidates (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE source_profiles (
            id INTEGER PRIMARY KEY,
            candidate_id INTEGER,
            platform TEXT NOT NULL,
            platform_id TEXT,
            profile_url TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO candidates(id, name) VALUES (?, ?)",
        [(56194, "王若帆"), (56195, "周超")],
    )
    conn.executemany(
        """
        INSERT INTO source_profiles(candidate_id, platform, platform_id, profile_url)
        VALUES (?, ?, ?, ?)
        """,
        [
            (56194, "boss_app", "boss-app:wang-rf", ""),
            (
                56194,
                "maimai",
                "247772709",
                "https://maimai.cn/profile/detail?dstu=247772709&trackable_token=tok",
            ),
            (56195, "boss_app", "boss-app:zhou", ""),
            (
                56195,
                "maimai",
                "239360802",
                "https://maimai.cn/profile/detail?dstu=239360802&trackable_token=tok",
            ),
        ],
    )
    conn.commit()
    conn.close()


def test_write_delivery_package_includes_all_contacted_candidates_and_subset_statuses(
    tmp_path: Path,
) -> None:
    root = _campaign_root(tmp_path)
    main_db = tmp_path / "main.db"
    _main_db(main_db)
    legacy_handoff = root / "state/jd-delivery-handoff.json"
    legacy_handoff.write_text(
        json.dumps(
            {
                "schema": "jd_delivery_handoff_v1",
                "delivery_skill": "jd-talent-delivery",
            }
        ),
        encoding="utf-8",
    )
    sync_result_path = root / "reports/main-db-sync-result.json"
    sync_result = json.loads(sync_result_path.read_text(encoding="utf-8"))
    sync_result["handoff"] = {
        "schema": "jd_delivery_handoff_v1",
        "delivery_skill": "jd-talent-delivery",
        "main_db_path": str(main_db),
    }
    _write_json(sync_result_path, sync_result)

    result = delivery.write_delivery_package(root, main_db_path=main_db)

    assert result["quality_gates"]["status"] == "passed"
    assert result["handoff"]["schema"] == "boss_maimai_campaign_delivery_handoff_v1"
    assert result["handoff"]["outputs"] == {
        "report_json": "reports/boss-maimai-delivery-report.json",
        "report_md": "reports/boss-maimai-delivery-report.md",
        "follow_up_csv": "reports/boss-maimai-follow-up-queue.csv",
        "follow_up_md": "reports/boss-maimai-follow-up-queue.md",
        "quality_gates": "reports/boss-maimai-delivery-quality-gates.json",
        "feishu_manifest": "feishu/boss-maimai-delivery-manifest.json",
        "im_notification_message": "feishu/im-notification-message.txt",
        "im_notification_results": "feishu/im-notification-results.json",
    }
    assert not legacy_handoff.exists()
    state_handoff = json.loads(
        (root / "state/boss-maimai-delivery-handoff.json").read_text(encoding="utf-8")
    )
    updated_sync_result = json.loads(sync_result_path.read_text(encoding="utf-8"))
    assert state_handoff["schema"] == "boss_maimai_campaign_delivery_handoff_v1"
    assert updated_sync_result["handoff"]["schema"] == "boss_maimai_campaign_delivery_handoff_v1"
    assert "jd-talent-delivery" not in json.dumps(updated_sync_result["handoff"], ensure_ascii=False)
    report = json.loads(
        (root / "reports/boss-maimai-delivery-report.json").read_text(encoding="utf-8")
    )
    assert report["boss_funnel"]["list_card_count"] == 16
    assert report["boss_funnel"]["detail_count"] == 16
    assert report["boss_funnel"]["real_contact_count"] == 5
    assert report["maimai_funnel"]["target_count"] == 5
    assert report["maimai_funnel"]["matched_count"] == 2
    assert report["main_db_sync"]["created_candidates"] == 2
    rows = _read_csv(root / "reports/boss-maimai-follow-up-queue.csv")
    assert [row["real_name"] for row in rows] == ["孙同", "罗力睿", "汪婧昀", "周超", "王若帆"]
    assert all(row["follow_up_required"] == "true" for row in rows)
    by_name = {row["real_name"]: row for row in rows}
    for name in ["孙同", "罗力睿", "汪婧昀"]:
        assert by_name[name]["maimai_match_status"] == "no_match"
        assert by_name[name]["preferred_channel"] == "boss"
    assert by_name["周超"]["maimai_match_status"] == "confirmed_bound"
    assert by_name["周超"]["preferred_channel"] == "maimai"
    assert by_name["周超"]["main_db_candidate_id"] == "56195"
    assert by_name["王若帆"]["maimai_match_status"] == "auto_bound"
    assert by_name["王若帆"]["preferred_channel"] == "maimai"
    assert by_name["王若帆"]["main_db_candidate_id"] == "56194"
    assert "jd-talent-delivery" not in (
        root / "reports/boss-maimai-delivery-report.md"
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize("final_status", ["rejected", "pending_confirmation"])
def test_identity_ledger_latest_event_overrides_stale_bound_candidate(
    tmp_path: Path,
    final_status: str,
) -> None:
    root = _campaign_root(tmp_path)
    _append_jsonl(
        root / "state/cross-channel-identity-ledger.jsonl",
        {
            "source_candidate_key": "boss-app:wang-rf",
            "match_status": final_status,
            "decision_reason": "manual_correction",
            "confidence": 0,
            "target_platform_id": "",
            "target_profile_url": "",
        },
    )

    report = delivery.build_delivery_report(root)
    rows = delivery.build_follow_up_rows(root, report)
    by_name = {row["real_name"]: row for row in rows}

    assert by_name["王若帆"]["maimai_match_status"] == final_status
    assert by_name["王若帆"]["preferred_channel"] == "boss"
    assert by_name["王若帆"]["maimai_profile_url"] == ""
    assert by_name["王若帆"]["maimai_platform_id"] == ""


def test_quality_gate_blocks_when_follow_up_rows_do_not_equal_contacted_count(
    tmp_path: Path,
) -> None:
    root = _campaign_root(tmp_path)
    report = delivery.build_delivery_report(root)
    rows = delivery.build_follow_up_rows(root, report)[:4]

    gates = delivery.validate_delivery_quality_gates(root, report, rows)

    assert gates["status"] == "blocked"
    assert "follow_up_row_count_mismatch" in gates["blockers"]


@pytest.mark.parametrize(
    ("real_name", "match_status"),
    [
        ("王若帆", "auto_bound"),
        ("周超", "confirmed_bound"),
    ],
)
def test_quality_gate_blocks_matched_maimai_without_profile_url(
    tmp_path: Path,
    real_name: str,
    match_status: str,
) -> None:
    root = _campaign_root(tmp_path)
    report = delivery.build_delivery_report(root)
    for row in report["candidate_rows"]:
        if row["real_name"] == real_name:
            row["maimai_profile_url"] = ""
            break
    rows = delivery.build_follow_up_rows(root, report)
    by_name = {row["real_name"]: row for row in rows}

    gates = delivery.validate_delivery_quality_gates(root, report, rows)

    assert by_name[real_name]["maimai_match_status"] == match_status
    assert by_name[real_name]["preferred_channel"] == "maimai"
    assert gates["status"] == "blocked"
    assert "matched_maimai_missing_profile_url" in gates["blockers"]


def test_quality_gate_blocks_target_and_real_name_count_mismatch(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    report = delivery.build_delivery_report(root)
    report["maimai_funnel"]["target_count"] = 4
    rows = delivery.build_follow_up_rows(root, report)

    gates = delivery.validate_delivery_quality_gates(root, report, rows)

    assert gates["status"] == "blocked"
    assert "maimai_target_count_mismatch" in gates["blockers"]


def test_quality_gate_blocks_main_db_created_count_exceeding_maimai_matched(
    tmp_path: Path,
) -> None:
    root = _campaign_root(tmp_path)
    report = delivery.build_delivery_report(root)
    report["main_db_sync"]["created_candidates"] = 3
    rows = delivery.build_follow_up_rows(root, report)

    gates = delivery.validate_delivery_quality_gates(root, report, rows)

    assert gates["status"] == "blocked"
    assert "main_db_created_exceeds_matched" in gates["blockers"]


def test_quality_gate_blocks_follow_up_required_not_true(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    report = delivery.build_delivery_report(root)
    rows = delivery.build_follow_up_rows(root, report)
    rows[0]["follow_up_required"] = "false"

    gates = delivery.validate_delivery_quality_gates(root, report, rows)

    assert gates["status"] == "blocked"
    assert "follow_up_required_not_true" in gates["blockers"]


def test_quality_gate_blocks_invalid_required_inputs(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    (root / "structured/maimai-match-targets.jsonl").write_text(
        '{"ok": true}\n["not an object"]\n',
        encoding="utf-8",
    )
    report = delivery.build_delivery_report(root)
    rows = delivery.build_follow_up_rows(root, report)

    gates = delivery.validate_delivery_quality_gates(root, report, rows)

    assert gates["status"] == "blocked"
    assert "invalid_required_inputs" in gates["blockers"]
    assert gates["invalid_required_inputs"][0]["path"] == "structured/maimai-match-targets.jsonl"
    assert "line 2" in gates["invalid_required_inputs"][0]["error"]


@pytest.mark.parametrize(
    "required_path",
    [
        "reports/sourcing-summary.json",
        "reports/executor-summary.json",
        "reports/maimai-match-summary.json",
        "reports/main-db-sync-result.json",
        "structured/approved-contact-queue.jsonl",
        "structured/maimai-match-targets.jsonl",
        "state/cross-channel-identity-ledger.jsonl",
    ],
)
def test_write_delivery_package_blocks_when_required_input_is_invalid(
    tmp_path: Path,
    required_path: str,
) -> None:
    root = _campaign_root(tmp_path)
    broken_path = root / required_path
    if required_path.endswith(".jsonl"):
        broken_path.write_text('{"ok": true}\n["not an object"]\n', encoding="utf-8")
    else:
        broken_path.write_text('{"broken":', encoding="utf-8")

    result = delivery.write_delivery_package(root)

    gates_path = root / "reports/boss-maimai-delivery-quality-gates.json"
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    assert result["status"] == "blocked"
    assert result["quality_gates"]["status"] == "blocked"
    assert gates["status"] == "blocked"
    assert "invalid_required_inputs" in gates["blockers"]
    assert gates["invalid_required_inputs"][0]["path"] == required_path


@pytest.mark.parametrize(
    "required_path",
    [
        "reports/sourcing-summary.json",
        "reports/executor-summary.json",
        "reports/maimai-match-summary.json",
        "reports/main-db-sync-result.json",
        "structured/approved-contact-queue.jsonl",
        "structured/maimai-match-targets.jsonl",
        "state/cross-channel-identity-ledger.jsonl",
    ],
)
def test_write_delivery_package_blocks_when_required_input_is_missing(
    tmp_path: Path,
    required_path: str,
) -> None:
    root = _campaign_root(tmp_path)
    (root / required_path).unlink()

    result = delivery.write_delivery_package(root)

    gates_path = root / "reports/boss-maimai-delivery-quality-gates.json"
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    assert result["status"] == "blocked"
    assert gates_path.exists()
    assert gates["status"] == "blocked"
    assert "missing_required_inputs" in gates["blockers"]
    assert required_path in gates["missing_required_inputs"]


def test_feishu_manifest_rejects_legacy_markers_and_sensitive_paths(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    delivery.write_delivery_package(root)

    manifest = delivery.build_feishu_manifest(root, dry_run=True)

    serialized = json.dumps(manifest, ensure_ascii=False)
    serialized_lower = serialized.lower()
    assert manifest["schema"] == "boss_maimai_campaign_delivery_feishu_manifest_v1"
    assert manifest["dry_run"] is True
    assert manifest["legacy_package_policy"] == "keep_existing_package_unchanged"
    assert "boss-maimai-delivery-report.md" in serialized
    assert "boss-maimai-follow-up-queue.csv" in serialized
    assert "boss-maimai-delivery-quality-gates.json" in serialized
    assert "jd-talent-delivery" not in serialized
    assert "talent-recommendation" not in serialized
    assert "talent.db" not in serialized
    assert ".zip" not in serialized
    assert "top30" not in serialized_lower


def test_feishu_manifest_requires_im_notification_after_publish_readback(
    tmp_path: Path,
) -> None:
    root = _campaign_root(tmp_path)
    delivery.write_delivery_package(root)

    manifest = delivery.build_feishu_manifest(root, dry_run=True)

    command_names = [" ".join(command[:3]) for command in manifest["commands"]]
    assert command_names[-2:] == [
        "lark-cli im +chat-search",
        "lark-cli im +messages-send",
    ]
    search_command = manifest["commands"][-2]
    send_command = manifest["commands"][-1]
    assert "JD需求协同" in search_command
    assert "--disable-search-by-user" in search_command
    assert "--chat-id" in send_command
    assert "<JD需求协同_chat_id>" in send_command
    assert "--idempotency-key" in send_command
    idempotency_key = send_command[send_command.index("--idempotency-key") + 1]
    assert idempotency_key.startswith("boss-maimai-")
    assert len(idempotency_key) <= 32
    assert "--text" in send_command
    assert "<contents of feishu/im-notification-message.txt>" in send_command
    assert search_command[-1] == "--dry-run"
    assert send_command[-1] == "--dry-run"
    assert manifest["notification"] == {
        "send_after": "feishu_publish_readback_passed",
        "target_name": "JD需求协同",
        "message_file": "feishu/im-notification-message.txt",
        "result_file": "feishu/im-notification-results.json",
        "idempotency_key": idempotency_key,
    }
    assert manifest["readback_expectations"]["im_notification_status"] == "sent"
    assert manifest["readback_expectations"]["im_notification_target"] == "JD需求协同"


def test_feishu_manifest_allows_campaign_name_with_forbidden_markers_when_sources_are_safe(
    tmp_path: Path,
) -> None:
    root = _campaign_root(tmp_path, name="boss-top30.db-campaign")

    delivery.write_delivery_package(root)
    manifest = delivery.build_feishu_manifest(root, dry_run=True)

    assert manifest["status"] == "ready"
    assert manifest["source_files"] == {
        "delivery_report": "reports/boss-maimai-delivery-report.md",
        "follow_up_queue": "reports/boss-maimai-follow-up-queue.csv",
        "quality_gates": "reports/boss-maimai-delivery-quality-gates.json",
    }
    file_args = []
    for command in manifest["commands"]:
        for index, value in enumerate(command):
            if value == "--file":
                file_args.append(command[index + 1])
    assert file_args == [
        "reports/boss-maimai-delivery-report.md",
        "reports/boss-maimai-follow-up-queue.csv",
    ]


def test_blocked_feishu_manifest_sanitizes_quality_gate_sensitive_paths(
    tmp_path: Path,
) -> None:
    root = _campaign_root(tmp_path)
    delivery.write_delivery_package(root)
    _write_json(
        root / "reports/boss-maimai-delivery-quality-gates.json",
        {
            "schema": "boss_maimai_campaign_delivery_quality_gates_v1",
            "status": "blocked",
            "blockers": [
                "missing_required_inputs",
                "invalid_required_inputs",
                "jd-talent-delivery",
            ],
            "missing_required_inputs": [
                "data/talent.db",
                "raw/private-capture.jsonl",
                "reports/campaign-to-main.zip",
            ],
            "invalid_required_inputs": [
                {
                    "path": "talent-recommendation/raw.json",
                    "error": "raw payload leaked from talent.db",
                }
            ],
            "follow_up_row_count": 5,
            "real_contact_count": 5,
            "maimai_target_count": 5,
        },
    )

    manifest = delivery.build_feishu_manifest(root, dry_run=True)

    serialized = json.dumps(manifest, ensure_ascii=False)
    serialized_lower = serialized.lower()
    assert manifest["status"] == "blocked"
    assert manifest["quality_gates"]["status"] == "blocked"
    assert "missing_required_inputs" in manifest["quality_gates"]["blockers"]
    assert manifest["legacy_package_policy"] == "keep_existing_package_unchanged"
    assert "jd-talent-delivery" not in serialized
    assert "talent-recommendation" not in serialized
    assert "talent.db" not in serialized
    assert ".zip" not in serialized
    assert "raw/" not in serialized
    assert "top30" not in serialized_lower


def test_cli_build_writes_outputs_and_prints_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _campaign_root(tmp_path)

    assert delivery.main(["build", "--campaign-root", str(root)]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "passed"
    assert (root / "reports/boss-maimai-delivery-report.json").exists()
    assert (root / "reports/boss-maimai-delivery-report.md").exists()
    assert (root / "reports/boss-maimai-follow-up-queue.csv").exists()
    assert (root / "reports/boss-maimai-follow-up-queue.md").exists()
    assert (root / "reports/boss-maimai-delivery-quality-gates.json").exists()
    assert (root / "feishu/boss-maimai-delivery-manifest.json").exists()
