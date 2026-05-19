from pathlib import Path
import json


SKILL = Path("skills/maimai-talent-search-campaign/SKILL.md")
WORKFLOW = Path("agents/workflows/maimai-unattended-campaign/AGENT.md")
OUTREACH_TEMPLATE = Path("templates/maimai-campaign/outreach-queue-fields.json")


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


def test_workflow_keeps_live_safety_boundary_and_resume_sources():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "不自动导航、刷新、点击已进入执行态的脉脉业务页面" in text
    assert "raw/search/unit-" in text
    assert "raw/detail-live/<pack_id>/job-" in text
    assert "state/import-ledger.jsonl" in text
    assert "blocked_notification_failed" in text


def test_outreach_template_has_execution_fields():
    data = json.loads(OUTREACH_TEMPLATE.read_text(encoding="utf-8"))
    names = [field["name"] for field in data["fields"]]
    assert names[:5] == ["owner", "status", "last_touch_at", "next_followup_at", "notes"]
    assert "priority" in names
    assert "recommendation_label" in names
    assert "profile_url" in names
