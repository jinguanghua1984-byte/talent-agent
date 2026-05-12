---
name: wechat-chat-sync
description: "微信聊天记录手动同步 workflow。用于把指定候选人的指定微信联系人或群聊在明确时间范围内导出为 markdown，并把归档索引写回本地人才库。"
---

# wechat-chat-sync 工作流

`wechat-chat-sync` 是运行时中立的 canonical workflow。它只描述业务编排、安全边界和资源契约；具体运行时必须先读取 `agents/capabilities.md`，再把通用能力映射到当前环境。

## 触发入口

以下意图进入本工作流：

- 同步微信聊天、微信聊天记录、wechat sync、聊天时间线。
- 为指定候选人归档某个微信联系人或群聊的聊天记录。
- 在同步聊天记录时顺带补充候选人的 `email`、`phone`、`wechat` 或 `wechat_id`。

## 前置检查

1. 读取 `agents/capabilities.md`，确认当前运行时具备文件读写、命令执行和人工确认能力。
2. 读取 `agents/workflows/talent-library/AGENT.md`，确认候选人定位和数据库写入边界。
3. 读取 `agents/workflows/wechat-chat-sync/references/cli-contract.md`，确认 `wechat-cli export` 参数、退出码和失败处理。
4. 读取 `agents/workflows/wechat-chat-sync/references/timeline-format.md`，确认 markdown 归档格式和隐私规则。
5. 确认用户提供候选人、微信联系人或群名、起始时间和结束时间。

## 资源索引

| 资源 | 用途 |
| --- | --- |
| `agents/capabilities.md` | 运行时中立能力契约 |
| `agents/workflows/wechat-chat-sync/references/cli-contract.md` | `wechat-cli export` 参数和错误处理 |
| `agents/workflows/wechat-chat-sync/references/timeline-format.md` | markdown 时间线归档格式 |
| `agents/workflows/wechat-chat-sync/assets/timeline-template.md` | 时间线文件头模板 |
| `agents/workflows/talent-library/AGENT.md` | 人才库候选人定位和写库安全规则 |
| `scripts/talent_library.py` | 统一业务入口 |
| `data/wechat-timelines/` | 聊天 markdown 归档目录 |

## 执行流程

1. 用候选人 id 或查询条件定位候选人；命中多条时让用户选择。
2. 展示候选人、微信联系人或群名、起止时间、消息上限和输出目录。
3. 如果用户要求同时更新邮箱、手机号、微信号或微信 id，展示旧值和新值。
4. 调用 `scripts/talent_library.py wechat-sync` 执行导出、归档和索引写入。
5. 输出同步摘要：候选人、聊天名、时间范围、消息数、markdown 路径和索引 id。

## 安全规则

1. 未提供起止时间时不得执行导出；不得默认导出全量聊天。
2. 不在对话中默认展示聊天全文。
3. 不把聊天正文写入 SQLite；SQLite 只保存归档索引。
4. 批量同步多个候选人时必须先展示 dry-run。
5. 删除候选人不隐式删除 markdown 归档文件；删除归档文件必须单独确认。
