# Shared Agent Policies

这些 policy 是运行时中立的 cross-workflow 安全合同。`agents/workflows/*/AGENT.md` 应在资源索引中引用需要的 policy，并只保留本 workflow 特有阶段、命令和产物。

| Policy | 用途 |
| --- | --- |
| `agents/policies/platform-automation-safety.md` | 平台自动化、Computer Use、CDP、外部执行器和平台阻断停机边界 |
| `agents/policies/main-db-sync-gates.md` | Campaign DB 到主库 `data/talent.db` 的 dry-run/apply 门禁 |
| `agents/policies/feishu-publish-gates.md` | 飞书 dry-run、发布、回读和 IM 完成通知门禁 |
| `agents/policies/campaign-recovery.md` | 中断证据、continuation plan、磁盘事实源和下一步判断 |
