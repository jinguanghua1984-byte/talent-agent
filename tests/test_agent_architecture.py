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
    "boss-maimai-cross-channel-delivery",
    "liepin-unattended-campaign",
]

CANONICAL_SKILL_WORKFLOWS = {
    "jd-talent-delivery": "jd-talent-delivery",
    "maimai-talent-search-campaign": "maimai-unattended-campaign",
    "boss-app-recommendation-sourcing": "boss-app-recommendation-sourcing",
    "boss-maimai-cross-channel-delivery": "boss-maimai-cross-channel-delivery",
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
    "boss-maimai-cross-channel-delivery": "boss-maimai-cross-channel-delivery",
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
    assert "任务级授权边界" in text
    assert "agents/policies/feishu-publish-gates.md" in text
    assert "dry-run 与回读通过后的发布/通知链路不再逐动作 `human.confirm`" in text


def test_agent_collaboration_gates_document_defines_tool_boundaries():
    path = ROOT / "docs" / "dev" / "agent-collaboration-gates.md"
    text = path.read_text(encoding="utf-8")

    for marker in [
        "# Claude Code + Codex 协作门禁",
        "## 默认分工",
        "## 启动前主执行者门禁",
        "## 写入隔离",
        "## 共享事实源",
        "## 外部副作用门禁",
        "## 合并前记录",
    ]:
        assert marker in text

    assert "同一轮代码修改只指定一个工具负责最终落地" in text
    assert "Claude Code" in text
    assert "长上下文项目理解" in text
    assert "跨目录规划" in text
    assert "安全门禁" in text
    assert "最终合并前审查" in text
    assert "Codex" in text
    assert "局部脚本实现" in text
    assert "单文件/少文件" in text
    assert "测试失败修复" in text
    assert "确定性脚本" in text
    assert "状态摘要" in text
    assert "schema 校验" in text
    assert "成本 dry-run" in text


def test_agent_collaboration_gates_require_isolation_artifacts_and_merge_evidence():
    text = (ROOT / "docs" / "dev" / "agent-collaboration-gates.md").read_text(
        encoding="utf-8"
    )

    for required in [
        "branch / worktree",
        "不得让两个 agent 同时改同一目录",
        "同一 migration",
        "同一 workflow 文档",
        "同一 DB 写入脚本",
        "`tasks/todo.md`",
        "`tasks/archive/`",
        "campaign `state` / `ledger` / `reports`",
        "`data/talent.db`",
        "dry-run/apply 报告",
        "`LLMUsageLedger`",
        "campaign_status summarize",
        "next-action",
        "目标",
        "已改文件",
        "剩余风险",
        "验证命令",
        "禁止事项",
        "下一步合法命令",
    ]:
        assert required in text

    assert "主库同步" in text
    assert "Campaign DB apply" in text
    assert "飞书发布" in text
    assert "外部平台沟通" in text
    assert "只认项目脚本和人工授权" in text
    assert "哪个工具改了哪些文件" in text
    assert "是否有未解决风险" in text


def test_readme_and_capabilities_point_to_collaboration_gates():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    capabilities = (ROOT / "agents" / "capabilities.md").read_text(encoding="utf-8")

    assert "docs/dev/agent-collaboration-gates.md" in readme
    assert "Claude Code + Codex 协作门禁" in readme
    assert "docs/dev/agent-collaboration-gates.md" in capabilities
    assert "主执行者" in capabilities
    assert "共享事实源" in capabilities


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


def test_boss_app_sourcing_contracts_lock_computer_use_browsing_boundary():
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

    for text in (skill, workflow):
        assert "浏览、滚屏、进详情、返回列表、展开详情" in text
        assert "全部使用 Computer Use" in text
        assert "只有" in text
        assert "立即沟通" in text
        assert "外部执行器" in text
        assert "不得使用 osascript" in text
        assert "坐标点击" in text

    assert "Computer Use 缺失" in workflow
    assert "state/continuation-plan.json" in workflow


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


def test_boss_maimai_cross_channel_contracts_define_merge_and_sync_gates():
    skill = (
        ROOT
        / "agents"
        / "skills"
        / "boss-maimai-cross-channel-delivery"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "boss-maimai-cross-channel-delivery"
        / "AGENT.md"
    ).read_text(encoding="utf-8")
    s3 = markdown_section(workflow, "S3 身份匹配判定")
    s9 = markdown_section(workflow, "S9 主库 sync dry-run 与 apply")

    for text in (skill, workflow):
        assert "BOSS 为 primary" in text
        assert "脉脉为 supplement" in text
        assert "`structured/maimai-match-targets.jsonl`" in text
        assert "`state/cross-channel-identity-ledger.jsonl`" in text
        assert "`reports/main-db-sync-dry-run.json`" in text
        assert "`reports/boss-maimai-delivery-report.json`" in text
        assert "`reports/boss-maimai-delivery-report.md`" in text
        assert "`reports/boss-maimai-follow-up-queue.csv`" in text
        assert "`reports/boss-maimai-follow-up-queue.md`" in text
        assert "`reports/boss-maimai-delivery-quality-gates.json`" in text
        assert "`feishu/boss-maimai-delivery-manifest.json`" in text
        assert "`feishu/im-notification-message.txt`" in text
        assert "`feishu/im-notification-results.json`" in text
        assert "`state/boss-maimai-delivery-handoff.json`" in text
        assert "`data/talent.db`" in text
        assert "一次总授权" in text
        assert "Campaign DB clean" in text
        assert "`JD需求协同`" in text
        assert "`im +messages-send`" in text

    assert "不默认交接 `jd-talent-delivery`" in skill
    assert "`feishu/boss-maimai-delivery-manifest.json`" in skill
    assert "旧 Top30 飞书包保持不动" in skill
    assert "后续独立任务" in skill

    assert "`name_company_title`" in s3
    assert "`name_company_fallback`" in s3
    assert ">=95" in s3
    assert "不得自动绑定" in s3
    assert "`pending_confirmation`" in s3

    assert "`talent_sync.py export`" in s9
    assert "`verify-bundle`" in s9
    assert "`talent_sync.py import`" in s9
    assert "`CONFIRM_SYNC_TEXT`" in s9


def test_boss_maimai_cross_channel_s10_is_campaign_delivery_not_jd_default():
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "boss-maimai-cross-channel-delivery"
        / "AGENT.md"
    ).read_text(encoding="utf-8")
    heading = "S10 BOSS campaign delivery / 飞书交付"

    assert f"### {heading}" in workflow
    s10 = markdown_section(workflow, heading)
    assert (
        "scripts.boss_maimai_campaign_delivery build --campaign-root <campaign_root>"
        in s10
    )
    assert "--main-db data/talent.db" in s10
    assert (
        "scripts.boss_maimai_campaign_delivery manifest --campaign-root "
        "<campaign_root> --dry-run"
    ) in s10
    assert "feishu/boss-maimai-delivery-manifest.json" in s10
    assert "feishu/im-notification-message.txt" in s10
    assert "feishu/im-notification-results.json" in s10
    assert "JD需求交付" in s10
    assert "drive +import --type docx" in s10
    assert "sheets +create" in s10
    assert "sheets +append" in s10
    assert "readback_expectations" in s10
    assert "BOSS寻访交付报告" in s10
    assert "BOSS跟进表" in s10
    assert "Wiki/Doc/Sheet" in s10
    assert "无法挂到目标知识库" in s10
    assert "无法回读" in s10
    assert "S10 停止" in s10
    assert "reports/boss-maimai-delivery-quality-gates.json" in s10
    assert "follow_up_row_count == real_contact_count" in s10
    assert "飞书发布和回读通过后" in s10
    assert "im +chat-search --as user" in s10
    assert "im +messages-send --as user" in s10
    assert "JD需求协同" in s10
    assert "旧 Top30 飞书包保持不动" in s10
    assert "jd-talent-delivery" not in s10


