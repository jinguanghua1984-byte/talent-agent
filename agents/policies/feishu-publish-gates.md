# Feishu Publish Gates Policy

## 适用范围

适用于需要通过 `lark-cli` 发布 Docs、Sheets、Drive、Wiki 或发送飞书 IM 通知的 workflow。

## 发布前门禁

- workflow 必须声明自己的发布空间、知识库位置、文档/表格目标和通知目标；policy 不提供全局默认空间或群。
- 发布前必须执行对应 manifest dry-run，确认只引用本次任务的报告、表格、quality gates 和输出目录。
- 发布前必须校验 `lark-cli doctor`、`lark-cli auth status` 和所需 Docs/Sheets/Wiki/IM scope。
- 包含中文 JSON payload 的命令必须使用 UTF-8 argv runner，不得把 JSON、中文或 URL 拼成 PowerShell 字符串。

## 发布和回读

飞书发布后必须回读 Wiki 节点、Doc outline、Sheet 表头和前几行。回读是验证，不是乱码修复兜底；如果回读不一致，视为发布失败，必须修正发布器或 manifest。

## IM 完成通知

飞书发布和回读通过后，必须按 workflow 声明发送 IM 完成通知。JD delivery 和 BOSS-Maimai 的默认或常用目标可以是 `JD需求交付` 与 `JD需求协同`；脉脉等 campaign 的通知目标可以来自 run-policy 的 `notify_chat_id`、`notify_user_id` 或 workflow 显式参数。默认命令形态为 `im +chat-search` 和 `im +messages-send`。通知正文、发送结果和回读证据必须写入 `feishu/im-notification-results.json` 或 workflow 指定的等价产物。

## 通知失败

通知失败不得改变业务执行结果，但不得把任务误报为完整关闭。通知失败状态必须写为 `blocked_notification_failed`，并记录可恢复的通知重试入口。
