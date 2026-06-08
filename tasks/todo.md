# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

### 腾讯游戏多模态算法 BOSS-Maimai 寻访（2026-06-06）

目标：按腾讯游戏多模态算法研究员/专家 JD 建立 BOSS App 寻访 campaign，完成 BOSS 候选采集后再按 BOSS primary、脉脉 supplement 规则做脉脉匹配与交付衔接。

边界：
- BOSS App 浏览、滚屏、进详情、返回列表和详情采集必须使用 Computer Use；当前运行时如果无 Computer Use，写恢复状态后停止，不用 osascript/坐标点击替代。
- 用户已授权本次 campaign 级真实触达；仅在候选人详情判定为 `contact`、`executor-policy.json` 与 `state/current-contact-intent.json` 均通过时，用外部执行器点击当前详情页精确文案 `立即沟通`，不逐人二次确认。
- BOSS 候选未产生前，不启动 BOSS->脉脉身份合并；脉脉匹配只在 BOSS 优质人选清单可追溯后执行。
- 主库写入只在 Campaign DB clean、main-db dry-run clean、备份完成并获得本 campaign 一次总授权后执行；本次已按用户“下一步”授权完成 `data/talent.db` 同步。

待修改/产物：
- `data/campaigns/tencent-games-multimodal-algorithm-boss-maimai-2026-06-06/`
- `tasks/todo.md`

验证方式：
- `.venv/bin/python -m scripts.boss_app_sourcing summarize --campaign-root data/campaigns/tencent-games-multimodal-algorithm-boss-maimai-2026-06-06`
- `.venv/bin/python -m scripts.boss_app_sourcing validate-executor --campaign-root data/campaigns/tencent-games-multimodal-algorithm-boss-maimai-2026-06-06`
- `.venv/bin/python -m scripts.boss_maimai_targets export --campaign-root data/campaigns/tencent-games-multimodal-algorithm-boss-maimai-2026-06-06`
- `.venv/bin/python -m scripts.platform_match.session verify --platform maimai`
- `.venv/bin/python -m pytest tests -q`

检查项：
- [x] 建立 BOSS App 寻访合同和筛选策略。
- [x] 执行 BOSS App 预检；无 Computer Use 时写 continuation plan。
- [x] 用户指出不能只看一屏后，已继续 BOSS 推荐列表滚动寻访；当前累计采集 88 张卡片、34 个详情、22 个 `would_contact`。
- [x] 用户手动证明今日未到沟通上限后，继续执行 BOSS 真实触达；当前 `real_contact_count=22`，其中 19 人已捕获实名、3 人沟通页只暴露昵称。
- [x] 已纠正并记录 `邵嘉闻`；最新一位 `李良驹` 已核验为 `sent`/`送达`，executor 校验通过。
- [x] 继续 BOSS 当前列表寻访，直到真实平台停止条件或沟通上限；BOSS 已在祝先生触达时返回 `该职位今日沟通数已达上限，付费解锁上限`，按付费上限中断，不购买不绕过。
- [x] BOSS 侧完成后重跑脉脉匹配 target 导出；已刷新 `structured/maimai-match-targets.jsonl`，`selected_count=39`、`target_count=33`、`missing_real_name_count=6`。
- [x] 完成脉脉匹配和身份 ledger；`http://127.0.0.1:9888` live gate 已完成 141 个 batch，返回 653 条联系人；用户已复核 11 个 pending identity，当前 33 个 target 中 `auto_bound=2`、`confirmed_bound=8`、`pending_confirmation=0`、`no_match=23`。
- [x] 交付/同步门禁完成；Campaign DB import dry-run/apply clean，主库同步前已备份 `data/talent.db`，main-db dry-run 无 conflicts/skipped/errors，实际新增 7 人、合并 3 人，delivery gates passed，飞书报告/跟进表已发布并向 `JD需求协同` 发送完成通知。

## Open Items

- 猎聘 parity 后续缺口：Campaign DB 到主库同步 handoff 仍只能做 dry-run/report，不得写 `data/talent.db`，真实 apply 需单独确认。
- 猎聘 parity 后续缺口：JD delivery/ranking 与飞书交付是否纳入猎聘寻访默认链路，需要先按 broad-recall summary 与主库同步边界设计。
- 大疆 BG OTD 脉脉寻访仍有历史平台验证码阻断；继续该旧 campaign 前需用户在平台侧处理验证码/安全验证。

## Recent Done

- 2026-06-08：腾讯游戏多模态算法 BOSS-Maimai 寻访完成；BOSS 已沟通 38 人，脉脉匹配 33 个 target 后确认绑定 10 人，主库新增 7 人/合并 3 人，delivery gates passed，飞书报告和跟进表已发布并通知 `JD需求协同`。
- 2026-06-08：BOSS-Maimai cross-channel workflow 已补齐脉脉匹配阶段 CDP Chrome 自动启动、健康门禁、无人值守推进和恢复事实源合同；架构测试 20 passed，全量测试 1380 passed；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-07：rtk CLI 已按 `rtk-ai/rtk` 官方 release 安装到 `/Users/eric/.local/bin/rtk`，版本 `0.42.3`；`rtk gain`、交互式 zsh PATH、Codex 全局 `RTK.md`/`AGENTS.md` 初始化均验证通过；全量测试 1379 passed；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-06：成本治理 P1 已落地只读 `campaign_status summarize` 和 `campaign_orchestrator next-action`，真实 BOSS-Maimai campaign smoke 输出 `next_stage=maimai-match-session`；聚焦测试 11 passed，全量测试 1379 passed；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-06：JD `feedback_note` 解析降本已落地规则优先与批量 LLM fallback，业务侧仍只填写 `feedback_note`；聚焦测试 22 passed，反馈链路测试 63 passed，全量测试 1373 passed；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-06：Claude Code + Codex 协作门禁已固化到 `docs/dev/agent-collaboration-gates.md`、README、capabilities 和架构测试；聚焦测试 19 passed，全量测试 1371 passed；完整记录已归档到 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
