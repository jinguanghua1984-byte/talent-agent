from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = [
    "public-search",
    "platform-match",
    "screen",
    "report",
    "talent-library",
    "wechat-chat-sync",
    "jd-talent-delivery",
    "maimai-unattended-campaign",
    "boss-app-recommendation-sourcing",
    "liepin-unattended-campaign",
]

CANONICAL_SKILL_WORKFLOWS = {
    "jd-talent-delivery": "jd-talent-delivery",
    "maimai-talent-search-campaign": "maimai-unattended-campaign",
    "boss-app-recommendation-sourcing": "boss-app-recommendation-sourcing",
    "liepin-talent-search-campaign": "liepin-unattended-campaign",
}

CLAUDE_ADAPTER_WORKFLOWS = {
    "public-search": "public-search",
    "platform-match": "platform-match",
    "screen": "screen",
    "report": "report",
    "talent-library": "talent-library",
    "wechat-chat-sync": "wechat-chat-sync",
    "jd-talent-delivery": "jd-talent-delivery",
    "maimai-talent-search-campaign": "maimai-unattended-campaign",
    "boss-app-recommendation-sourcing": "boss-app-recommendation-sourcing",
    "liepin-talent-search-campaign": "liepin-unattended-campaign",
}


def markdown_section(text: str, heading: str) -> str:
    marker = f"### {heading}"
    start = text.index(marker)
    next_heading = text.find("\n### ", start + len(marker))
    if next_heading == -1:
        return text[start:]
    return text[start:next_heading]


def test_canonical_workflow_files_exist():
    for name in WORKFLOWS:
        path = ROOT / "agents" / "workflows" / name / "AGENT.md"
        assert path.exists(), f"missing canonical workflow: {path}"
        text = path.read_text(encoding="utf-8")
        assert f"name: {name}" in text
        assert "## 触发入口" in text or "## 触发" in text


def test_canonical_workflows_do_not_reference_runtime_private_paths():
    forbidden = [
        ".claude/skills",
        "Claude Code",
        "Claude 在内存",
        "Claude 解析",
        "Claude 抽象",
        "WebSearch",
        "mcp__",
        "`Read`",
        "`Write`",
        "`Bash`",
    ]
    for name in WORKFLOWS:
        path = ROOT / "agents" / "workflows" / name / "AGENT.md"
        text = path.read_text(encoding="utf-8")
        hits = [word for word in forbidden if word in text]
        assert hits == [], f"{path} contains runtime-specific terms: {hits}"


def test_runtime_neutral_skill_contracts_live_under_agents():
    for skill_name, workflow_name in CANONICAL_SKILL_WORKFLOWS.items():
        path = ROOT / "agents" / "skills" / skill_name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        assert f"name: {skill_name}" in text
        assert f"agents/workflows/{workflow_name}/AGENT.md" in text
        assert "## 目标" in text

    assert not (ROOT / "skills").exists()


def test_claude_skill_files_are_adapters_to_canonical_workflows():
    for name, workflow_name in CLAUDE_ADAPTER_WORKFLOWS.items():
        path = ROOT / ".claude" / "skills" / name / "SKILL.md"
        assert path.exists(), f"missing Claude adapter: {path}"
        text = path.read_text(encoding="utf-8")
        assert f"agents/workflows/{workflow_name}/AGENT.md" in text
        assert "Claude Code Adapter" in text
        assert "## Adapter Steps" in text
        assert "agents/capabilities.md" in text
        assert "运行时私有入口" in text
        if name in CANONICAL_SKILL_WORKFLOWS:
            assert f"agents/skills/{name}/SKILL.md" in text


def test_readme_describes_runtime_neutral_architecture():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "运行时中立" in text
    assert "agents/skills/" in text
    assert "agents/workflows/" in text
    assert ".claude/skills/ — Claude Code 兼容适配器" in text


def test_env_example_uses_generic_llm_settings():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "LLM_PROVIDER=" in text
    assert "LLM_MODEL=" in text
    assert "LLM_API_KEY=" in text
    assert "ANTHROPIC_API_KEY" in text


