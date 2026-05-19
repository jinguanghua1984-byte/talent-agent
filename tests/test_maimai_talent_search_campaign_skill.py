from pathlib import Path
import json

from scripts.maimai_ai_infra_outreach_export import CSV_FIELDS


SKILL = Path("skills/maimai-talent-search-campaign/SKILL.md")
WORKFLOW = Path("agents/workflows/maimai-unattended-campaign/AGENT.md")
OUTREACH_TEMPLATE = Path("templates/maimai-campaign/outreach-queue-fields.json")
EXECUTION_FIELDS = ["owner", "status", "last_touch_at", "next_followup_at", "notes"]


def test_skill_extracts_first_and_asks_only_missing_fields():
    text = SKILL.read_text(encoding="utf-8")
    assert "优先从调用提示词、JD、职位描述或粘贴内容中自动抽取" in text
    assert "只对缺失或冲突的信息提问" in text
    assert "冷启动" in text
    assert "关键词包" in text
    assert "停止阈值" in text


def test_skill_bakes_in_confirmed_defaults():
    text = SKILL.read_text(encoding="utf-8")
    assert "每日搜索请求预算：500" in text
    assert "不包括详情请求" in text
    assert "搜索 wave 每组不超过 50 页" in text
    assert "详情 pack 每组上限 100 人" in text
    assert "只对 A/B 档人选抓详情" in text
    assert "本地 Markdown 报告、CSV、飞书云文档、飞书多维表格" in text


def test_skill_declares_output_root_and_run_policy_contract():
    text = SKILL.read_text(encoding="utf-8")
    for token in [
        "data/campaigns/<campaign_id>/",
        "daily_search_request_budget=500",
        "search_wave_max_pages=50",
        "detail_pack_max_contacts=100",
        'detail_target_grades=["A","B"]',
        'notify_channel="feishu_im"',
        "allow_main_db_write=false",
    ]:
        assert token in text


def test_workflow_keeps_live_safety_boundary_and_resume_sources():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "不自动导航、刷新、点击已进入执行态的脉脉业务页面" in text
    assert "raw/search/unit-" in text
    assert "raw/detail-live/<pack_id>/job-" in text
    assert "state/import-ledger.jsonl" in text
    assert "blocked_notification_failed" in text


def test_workflow_declares_stop_conditions_and_status_outputs():
    text = WORKFLOW.read_text(encoding="utf-8")
    for token in [
        "登录页",
        "登录失效",
        "验证码",
        "安全页",
        "403",
        "429",
        "432",
        "非 JSON",
        "HTML 响应",
        "模板漂移",
        "详情 partial capture",
        "reports/interruption-*.json",
        "state/events.jsonl",
        "state/continuation-plan.json",
        "scripts/campaign_notify.py",
    ]:
        assert token in text


def test_outreach_template_has_execution_fields():
    data = json.loads(OUTREACH_TEMPLATE.read_text(encoding="utf-8"))
    assert data["schema"] == "maimai_outreach_queue_fields_v1"

    fields = data["fields"]
    names = [field["name"] for field in fields]
    assert names == EXECUTION_FIELDS + CSV_FIELDS
    assert len(names) == len(set(names))

    by_name = {field["name"]: field for field in fields}
    for field in fields:
        assert field["label"]
        assert field["type"]
        assert isinstance(field["required"], bool)
        assert field["description"]

    for name in EXECUTION_FIELDS:
        assert by_name[name].get("source_field") in (None, "")

    for name in CSV_FIELDS:
        assert by_name[name]["source_field"] == name

    assert by_name["status"]["values"] == ["待联系", "联系中", "已回复", "暂缓", "关闭"]
    assert by_name["priority"]["values"] == ["P0", "P1", "P2", "P3"]
    assert by_name["recommendation_label"]["values"] == ["强推荐", "推荐", "观察", "不推荐"]

    required_names = {field["name"] for field in fields if field["required"]}
    assert required_names == {"owner", "status", *CSV_FIELDS}
    assert by_name["key_evidence"]["required"] is True
    assert by_name["suggested_outreach_angle"]["required"] is True
