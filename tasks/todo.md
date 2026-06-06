# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

### rtk CLI 安装与 Codex 初始化（2026-06-07）

目标：阅读 `rtk-ai/rtk` 官方说明，在本机安装正确的 Rust Token Killer CLI，并为 Codex 初始化可验证配置。

边界：
- 优先使用官方推荐安装方式；必须用 `rtk gain` 排除同名错误包。
- 初始化只写 rtk/Codex 所需配置，不改动本仓库业务代码和数据库。
- 遥测保持默认未启用；不保存或记录任何令牌、设备码或账号密钥。
- 现有 BOSS-Maimai Active Task 保留，不因本次安装任务回退或改写。

待修改/产物：
- `tasks/todo.md`
- rtk 安装路径和初始化生成的本机配置文件

验证方式：
- `rtk --version`
- `rtk gain`
- `rtk init -g --codex`
- `rtk init --show`
- `zsh -ic 'command -v rtk && rtk --version'`

检查项：
- [x] 确认本机此前没有可用 `rtk` 命令。
- [x] 阅读官方 README/INSTALL 并确认安装与 Codex 初始化方式。
- [ ] 安装 rtk 并验证 `rtk gain` 可用。
- [ ] 为 Codex 执行初始化配置并验证生成内容。
- [ ] 写入简短 Review，并将完整记录归档。

### 腾讯游戏多模态算法 BOSS-Maimai 寻访（2026-06-06）

目标：按腾讯游戏多模态算法研究员/专家 JD 建立 BOSS App 寻访 campaign，完成 BOSS 候选采集后再按 BOSS primary、脉脉 supplement 规则做脉脉匹配与交付衔接。

边界：
- BOSS App 浏览、滚屏、进详情、返回列表和详情采集必须使用 Computer Use；当前运行时如果无 Computer Use，写恢复状态后停止，不用 osascript/坐标点击替代。
- 用户已授权本次 campaign 级真实触达；仅在候选人详情判定为 `contact`、`executor-policy.json` 与 `state/current-contact-intent.json` 均通过时，用外部执行器点击当前详情页精确文案 `立即沟通`，不逐人二次确认。
- BOSS 候选未产生前，不启动 BOSS->脉脉身份合并；脉脉匹配只在 BOSS 优质人选清单可追溯后执行。
- 不写 `data/talent.db`；如后续 Campaign DB clean，需要单独主库同步授权。

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
- [x] 用户指出不能只看一屏后，已继续 BOSS 推荐列表滚动寻访；当前累计采集 32 张卡片、14 个详情、7 个 `would_contact`。
- [x] 执行器真实触达 6 人且均验证为 `sent`/`送达`：王若飞、刘生、杨晨、王琦、杨林瑶、曹向书。
- [x] 第 7 位强匹配候选 David/WanFlow AI 已写入 approved queue，但执行器遇到 `paid_search_chat_card`，按 `stop_on_paid_prompt=true` 停止，未点击。
- [x] BOSS 侧因付费沟通卡片进入真实停止条件；不是因看满当前屏或主观提前结束。
- [x] BOSS 侧停止后重跑脉脉匹配 target 导出；`structured/maimai-match-targets.jsonl` 当前产出 6 位目标，David 因未触达且无真实姓名未进入 target。
- [ ] 完成脉脉匹配、身份 ledger 和后续交付/同步门禁；当前阻塞于 Chrome CDP 未在 `localhost:9222` 监听。

## Open Items

- 猎聘 parity 后续缺口：Campaign DB 到主库同步 handoff 仍只能做 dry-run/report，不得写 `data/talent.db`，真实 apply 需单独确认。
- 猎聘 parity 后续缺口：JD delivery/ranking 与飞书交付是否纳入猎聘寻访默认链路，需要先按 broad-recall summary 与主库同步边界设计。
- 大疆 BG OTD 脉脉寻访仍有历史平台验证码阻断；继续该旧 campaign 前需用户在平台侧处理验证码/安全验证。
- BOSS 当前职位今日沟通数达到付费解锁上限；等待额度重置或用户在 Codex 外处理后再续跑。

## Recent Done

- 2026-06-06：成本治理 P1 已落地只读 `campaign_status summarize` 和 `campaign_orchestrator next-action`，真实 BOSS-Maimai campaign smoke 输出 `next_stage=maimai-match-session`；聚焦测试 11 passed，全量测试 1379 passed；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-06：JD `feedback_note` 解析降本已落地规则优先与批量 LLM fallback，业务侧仍只填写 `feedback_note`；聚焦测试 22 passed，反馈链路测试 63 passed，全量测试 1373 passed；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-06：Claude Code + Codex 协作门禁已固化到 `docs/dev/agent-collaboration-gates.md`、README、capabilities 和架构测试；聚焦测试 19 passed，全量测试 1371 passed；完整记录已归档到 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
