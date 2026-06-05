# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

### BOSS AI Infra 训练和推理研发寻访（2026-06-02）

计划：
- [x] 读取 BOSS canonical skill/workflow，确认触达安全边界。
- [x] 初始化 campaign 合同：目标职位为 AI Infra 训练和推理研发，硬性要求为一线互联网大厂履历、工龄 3-10 年、年龄不超过 40。
- [x] 预检本机 BOSS App 推荐列表页并采集候选人卡片。
- [ ] 对匹配人选进入详情页精筛，累计 20 名可联系人选后停止。
- [x] 按本轮 campaign 级授权执行触达：同一职位、同一筛选规则、上限 20 人内，已判定 `contact` 且当前页为 `立即沟通` 的人选由执行器直接点击，不再逐人二次确认。
- [x] 生成阶段执行摘要和推荐报告，推送飞书并通知。

边界：
- 只使用 BOSS App 本机 UI 推荐列表，不使用 BOSS 网页端、CDP、浏览器扩展或 BOSS API。
- 不处理验证码、安全验证、登录失效或付费/权限弹窗；遇到即写 continuation plan 并停止。
- 不修改 BOSS 账号设置、职位设置、沟通话术或权限。
- 本轮用户已明确授权“合适立即沟通，不用二次确认”，并在执行器确认问题后重申不要逐人确认；本 campaign 以此作为批量触达授权，范围仅限本职位、本筛选规则、最多 20 名判定为 `contact` 的候选人。

验证：
- `.venv/bin/python -m scripts.boss_app_sourcing validate --campaign-root <campaign_root>`。
- `.venv/bin/python -m scripts.boss_app_sourcing summarize --campaign-root <campaign_root>`。
- 飞书推送后读取 publish/notification 结果文件确认。

Review：
- 2026-06-02：已真实触达 `17/20` 人，沟通页实名回填 `17` 人，执行器校验 `passed`。
- 第 18 位候选人郭先生触发 BOSS 付费上限弹窗：`该职位今日沟通数已达上限，付费解锁上限`；已停止，未购买、未绕过，剩余 `3` 人待额度恢复后续跑。
- 阶段报告与触达人选表已推送飞书 `JD需求交付`，并已通知 `JD需求协同`。回执：`data/campaigns/boss-ai-infra-training-inference-20260602/reports/feishu-publish-results.json`。
- 2026-06-02：已修订 `boss-app-recommendation-sourcing` skill/workflow：campaign 级授权成立时，workflow 可直接调用外部执行器 `contact-current --execute`，不逐人确认；执行器仍只负责当前详情页 `立即沟通` 原子点击，列表、详情、筛选、翻页继续由 Computer Use 负责。

## Open Items

- BOSS 当前职位今日沟通数达到付费解锁上限；等待额度重置，或用户在 Codex 外处理付费额度后，继续补足剩余 `3` 人。
- Campaign validate 仍有采集完整性问题：`8` 个历史候选缺详情、`2` 组重复签名；不影响本轮 `17` 条已送达审计，但续跑前应优先清理候选池去重/详情状态。

## Recent Done

- 2026-06-05：BOSS-Maimai cross-channel spec re-review 两项 blocking 修复已完成：`education` 不再作为 `name_school_title_core` auto-bind 证据，`decide_match` 无结果/低分统一返回 `no_match`，并同步 canonical skill/workflow 与设计文档。验证：目标 pytest `20 passed`，`git diff --check` 通过。完整记录见 `tasks/archive/2026-06.md`。
- 2026-06-05：BOSS-Maimai cross-channel code-quality review 三项修复已完成：缺关键证据的 query 不再生成可 auto-bind 退化查询，目标导出在无 `boss_payload` 时保留完整原行上下文，JSONL 非对象行改为报错。验证：目标 pytest `19 passed`，`git diff --check` 通过。完整记录见 `tasks/archive/2026-06.md`。
- 2026-06-02：BOSS 当前详情页触达执行器 MVP Task 6 已完成 canonical docs handoff：记录外部执行器产物、S6a handoff、existing sourcing 回写路径，并明确 Codex/Computer Use 不点击真实触达按钮。完整记录见 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
