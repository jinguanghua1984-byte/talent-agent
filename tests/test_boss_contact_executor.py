import json
import subprocess
from pathlib import Path

import pytest

from scripts import boss_app_sourcing, boss_contact_executor


ACK = "I understand this sends real messages to third-party candidates."


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _make_contact_candidate(tmp_path: Path) -> tuple[Path, str]:
    manifest = boss_app_sourcing.init_campaign("boss-contact-executor", "AI Infra", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "陶先生",
        "current_company": "上海华为技术有限公司",
        "current_title": "博士后研究员-大模型方向",
        "age": "34岁",
        "work_years": "4年",
        "education": "博士",
        "expected_salary": "50-80K",
    })
    boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {"profile_header": "陶先生；上海华为技术有限公司；博士后研究员-大模型方向", "contact_button_text": "立即沟通"},
        "contact",
        90,
        ["华为目标公司"],
    )
    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "dry_run", True, False)
    return root, candidate["candidate_key"]


def make_executor_campaign(tmp_path: Path) -> tuple[Path, str]:
    root, candidate_key = _make_contact_candidate(tmp_path)
    boss_app_sourcing.record_approved_contact_queue_item(root, candidate_key)
    boss_app_sourcing.write_current_contact_intent(root, candidate_key, now_text="2026-06-02T10:00:00+08:00")
    write_json(root / "executor-policy.json", {
        "schema": "boss_contact_executor_policy_v1",
        "campaign_id": root.name,
        "allow_real_contact": True,
        "operator_acknowledgement": ACK,
        "max_contacts_per_run": 1,
        "max_contacts_per_day": 50,
        "message_template_id": "boss-current-preset",
        "require_execute_flag": True,
        "skip_continue_chat": True,
        "stop_on_paid_prompt": True,
        "stop_on_captcha": True,
        "stop_on_login_or_security_page": True,
        "stop_on_unknown_ui": True,
        "capture_real_name_after_contact": False,
        "kill_switch_path": str(root / "state/stop-executor.flag"),
    })
    return root, candidate_key


