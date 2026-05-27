from pathlib import Path


WORKFLOW = Path("agents/workflows/jd-talent-delivery/AGENT.md")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_declares_runtime_neutral_entry_and_resources() -> None:
    text = _text()

    for token in [
        "jd-talent-delivery 工作流",
        "agents/capabilities.md",
        "agents/workflows/talent-library/AGENT.md",
        "agents/workflows/talent-library/references/data-contract.md",
        "agents/workflows/talent-library/references/safety-rules.md",
        "lark-cli",
        "JD需求交付",
    ]:
        assert token in text


def test_workflow_declares_stage_artifacts() -> None:
    text = _text()

    for token in [
        "S0：前置检查",
        "S1：建立输出目录",
        "S2：岗位画像",
        "S3：评分卡",
        "S4：人才库粗筛",
        "S5：人才库精排",
        "S6：报告和外联表",
        "S7：飞书发布",
        "S8：飞书完成通知",
        "data/output/<jd-slug>-<YYYY-MM-DD>/",
        "data/output/<jd-slug>-<YYYY-MM-DD>-run-NNN/",
        "run-manifest.json",
        "output_dir",
    ]:
        assert token in text


def test_workflow_runs_end_to_end_without_intermediate_confirmation() -> None:
    text = _text()

    for token in [
        "输入齐全且所有门禁通过时，必须按 S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 顺序连续执行到完成",
        "阶段成功输出即为进入下一阶段的授权",
        "不得在 S1-S8 之间询问是否继续、是否发布或是否发送通知",
        "dry-run、回读和质量门禁都是自动验证门禁；通过即继续，失败才停止",
    ]:
        assert token in text


def test_workflow_includes_prepare_command_example() -> None:
    text = _text()

    assert (
        "python -m scripts.jd_talent_delivery prepare --jd-path <jd_path> "
        "--output-base data/output --top-n <N>"
    ) in text


def test_workflow_enforces_scorecard_consistency() -> None:
    text = _text()

    for token in [
        "粗筛和精排必须读取同一个 `scoring/scorecard.json`",
        "粗筛不得新增精排不存在的评分维度",
        "精排不得重新解释 JD",
        "维度、权重、阈值必须写入报告",
    ]:
        assert token in text


def test_workflow_declares_independent_match_and_quality_gates() -> None:
    text = _text()

    for token in [
        "不要求存在 campaign `strategy.json`",
        "不要求存在历史 `*rank*.json`",
        "脉脉详情页 URL 必须保留可打开所需的 `trackable_token`",
        "`reports/quality-gates.json`",
        "TopN 全部为 C/淘汰时必须停止发布",
        "CSV 必须可解析且行数等于 TopN",
        "Sheet 回读必须比对本地 CSV 表头和前几行",
        "lark-cli 必须通过 argv list 调用",
        "外联表禁止使用 `drive +import --type sheet`",
        "sheets +create",
        "sheets +write --values <UTF-8 JSON>",
        "回读是验证，不是乱码修复兜底",
    ]:
        assert token in text


def test_workflow_codifies_completion_notification() -> None:
    text = _text()

    for token in [
        "S8：飞书完成通知",
        "im +messages-send",
        "JD需求协同",
        "im +chat-search --as user",
        "--chat-id <chat_id>",
        "任务执行结果",
        "成果物清单",
        "Wiki目录",
        "推荐报告摘要",
        "feishu/im-notification-message.txt",
        "feishu/im-notification-results.json",
        "通知发送失败属于任务失败",
    ]:
        assert token in text


def test_workflow_documents_feedback_collection_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    for token in [
        "feedback/delivery-feedback.json",
        "feedback/feedback-summary.json",
        "feedback/calibration-suggestions.json",
        "反馈导入默认 dry-run",
        "不得写入 data/talent.db",
        "reason_codes",
        "accepted_at_30",
        "actionable_at_30",
    ]:
        assert token in text


def test_workflow_does_not_require_second_confirmation_after_publish_dry_run() -> None:
    text = _text()

    for token in [
        "dry-run 成功后必须直接执行真实发布",
        "不得要求人工二次确认",
        "发布成功并回读通过后继续 S8",
    ]:
        assert token in text


def test_workflow_enforces_safety_and_stop_conditions() -> None:
    text = _text()

    for token in [
        "`data/talent.db` 只读",
        "不写 `match_scores`",
        "不上传 SQLite DB",
        "不上传 sync zip",
        "不上传 raw search",
        "不上传 raw detail",
        "不上传 raw capture",
        "不自动追加 `--yes`",
        "认证失败",
        "权限不足",
        "scope 缺失",
        "dry-run 失败",
        "外联表发布步骤出现 `drive +import --type sheet`",
        "飞书完成通知发送失败",
    ]:
        assert token in text
