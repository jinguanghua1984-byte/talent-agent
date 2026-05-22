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
        "data/output/<jd-slug>-<YYYY-MM-DD>/",
    ]:
        assert token in text


def test_workflow_enforces_scorecard_consistency() -> None:
    text = _text()

    for token in [
        "粗筛和精排必须读取同一个 `scoring/scorecard.json`",
        "粗筛不得新增精排不存在的评分维度",
        "精排不得重新解释 JD",
        "维度、权重、阈值必须写入报告",
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
    ]:
        assert token in text