def test_boss_maimai_cross_channel_contract_mentions_alias_and_school_fallback_safety():
    skill = (
        ROOT
        / "agents"
        / "skills"
        / "boss-maimai-cross-channel-delivery"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "boss-maimai-cross-channel-delivery"
        / "AGENT.md"
    ).read_text(encoding="utf-8")
    combined = skill + "\n" + workflow

    assert "name_company_alias" in combined
    assert "name_school_fallback" in combined
    assert "不得自动绑定" in combined
    assert "BOSS 为 primary" in combined


def test_boss_maimai_cross_channel_reuses_maimai_cdp_unattended_contract():
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "boss-maimai-cross-channel-delivery"
        / "AGENT.md"
    ).read_text(encoding="utf-8")

    for token in [
        "agents/workflows/maimai-unattended-campaign/AGENT.md",
        "auto_bootstrap_browser_after_plan_confirmation=true",
        "确认后不得提示负责人手动启动浏览器",
        "data/session/maimai-cdp-profile",
        "extensions/maimai-scraper",
        "--remote-debugging-port=9888",
        "http://127.0.0.1:9888",
        "只等待登录/验证码/人才银行页健康条件",
        "raw/maimai-match-search/<target_id>/query-*.json",
        "state/continuation-plan.json",
        "state/import-ledger.jsonl",
        "blocked_notification_failed",
    ]:
        assert token in workflow

    assert "不得要求 Campaign DB clean dry-run 后再次人工确认" in workflow
    assert "主库写入不包含在无人值守授权内" in workflow


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


