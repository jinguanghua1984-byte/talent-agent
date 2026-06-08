# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

无。

## Open Items

- 猎聘 parity 后续缺口：Campaign DB 到主库同步 handoff 仍只能做 dry-run/report，不得写 `data/talent.db`，真实 apply 需单独确认。
- 猎聘 parity 后续缺口：JD delivery/ranking 与飞书交付是否纳入猎聘寻访默认链路，需要先按 broad-recall summary 与主库同步边界设计。
- 大疆 BG OTD 脉脉寻访仍有历史平台验证码阻断；继续该旧 campaign 前需用户在平台侧处理验证码/安全验证。

## Recent Done

- 2026-06-08：阿里 paper 脉脉人工确认包已推送飞书 `JD需求交付` 并通知 `JD需求协同`；Docx `https://sq8org1v4k6.feishu.cn/wiki/QVviwGQVlit7VikCoaucVqKKnec`，可编辑确认表 `https://sq8org1v4k6.feishu.cn/wiki/YwqQwM7xmi8LcVkZSXMcUVmpnP5`，Sheet 写入 79 行/16 列，IM message_id=`om_x100b6d531802d500b04e5b61bba5e75`；未写主库、未执行身份绑定，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-08：飞书 `阿里 paper` 238 条线索已完成脉脉无人值守匹配；生成 232 个 target、跳过 6 条缺姓名记录，中文首轮 232/232、拼音 fallback 223/223，累计 1275 条 raw contacts；最终为 78 个 `pending_confirmation`、150 个 `no_match_after_pinyin_fallback`、4 个无可用 fallback 的 `no_match`，0 个 auto-bound，未写 `data/talent.db`；最终报告位于 `data/campaigns/feishu-ali-paper-maimai-leads-20260608/reports/final-identity-confirmation.md`，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-08：`MYCC 内测围观群` 最近 7 天 normal 版群聊精华已生成；`wx history` 拉取 3520 条消息、非系统消息 3486 条，摘要、history、JSONL 和 63 份 profiles 已写入 `wechat/46015533484@chatroom-MYCC 内测围观群/`；未发现未脱敏 `sk-` 密钥；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-08：腾讯游戏多模态算法 BOSS-Maimai 寻访完成；BOSS 已沟通 38 人，脉脉匹配 33 个 target 后确认绑定 10 人，主库新增 7 人/合并 3 人，delivery gates passed，飞书报告和跟进表已发布并通知 `JD需求协同`。
- 2026-06-08：BOSS-Maimai cross-channel workflow 已补齐脉脉匹配阶段 CDP Chrome 自动启动、健康门禁、无人值守推进和恢复事实源合同；架构测试 20 passed，全量测试 1380 passed；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-07：rtk CLI 已按 `rtk-ai/rtk` 官方 release 安装到 `/Users/eric/.local/bin/rtk`，版本 `0.42.3`；`rtk gain`、交互式 zsh PATH、Codex 全局 `RTK.md`/`AGENTS.md` 初始化均验证通过；全量测试 1379 passed；完整记录已归档到 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