def test_capabilities_include_local_app_operations():
    text = (ROOT / "agents" / "capabilities.md").read_text(encoding="utf-8")
    assert "`computer.operate`" in text
    assert "本地 App" in text


def test_boss_app_sourcing_contracts_define_contact_audit_gates():
    skill = (
        ROOT
        / "agents"
        / "skills"
        / "boss-app-recommendation-sourcing"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "boss-app-recommendation-sourcing"
        / "AGENT.md"
    ).read_text(encoding="utf-8")
    s6b = markdown_section(workflow, "S6b live-test 真实沟通")
    s6c = markdown_section(workflow, "S6c 人工已沟通页面回采")

    for text in (skill, workflow):
        assert "`allow_real_contact=true`" in text
        assert "`allow_live_contact_test=true`" in text
        assert "默认" in text
        assert "不点击" in text

    assert "`allow_real_contact=true`" in s6b
    assert "`allow_live_contact_test=true`" in s6b
    assert "`live_contact_test_limit`" in s6b
    assert "`human.confirm`" in s6b
    assert "动作级确认" in s6b
    assert "自动发送预设消息" in s6b
    assert "`raw/communication-pages.jsonl`" in s6b
    assert "`structured/contact-decisions.jsonl`" in s6b
    assert "`structured/candidates.jsonl`" in s6b
    assert "real_name_source=communication_page_after_live_contact_test" in s6b

    assert "`raw/communication-pages.jsonl`" in s6c
    assert "`structured/contact-decisions.jsonl`" in s6c
    assert "`structured/candidates.jsonl`" in s6c
    assert "real_name_source=manual_opened_communication_page" in s6c
    assert "不发送新消息" in s6c

    assert "`reports/interruption-<stage>-<reason>-<timestamp>.json`" in workflow
    assert "`state/continuation-plan.json`" in workflow
    assert "`state/events.jsonl`" in workflow


def test_boss_app_sourcing_contracts_define_external_executor_handoff():
    skill = (
        ROOT
        / "agents"
        / "skills"
        / "boss-app-recommendation-sourcing"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "boss-app-recommendation-sourcing"
        / "AGENT.md"
    ).read_text(encoding="utf-8")
    s6 = workflow.index("### S6 沟通 dry-run")
    s6a = workflow.index("### S6a 外部执行器 handoff")
    s6b = workflow.index("### S6b live-test 真实沟通")
    s6a_text = markdown_section(workflow, "S6a 外部执行器 handoff")
    s6b_text = markdown_section(workflow, "S6b live-test 真实沟通")

    assert s6 < s6a < s6b

    for text in (skill, workflow):
        assert "`structured/approved-contact-queue.jsonl`" in text
        assert "`state/current-contact-intent.json`" in text
        assert "`state/executor-result.json`" in text
        assert "`executor-policy.json`" in text
        assert "外部执行器" in text
        assert "Codex" in text
        assert "campaign 级" in text
        assert "不再逐人" in text

    for artifact in [
        "`structured/approved-contact-queue.jsonl`",
        "`state/current-contact-intent.json`",
        "`state/executor-result.json`",
        "`raw/executor-contact-attempts.jsonl`",
        "`reports/executor-summary.md`",
        "`reports/executor-summary.json`",
    ]:
        assert artifact in s6a_text

    assert "contact-current" in s6a_text
    assert "用户" in s6a_text
    assert "`--execute`" in s6a_text
    assert "macOS Accessibility" in s6a_text
    assert "`shell.run`" in s6a_text
    assert "不再逐人二次确认" in s6a_text
    assert "`executor-policy.json`" in s6a_text
    assert "`max_contacts_per_run=1`" in s6a_text
    assert "Computer Use 定位" in s6a_text
    assert "不交给执行器翻列表或找人" in s6a_text
    assert "不能由 `computer.operate` 直接点击" in s6a_text
    assert "列表遍历、详情采集、候选筛选或翻页" in workflow

    assert "`allow_live_contact_test=true`" in s6b_text
    assert "`human.confirm`" in s6b_text
    assert "动作级确认" in s6b_text