POLICY_CONTRACTS = {
    "platform-automation-safety": [
        "Computer Use",
        "外部执行器",
        "不得使用 osascript",
        "坐标点击",
        "CDP",
        "登录",
        "验证码",
        "安全页",
        "state/continuation-plan.json",
    ],
    "main-db-sync-gates": [
        "Campaign DB",
        "`data/talent.db`",
        "`talent_sync.py export`",
        "`verify-bundle`",
        "`talent_sync.py import`",
        "`CONFIRM_SYNC_TEXT`",
        "确认同步人才库",
        "一次总授权",
        "不得自动执行主库同步",
    ],
    "feishu-publish-gates": [
        "lark-cli",
        "dry-run",
        "回读",
        "`JD需求交付`",
        "`JD需求协同`",
        "`im +chat-search`",
        "`im +messages-send`",
        "`feishu/im-notification-results.json`",
        "blocked_notification_failed",
    ],
    "campaign-recovery": [
        "`reports/interruption-*.json`",
        "`state/continuation-plan.json`",
        "`state/events.jsonl`",
        "`state/request-ledger.jsonl`",
        "磁盘事实",
        "campaign_status summarize",
        "next-action",
        "不得盲信内存上下文",
    ],
}


def test_shared_policy_files_define_reusable_contracts():
    for name, required_tokens in POLICY_CONTRACTS.items():
        path = ROOT / "agents" / "policies" / f"{name}.md"
        assert path.exists(), f"missing shared policy: {path}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# ")
        for token in required_tokens:
            assert token in text, f"{path} missing policy token: {token}"


WORKFLOW_POLICY_REFERENCES = {
    "boss-maimai-cross-channel-delivery": [
        "agents/policies/platform-automation-safety.md",
        "agents/policies/main-db-sync-gates.md",
        "agents/policies/feishu-publish-gates.md",
        "agents/policies/campaign-recovery.md",
    ],
    "jd-talent-delivery": [
        "agents/policies/main-db-sync-gates.md",
        "agents/policies/feishu-publish-gates.md",
        "agents/policies/campaign-recovery.md",
    ],
    "liepin-unattended-campaign": [
        "agents/policies/platform-automation-safety.md",
        "agents/policies/main-db-sync-gates.md",
        "agents/policies/campaign-recovery.md",
    ],
    "maimai-unattended-campaign": [
        "agents/policies/platform-automation-safety.md",
        "agents/policies/main-db-sync-gates.md",
        "agents/policies/feishu-publish-gates.md",
        "agents/policies/campaign-recovery.md",
    ],
}


def test_workflows_reference_shared_policies_for_reused_gates():
    for workflow_name, required_refs in WORKFLOW_POLICY_REFERENCES.items():
        workflow = (
            ROOT / "agents" / "workflows" / workflow_name / "AGENT.md"
        ).read_text(encoding="utf-8")
        for ref in required_refs:
            assert ref in workflow, f"{workflow_name} missing shared reference {ref}"


WORKFLOW_LINE_BUDGETS = {
    "boss-maimai-cross-channel-delivery": 190,
    "jd-talent-delivery": 215,
    "liepin-unattended-campaign": 265,
    "public-search": 260,
}


def test_compressed_workflows_stay_within_line_budgets():
    for workflow_name, max_lines in WORKFLOW_LINE_BUDGETS.items():
        path = ROOT / "agents" / "workflows" / workflow_name / "AGENT.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= max_lines, f"{workflow_name} has {len(lines)} lines"


def test_public_search_commands_reference_preserves_execution_contract():
    workflow = (
        ROOT / "agents" / "workflows" / "public-search" / "AGENT.md"
    ).read_text(encoding="utf-8")
    commands = (
        ROOT / "agents" / "workflows" / "public-search" / "commands.md"
    ).read_text(encoding="utf-8")

    assert "agents/workflows/public-search/commands.md" in workflow
    for token in [
        "Token Tracker",
        "scripts/public_search/token_tracker.py",
        "data/token-tracker/tokens.jsonl",
        "搜索反馈",
        "迭代循环",
        "策略沉淀",
        "放弃记录",
    ]:
        assert token in commands