def test_validate_policy_requires_execute_flag_and_acknowledgement(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    policy = boss_contact_executor.load_executor_policy(root)

    dry = boss_contact_executor.validate_executor_policy(policy, execute=False)
    assert dry["execute"] is False

    execute = boss_contact_executor.validate_executor_policy(policy, execute=True)
    assert execute["execute"] is True

    policy["operator_acknowledgement"] = "wrong"
    with pytest.raises(ValueError, match="operator_acknowledgement"):
        boss_contact_executor.validate_executor_policy(policy, execute=True)

    policy["operator_acknowledgement"] = ACK
    policy["allow_real_contact"] = False
    with pytest.raises(ValueError, match="allow_real_contact"):
        boss_contact_executor.validate_executor_policy(policy, execute=True)


def test_validate_policy_allows_null_daily_contact_limit(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    policy = boss_contact_executor.load_executor_policy(root)
    policy["max_contacts_per_day"] = None

    validated = boss_contact_executor.validate_executor_policy(policy, execute=True)

    assert validated["max_contacts_per_day"] is None


def test_validate_policy_rejects_executor_real_name_capture(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    policy = boss_contact_executor.load_executor_policy(root)
    policy["capture_real_name_after_contact"] = True

    with pytest.raises(ValueError, match="capture_real_name_after_contact"):
        boss_contact_executor.validate_executor_policy(policy, execute=True)


def test_validate_policy_rejects_batch_size_in_mvp(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    policy = boss_contact_executor.load_executor_policy(root)
    policy["max_contacts_per_run"] = 2
    with pytest.raises(ValueError, match="max_contacts_per_run"):
        boss_contact_executor.validate_executor_policy(policy, execute=True)


def test_load_and_validate_current_intent(tmp_path: Path) -> None:
    root, candidate_key = make_executor_campaign(tmp_path)
    intent = boss_contact_executor.load_current_intent(root)
    validated = boss_contact_executor.validate_current_intent(
        intent,
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert validated["candidate_key"] == candidate_key

    intent["approval_status"] = "pending"
    with pytest.raises(ValueError, match="approval_status"):
        boss_contact_executor.validate_current_intent(intent, now_text="2026-06-02T10:05:00+08:00")


def test_validate_current_intent_rejects_expired_intent(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    intent = boss_contact_executor.load_current_intent(root)
    with pytest.raises(ValueError, match="expired"):
        boss_contact_executor.validate_current_intent(intent, now_text="2026-06-02T10:11:00+08:00")


def test_validate_current_intent_rejects_naive_expires_at(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    intent = boss_contact_executor.load_current_intent(root)
    intent["expires_at"] = "2026-06-02T10:10:00"

    with pytest.raises(ValueError, match="expires_at.*timezone"):
        boss_contact_executor.validate_current_intent(intent, now_text="2026-06-02T10:05:00+08:00")


def test_validate_current_intent_rejects_naive_now_text(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    intent = boss_contact_executor.load_current_intent(root)

    with pytest.raises(ValueError, match="now_text.*timezone"):
        boss_contact_executor.validate_current_intent(intent, now_text="2026-06-02T10:05:00")


def write_fixture(path: Path, data: dict) -> Path:
    write_json(path, data)
    return path


def ready_fixture(tmp_path: Path) -> Path:
    return write_fixture(tmp_path / "detail-ready.json", {
        "detail": {
            "front_app": "BOSS直聘",
            "window_title": "陶先生",
            "page_text": "陶先生 上海华为技术有限公司 博士后研究员-大模型方向 立即沟通",
            "buttons": ["立即沟通"],
        },
        "communication": {
            "front_app": "BOSS直聘",
            "window_title": "陶壮",
            "page_text": "沟通页顶部：陶壮；AI Infra训练与推理研发；消息状态：送达",
            "buttons": ["求简历", "换电话/微信"],
        },
    })


def test_contact_current_fixture_dry_run_does_not_click(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    ui = boss_contact_executor.FixtureBossUI(ready_fixture(tmp_path))
    result = boss_contact_executor.contact_current(
        root,
        execute=False,
        ui=ui,
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert result["result"] == "dry_run_ready"
    assert result["would_click"] is True
    assert ui.clicked is False
    assert boss_app_sourcing.load_json(root / "state/executor-result.json")["result"] == "dry_run_ready"


def test_contact_current_fixture_execute_sends_and_writes_audit(tmp_path: Path) -> None:
    root, candidate_key = make_executor_campaign(tmp_path)
    result = boss_contact_executor.contact_current(
        root,
        execute=True,
        ui=boss_contact_executor.FixtureBossUI(ready_fixture(tmp_path)),
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert result["result"] == "sent"
    assert result["candidate_key"] == candidate_key
    assert result["message_status"] == "送达"
    assert "real_name" not in result
    assert "communication_page_text" not in result
    attempts = boss_app_sourcing.load_jsonl(root / "raw/executor-contact-attempts.jsonl")
    assert [row["event_type"] for row in attempts] == ["attempt_started", "attempt_finished"]


class KillSwitchBeforeClickBossUI(boss_contact_executor.FixtureBossUI):
    def __init__(self, fixture_path: Path, kill_switch_path: Path):
        super().__init__(fixture_path)
        self.kill_switch_path = kill_switch_path

    def find_contact_button(self, snapshot: boss_contact_executor.BossPageSnapshot) -> boss_contact_executor.ContactButtonState:
        button = super().find_contact_button(snapshot)
        self.kill_switch_path.write_text("stop\n", encoding="utf-8")
        return button


def test_contact_current_checks_kill_switch_immediately_before_click(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    ui = KillSwitchBeforeClickBossUI(ready_fixture(tmp_path), root / "state/stop-executor.flag")

    with pytest.raises(RuntimeError, match="executor_kill_switch_enabled"):
        boss_contact_executor.contact_current(
            root,
            execute=True,
            ui=ui,
            now_text="2026-06-02T10:05:00+08:00",
        )

    assert ui.clicked is False
    result = boss_app_sourcing.load_json(root / "state/executor-result.json")
    assert result["result"] == "stopped"
    assert result["stopped_reason"] == "executor_kill_switch_enabled"


def test_contact_current_finishes_lock_with_result(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    result = boss_contact_executor.contact_current(
        root,
        execute=True,
        ui=boss_contact_executor.FixtureBossUI(ready_fixture(tmp_path)),
        now_text="2026-06-02T10:05:00+08:00",
    )
    executor_result = boss_app_sourcing.load_json(root / "state/executor-result.json")
    lock = boss_app_sourcing.load_json(root / "state/executor.lock")

    assert lock["status"] == "finished"
    assert lock["finished_at"] == "2026-06-02T10:05:00+08:00"
    assert lock["result"] == result["result"] == executor_result["result"]
    assert lock["lock_id"]
    assert lock["intent_id"] == result["intent_id"]
    assert lock["candidate_key"] == result["candidate_key"]
    assert isinstance(lock["pid"], int)


def test_contact_current_rejects_running_lock_without_click(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    boss_app_sourcing.write_json(root / "state/executor.lock", {
        "schema": "boss_executor_lock_v1",
        "status": "running",
        "created_at": "2026-06-02T10:04:00+08:00",
    })
    ui = boss_contact_executor.FixtureBossUI(ready_fixture(tmp_path))

    with pytest.raises(RuntimeError, match="stale_lock_requires_review"):
        boss_contact_executor.contact_current(
            root,
            execute=True,
            ui=ui,
            now_text="2026-06-02T10:05:00+08:00",
        )

    assert ui.clicked is False
    attempts = boss_app_sourcing.load_jsonl(root / "raw/executor-contact-attempts.jsonl")
    assert attempts == []
    result = boss_app_sourcing.load_json(root / "state/executor-result.json")
    assert result["result"] == "stopped"
    assert result["stopped_reason"] == "stale_lock_requires_review"


class FailingAfterClickBossUI:
    def __init__(self, fixture_path: Path):
        self.delegate = boss_contact_executor.FixtureBossUI(fixture_path)
        self.clicked = False

    def read_current_page(self) -> boss_contact_executor.BossPageSnapshot:
        return self.delegate.read_current_page()

    def find_contact_button(
        self,
        page: boss_contact_executor.BossPageSnapshot,
    ) -> boss_contact_executor.ContactButtonState:
        return self.delegate.find_contact_button(page)

    def click_contact(self, button: boss_contact_executor.ContactButtonState) -> None:
        self.delegate.click_contact(button)
        self.clicked = True

    def wait_for_communication_page(self) -> boss_contact_executor.BossPageSnapshot:
        raise RuntimeError("communication_page_timeout")

    def extract_communication_result(
        self,
        page: boss_contact_executor.BossPageSnapshot,
    ) -> boss_contact_executor.CommunicationResult:
        raise AssertionError("extract should not be called")


def test_contact_current_click_recovery_failure_is_sent_unverified(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    ui = FailingAfterClickBossUI(ready_fixture(tmp_path))

    result = boss_contact_executor.contact_current(
        root,
        execute=True,
        ui=ui,
        now_text="2026-06-02T10:05:00+08:00",
    )

    assert ui.clicked is True
    assert result["result"] == "sent_unverified"
    assert result["stopped_reason"] == "communication_page_timeout"
    executor_result = boss_app_sourcing.load_json(root / "state/executor-result.json")
    assert executor_result["result"] == "sent_unverified"
    lock = boss_app_sourcing.load_json(root / "state/executor.lock")
    assert lock["status"] == "finished"
    assert lock["result"] == "sent_unverified"
    attempts = boss_app_sourcing.load_jsonl(root / "raw/executor-contact-attempts.jsonl")
    assert [row["event_type"] for row in attempts] == ["attempt_started", "attempt_finished"]
    assert attempts[-1]["action"] == "click_contact"
    assert attempts[-1]["result"] == "sent_unverified"


def test_contact_current_skips_continue_chat_without_click(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = write_fixture(tmp_path / "continue-chat.json", {
        "detail": {
            "front_app": "BOSS直聘",
            "window_title": "陶先生",
            "page_text": "陶先生 上海华为技术有限公司 博士后研究员-大模型方向 继续沟通",
            "buttons": ["继续沟通"],
        }
    })
    ui = boss_contact_executor.FixtureBossUI(fixture)
    result = boss_contact_executor.contact_current(
        root,
        execute=True,
        ui=ui,
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert result["result"] == "skipped_continue_chat"
    assert result["button_before_click"] == "继续沟通"
    assert ui.clicked is False


def test_contact_current_stops_on_paid_contact_button(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = write_fixture(tmp_path / "paid.json", {
        "detail": {
            "front_app": "BOSS直聘",
            "window_title": "陶先生",
            "page_text": "陶先生 上海华为技术有限公司 博士后研究员-大模型方向 搜索畅聊卡 剩余次数不足 立即联系牛人",
            "buttons": ["立即联系牛人"],
        }
    })
    result = boss_contact_executor.contact_current(
        root,
        execute=True,
        ui=boss_contact_executor.FixtureBossUI(fixture),
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert result["result"] == "stopped"
    assert result["stopped_reason"] == "paid_search_chat_card"


def test_contact_current_sent_unverified_when_communication_result_missing(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = write_fixture(tmp_path / "unverified.json", {
        "detail": {
            "front_app": "BOSS直聘",
            "window_title": "陶先生",
            "page_text": "陶先生 上海华为技术有限公司 博士后研究员-大模型方向 立即沟通",
            "buttons": ["立即沟通"],
        },
        "communication": {
            "front_app": "BOSS直聘",
            "window_title": "沟通页",
            "page_text": "沟通页顶部：未知；没有状态",
            "buttons": [],
        },
    })
    result = boss_contact_executor.contact_current(
        root,
        execute=True,
        ui=boss_contact_executor.FixtureBossUI(fixture),
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert result["result"] == "sent_unverified"
    assert result["stopped_reason"] == "communication_result_unverified"


def test_mac_accessibility_ui_reads_snapshot_from_osascript(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    timeouts: list[int] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        calls.append(cmd)
        timeouts.append(timeout)

        class Result:
            stdout = json.dumps({
                "front_app": "BOSS直聘",
                "window_title": "陶先生",
                "texts": ["陶先生", "上海华为技术有限公司", "博士后研究员-大模型方向"],
                "buttons": ["立即沟通"],
            }, ensure_ascii=False)
            stderr = ""

        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)
    ui = boss_contact_executor.MacAccessibilityBossUI()
    snapshot = ui.read_current_page()
    assert snapshot.front_app == "BOSS直聘"
    assert "上海华为技术有限公司" in snapshot.page_text
    assert snapshot.buttons == ["立即沟通"]
    assert calls[0][0] == "osascript"
    assert timeouts == [15]


def test_mac_accessibility_ui_targets_bossz_process_without_recursive_frontmost_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts: list[str] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        script = cmd[-1]
        scripts.append(script)

        class Result:
            stdout = (
                '{"clicked": true, "match_count": 1}'
                if "clicked" in script
                else json.dumps({
                    "front_app": "BOSS直聘",
                    "window_title": "陶先生",
                    "texts": ["陶先生", "上海华为技术有限公司", "博士后研究员-大模型方向"],
                    "buttons": ["立即沟通"],
                }, ensure_ascii=False)
            )
            stderr = ""

        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)
    boss_contact_executor.MacAccessibilityBossUI().read_current_page()
    boss_contact_executor.MacAccessibilityBossUI().click_contact(
        boss_contact_executor.ContactButtonState("立即沟通", 1),
    )

    assert all("BossZP" in script for script in scripts)
    assert all("whose({frontmost" not in script for script in scripts)
    assert "collect(child)" not in scripts[0]


def test_mac_accessibility_ui_falls_back_to_bounded_read_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts: list[str] = []
    timeouts: list[int] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        script = cmd[-1]
        scripts.append(script)
        timeouts.append(timeout)
        if len(scripts) == 1:
            raise subprocess.TimeoutExpired(cmd, timeout=timeout)

        class Result:
            stdout = json.dumps({
                "front_app": "BOSS直聘",
                "window_title": "陶先生",
                "texts": ["陶先生", "上海华为技术有限公司", "博士后研究员-大模型方向"],
                "buttons": ["立即沟通"],
            }, ensure_ascii=False)
            stderr = ""

        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)

    snapshot = boss_contact_executor.MacAccessibilityBossUI().read_current_page()

    assert snapshot.window_title == "陶先生"
    assert timeouts == [15, 5]
    assert "entireContents" in scripts[0]
    assert "entireContents" not in scripts[1]
    assert "uiElements()" in scripts[1]


def test_mac_accessibility_ui_clicks_exact_contact_button(monkeypatch: pytest.MonkeyPatch) -> None:
    scripts: list[str] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        scripts.append(cmd[-1])

        class Result:
            stdout = '{"clicked": true}'
            stderr = ""

        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)
    ui = boss_contact_executor.MacAccessibilityBossUI()
    result = ui.click_contact(boss_contact_executor.ContactButtonState("立即沟通", 1))
    assert result == {"clicked": True}
    assert "立即沟通" in scripts[0]


def test_mac_accessibility_ui_click_script_requires_boss_app_and_single_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts: list[str] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        scripts.append(cmd[-1])

        class Result:
            stdout = '{"clicked": true, "match_count": 1}'
            stderr = ""

        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)
    ui = boss_contact_executor.MacAccessibilityBossUI()
    ui.click_contact(boss_contact_executor.ContactButtonState("立即沟通", 1))

    assert "BossZP" in scripts[0]
    assert "match_count" in scripts[0]
    assert "ambiguous_button_count" in scripts[0]


def test_mac_accessibility_ui_does_not_treat_page_text_button_as_clickable() -> None:
    ui = boss_contact_executor.MacAccessibilityBossUI()
    page = boss_contact_executor.BossPageSnapshot(
        front_app="BOSS直聘",
        window_title="陶先生",
        page_text="陶先生 上海华为技术有限公司 博士后研究员-大模型方向 立即沟通",
        buttons=[],
    )
    button = ui.find_contact_button(page)
    assert button == boss_contact_executor.ContactButtonState("", 0)


def test_mac_accessibility_ui_wait_for_communication_page_raises_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_read(self: boss_contact_executor.MacAccessibilityBossUI) -> boss_contact_executor.BossPageSnapshot:
        return boss_contact_executor.BossPageSnapshot(
            front_app="BOSS直聘",
            window_title="陶先生",
            page_text="陶先生 上海华为技术有限公司 送达",
            buttons=[],
        )

    monkeypatch.setattr(boss_contact_executor.MacAccessibilityBossUI, "read_communication_page_probe", fake_read)
    ui = boss_contact_executor.MacAccessibilityBossUI(poll_seconds=0, max_wait_seconds=0)
    with pytest.raises(ValueError, match="communication page not confirmed"):
        ui.wait_for_communication_page()


def test_mac_accessibility_ui_wait_for_communication_page_retries_transient_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_read(self: boss_contact_executor.MacAccessibilityBossUI) -> boss_contact_executor.BossPageSnapshot:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise subprocess.TimeoutExpired(["osascript"], timeout=15)
        return boss_contact_executor.BossPageSnapshot(
            front_app="BOSS直聘",
            window_title="郭杰",
            page_text="沟通的职位 AI Infra训练与推理研发 求简历 消息状态：送达",
            buttons=["求简历", "换电话/微信"],
        )

    monkeypatch.setattr(boss_contact_executor.MacAccessibilityBossUI, "read_communication_page_probe", fake_read)
    ui = boss_contact_executor.MacAccessibilityBossUI(poll_seconds=0, max_wait_seconds=1)

    page = ui.wait_for_communication_page()

    assert calls == 2
    assert page.window_title == "郭杰"


def test_mac_accessibility_ui_communication_probe_uses_full_read_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts: list[str] = []
    timeouts: list[int] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        scripts.append(cmd[-1])
        timeouts.append(timeout)

        class Result:
            stdout = json.dumps({
                "front_app": "BOSS直聘",
                "window_title": "张女士",
                "texts": ["沟通的职位-AI Infra训练与推理研发", "送达"],
                "buttons": ["求简历", "换电话/微信"],
            }, ensure_ascii=False)
            stderr = ""

        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)

    page = boss_contact_executor.MacAccessibilityBossUI().read_communication_page_probe()

    assert "沟通的职位" in page.page_text
    assert timeouts == [10]
    assert "entireContents" in scripts[0]


def test_mac_accessibility_ui_communication_probe_falls_back_to_bounded_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts: list[str] = []
    timeouts: list[int] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        script = cmd[-1]
        scripts.append(script)
        timeouts.append(timeout)
        if len(scripts) == 1:
            raise subprocess.TimeoutExpired(cmd, timeout=timeout)

        class Result:
            stdout = json.dumps({
                "front_app": "BOSS直聘",
                "window_title": "张女士",
                "texts": ["沟通的职位-AI Infra训练与推理研发", "送达"],
                "buttons": ["求简历", "换电话/微信"],
            }, ensure_ascii=False)
            stderr = ""

        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)

    page = boss_contact_executor.MacAccessibilityBossUI().read_communication_page_probe()

    assert "沟通的职位" in page.page_text
    assert timeouts == [10, 5]
    assert "entireContents" in scripts[0]
    assert "entireContents" not in scripts[1]
    assert "uiElements()" in scripts[1]


def test_mac_accessibility_ui_extract_requires_confirmed_communication_page() -> None:
    ui = boss_contact_executor.MacAccessibilityBossUI()
    page = boss_contact_executor.BossPageSnapshot(
        front_app="BOSS直聘",
        window_title="陶先生",
        page_text="陶先生 上海华为技术有限公司 博士后研究员-大模型方向 送达",
        buttons=[],
    )

    result = ui.extract_communication_result(page)

    assert result.message_status == ""


def test_mac_accessibility_ui_extracts_result_from_confirmed_communication_page() -> None:
    ui = boss_contact_executor.MacAccessibilityBossUI()
    page = boss_contact_executor.BossPageSnapshot(
        front_app="BOSS直聘",
        window_title="陶壮",
        page_text="沟通的职位 博士后研究员-大模型方向 求简历 消息状态：送达",
        buttons=["求简历", "换电话/微信"],
    )

    result = ui.extract_communication_result(page)

    assert result.message_status == "送达"


def test_mac_accessibility_ui_raises_on_invalid_jxa_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        class Result:
            stdout = "not-json"
            stderr = ""

        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)
    ui = boss_contact_executor.MacAccessibilityBossUI()
    with pytest.raises(json.JSONDecodeError):
        ui.read_current_page()


def test_mac_accessibility_ui_propagates_called_process_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        raise boss_contact_executor.subprocess.CalledProcessError(1, cmd, stderr="osascript failed")

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)
    ui = boss_contact_executor.MacAccessibilityBossUI()
    with pytest.raises(boss_contact_executor.subprocess.CalledProcessError):
        ui.read_current_page()


def test_mac_accessibility_ui_propagates_timeout_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        raise boss_contact_executor.subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)
    ui = boss_contact_executor.MacAccessibilityBossUI()
    with pytest.raises(boss_contact_executor.subprocess.TimeoutExpired):
        ui.read_current_page()


def test_mac_accessibility_ui_raises_on_clicked_false(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        class Result:
            stdout = '{"clicked": false, "reason": "ambiguous_button_count", "match_count": 2}'
            stderr = ""

        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)
    ui = boss_contact_executor.MacAccessibilityBossUI()
    with pytest.raises(ValueError, match="ambiguous_button_count"):
        ui.click_contact(boss_contact_executor.ContactButtonState("立即沟通", 1))


def test_contact_current_cli_with_fixture_returns_zero_and_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = ready_fixture(tmp_path)
    exit_code = boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--mock-ui-fixture",
        str(fixture),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])
    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "dry_run_ready"


def test_contact_current_cli_execute_with_fixture_sends(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = ready_fixture(tmp_path)
    exit_code = boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--execute",
        "--mock-ui-fixture",
        str(fixture),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])
    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "sent"


def test_validate_and_summarize_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = ready_fixture(tmp_path)
    boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--execute",
        "--mock-ui-fixture",
        str(fixture),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])
    capsys.readouterr()

    assert boss_contact_executor.main(["validate", "--campaign-root", str(root)]) == 0
    validation = json.loads(capsys.readouterr().out)
    assert validation["status"] == "passed"

    assert boss_contact_executor.main(["summarize", "--campaign-root", str(root)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["sent_count"] == 1


def test_contact_current_cli_front_app_mismatch_returns_ui_stop_exit_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = write_fixture(tmp_path / "wrong-front-app.json", {
        "detail": {
            "front_app": "Safari",
            "window_title": "陶先生",
            "page_text": "陶先生 上海华为技术有限公司 博士后研究员-大模型方向 立即沟通",
            "buttons": ["立即沟通"],
        },
    })

    exit_code = boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--mock-ui-fixture",
        str(fixture),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])

    assert exit_code == 3
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "stopped"
    assert output["stopped_reason"] == "front_app must be BOSS直聘"


def test_contact_current_cli_page_mismatch_returns_ui_stop_exit_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = write_fixture(tmp_path / "page-mismatch.json", {
        "detail": {
            "front_app": "BOSS直聘",
            "window_title": "陶先生",
            "page_text": "陶先生 字节跳动 大模型算法 立即沟通",
            "buttons": ["立即沟通"],
        },
    })

    exit_code = boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--mock-ui-fixture",
        str(fixture),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])

    assert exit_code == 3
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "stopped"
    assert "current_company" in output["stopped_reason"]


def test_contact_current_cli_intent_schema_error_returns_validation_exit_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _ = make_executor_campaign(tmp_path)
    intent = boss_app_sourcing.load_json(root / "state/current-contact-intent.json")
    intent["schema"] = "bad_schema"
    boss_app_sourcing.write_json(root / "state/current-contact-intent.json", intent)

    exit_code = boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--mock-ui-fixture",
        str(ready_fixture(tmp_path)),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])

    assert exit_code == 2
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "stopped"
    assert "current_intent.schema" in output["stopped_reason"]


def test_contact_current_cli_preflight_error_does_not_print_stale_executor_result(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, candidate_key = make_executor_campaign(tmp_path)
    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": "old-intent",
        "campaign_id": root.name,
        "candidate_key": candidate_key,
        "result": "sent",
        "button_before_click": "立即沟通",
        "message_template_id": "boss-current-preset",
        "message_status": "送达",
        "real_name": "旧结果",
        "communication_page_text": "旧沟通页",
    })
    intent = boss_app_sourcing.load_json(root / "state/current-contact-intent.json")
    intent["schema"] = "bad_schema"
    intent["approval_status"] = "pending"
    boss_app_sourcing.write_json(root / "state/current-contact-intent.json", intent)

    exit_code = boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--mock-ui-fixture",
        str(ready_fixture(tmp_path)),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])

    assert exit_code == 2
    output = json.loads(capsys.readouterr().out)
    assert output["schema"] == "boss_executor_result_v1"
    assert output["result"] == "stopped"
    assert output["error_class"] == "ValueError"
    assert "current_intent.schema" in output["stopped_reason"]
    assert output["next_action_for_codex"] == "write_interruption_and_stop"


def test_contact_current_cli_sent_unverified_returns_recovery_exit_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = write_fixture(tmp_path / "sent-unverified.json", {
        "detail": {
            "front_app": "BOSS直聘",
            "window_title": "陶先生",
            "page_text": "陶先生 上海华为技术有限公司 博士后研究员-大模型方向 立即沟通",
            "buttons": ["立即沟通"],
        },
        "communication": {
            "front_app": "BOSS直聘",
            "window_title": "沟通页",
            "page_text": "沟通页顶部：未知；没有状态",
            "buttons": [],
        },
    })

    exit_code = boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--execute",
        "--mock-ui-fixture",
        str(fixture),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])

    assert exit_code == 4
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "sent_unverified"