def test_liepin_contracts_define_broad_recall_adaptive_planning_boundary():
    skill = (
        ROOT
        / "agents"
        / "skills"
        / "liepin-talent-search-campaign"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "liepin-unattended-campaign"
        / "AGENT.md"
    ).read_text(encoding="utf-8")

    assert "liepin_broad_recall_adaptive_v1" in skill
    assert "plan-adaptive-search" in skill
    assert "不触发猎聘请求" in skill
    assert "liepin_broad_recall_adaptive_v1" in workflow
    assert "plan-adaptive-search" in workflow
    assert "run-live-adaptive-search" in workflow
    assert "standardize-adaptive-search" in skill
    assert "standardize-adaptive-search" in workflow
    assert "broad-recall-summary" in skill
    assert "broad-recall-summary" in workflow
    assert "raw/search-adaptive" in skill
    assert "reports/page-quality-<wave_id>.jsonl" in skill
    assert "state/adaptive-unit-state-<wave_id>.json" in skill
    assert "全终止" in workflow
    assert "不得连接 CDP" in workflow
    assert "main-db-sync-handoff" in skill
    assert "main-db-sync-handoff" in workflow
    assert "不得自动执行主库同步" in workflow
    assert "jd-talent-delivery" in skill
    assert "jd-talent-delivery" in workflow
    assert "不写数据库" in workflow


def test_boss_app_sourcing_capability_exception_keeps_executor_narrow():
    capabilities = (ROOT / "agents" / "capabilities.md").read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "boss-app-recommendation-sourcing"
        / "AGENT.md"
    ).read_text(encoding="utf-8")

    assert "窄例外" in capabilities
    assert "`shell.run` 可调用受 policy、intent、lock、stop 条件约束的执行器" in capabilities
    assert "不能替代 `computer.operate` 做浏览、筛选或上下文判断" in capabilities
    assert "执行器只处理当前详情页的一次 `立即沟通` 点击" in workflow


def test_liepin_contracts_define_detail_smoke_boundary():
    skill = (
        ROOT
        / "agents"
        / "skills"
        / "liepin-talent-search-campaign"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "liepin-unattended-campaign"
        / "AGENT.md"
    ).read_text(encoding="utf-8")

    for text in (skill, workflow):
        assert "详情 smoke" in text
        assert "detail_p0" in text
        assert "上限 20" in text
        assert "不写 Campaign DB" in text
        assert "不写主库" in text
        assert "data/talent.db" in text
        assert "推荐报告" in text
        assert "外联队列" in text
        assert "飞书交付包" in text
        assert "不触发猎聘请求" in text
        assert "detail-dry-run" in text
        assert "import-search-dry-run" in text
        assert "import-search-apply" in text
        assert "确认写入猎聘搜索结果" in text
        assert "detail-apply" in text
        assert "确认写入猎聘详情" in text
        assert "campaign-summary" in text
        assert "reports/campaign-summary.json" in text
        assert "plan-detail-packs" in text
        assert "run-live-detail-pack" in text
        assert "detail-pack-<pack_id>-summary.json" in text
        assert "detail_pack_already_terminal" in text
        assert "raw/detail-targets/detail-targets-<scope>.json" in text
        assert "raw/detail-live/<pack_id>/job-*.json" in text
        assert "calibrate-detail-api" in text
        for stop_marker in [
            "登录",
            "验证码",
            "401",
            "403",
            "429",
            "432",
            "非 JSON",
            "partial capture",
        ]:
            assert stop_marker in text
        assert "安全页" in text or "安全验证" in text

    assert "plan-detail-smoke" in workflow
    assert "run-live-detail-smoke" in workflow
    assert "calibrate-detail-api" in workflow
    assert "raw/detail-live/<pack_id>/job-*.json" in workflow
    assert "state/detail-request-ledger.jsonl" in workflow
    assert "reports/detail-dry-run.json" in workflow
    assert "reports/search-import-dry-run.json" in workflow
    assert "state/import-ledger.jsonl" in workflow
    assert "candidate_details" in workflow
    assert "不是推荐报告" in workflow
    assert "Full detail pack planning" in workflow
    assert "后续 live detail 扩大执行必须另起确认点" in workflow
    assert "Full detail live execution recovery" in workflow
    assert "全部 target 已经是 terminal job 时不得连接 CDP" in workflow
