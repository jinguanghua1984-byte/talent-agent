# BOSS-Maimai Campaign 交付逻辑修正设计

> 日期：2026-06-06
> 状态：设计草案，待用户审阅
> 范围：修正 BOSS-Maimai 寻访完成后的交付语义、产物和飞书发布边界

## 1. 背景

当前 `boss-maimai-cross-channel-delivery` 的 S10 把主库同步后的动作定义为交接 `jd-talent-delivery`，继续生成全库 JD Top30 推荐报告和飞书交付。这与 BOSS 寻访业务目标不一致。

BOSS 寻访闭环的交付对象应是本次 campaign，而不是整个人才库排序结果。正确交付应回答：

1. 本次看了多少 BOSS 人选。
2. 沟通了哪些人。
3. 哪些人被拿去脉脉匹配。
4. 哪些人在脉脉命中或确认绑定。
5. 哪些人最终写入主人才库。
6. 后续应该跟进哪些人、用什么渠道跟进。

关键业务规则：所有已沟通 BOSS 人选都需要跟进；脉脉匹配成功只是更好触达，不是跟进表入选条件。

## 2. 已确认发布策略

用户已确认：

- 旧的 Top30 飞书包保持不动。
- 不修改、删除或标记旧 Top30 飞书文档。
- 修正后只发布新的 BOSS campaign 交付包。

因此本设计不包含旧飞书文档修订动作。实施阶段只能创建新的 campaign 交付文档和跟进表，并在发布结果中明确新旧交付包语义不同。

## 3. 当前 Campaign 证据

本次修正以现有 campaign 为样例验证设计可行性：

`data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/`

已存在可重建交付包的本地证据：

| 证据 | 路径 | 当前值 |
| --- | --- | --- |
| BOSS 浏览/详情/沟通摘要 | `reports/sourcing-summary.json` | 看过 16 人，详情 16 人，计划沟通 5 人，实际沟通 5 人，真实姓名回采 5 人 |
| 沟通执行摘要 | `reports/executor-summary.json` | 审批队列 5 人，尝试 5 人，送达 5 人 |
| 脉脉匹配目标 | `structured/maimai-match-targets.jsonl` | 5 人 |
| 跨渠道绑定结果 | `structured/cross-channel-bound-candidates.jsonl` | 2 人 |
| 主库同步结果 | `reports/main-db-sync-result.json` | 新增 candidates 2、details 2、source_profiles 4、field_values 14，冲突/跳过/删除均为 0 |

本次已沟通且需要跟进的人选全集为 5 人：

| 姓名 | BOSS 公司 | BOSS 职位 | 脉脉状态 | 主库状态 |
| --- | --- | --- | --- | --- |
| 孙同 | 启元实验室 | 大模型算法 | 未命中 | 未入库 |
| 罗力睿 | 北京通用人工智能研究院（BIGAI） | 算法研究员 | 未命中 | 未入库 |
| 汪婧昀 | 小红书 hilab post-train | 大模型算法工程师 | 未命中 | 未入库 |
| 周超 | 亥姆霍兹信息安全中心 | 大模型算法 | 用户确认绑定 | 已入库 |
| 王若帆 | 华泰证券 | 算法工程师 | 自动绑定 | 已入库 |

## 4. 目标

1. 把 BOSS-Maimai workflow 的最终交付从“全库 JD 推荐”改为“本次 BOSS campaign 任务摘要和交付报告”。
2. 生成覆盖所有已沟通人选的后续跟进表。
3. 在报告中同时呈现 BOSS 漏斗、沟通漏斗、脉脉匹配漏斗、主库同步结果和候选人级状态。
4. 飞书发布只发布新的 BOSS campaign 交付包，不触碰旧 Top30 包。
5. 用质量门禁防止再次把全库 Top30 当成 BOSS 寻访交付。

## 5. 非目标

1. 不重新跑 BOSS 或脉脉平台搜索。
2. 不修改 `data/talent.db`。
3. 不改变已完成的主库同步结果。
4. 不把未沟通候选人放入跟进表。
5. 不把全库 JD Top30 推荐、JD 岗位画像或泛化外联表作为 BOSS campaign 交付包的一部分。
6. 不上传 raw platform payload、SQLite DB、sync zip、截图或平台原始采集文件到飞书。

## 6. 方案比较

| 方案 | 说明 | 优点 | 风险 | 结论 |
| --- | --- | --- | --- | --- |
| A. 新增 campaign 级交付包 | 新增报告/跟进表生成器和发布入口，S10 改为 BOSS campaign delivery | 语义正确，后续可复用，能用门禁防错 | 需要新增脚本和测试 | 推荐 |
| B. 过滤现有 JD Top30 | 继续走 `jd-talent-delivery`，只保留本次入库的 2 人 | 改动小 | 漏掉 3 个已沟通但未入库的人，仍混淆业务边界 | 不采用 |
| C. 手工补 Markdown | 为本次 campaign 手工写一份摘要并发布 | 快 | 不可复用，无法防止再次误发 Top30 | 不采用 |

采用方案 A。

## 7. 修正后的工作流语义

`boss-maimai-cross-channel-delivery` 的 S10 改为：

1. 读取本 campaign 的 BOSS sourcing、contact、executor、maimai target、identity ledger、bound candidates、main DB sync 结果。
2. 构造 campaign delivery report。
3. 构造 follow-up queue，行集等于本次已沟通 BOSS 人选全集。
4. 跑 campaign delivery quality gates。
5. 用户批准发布时，创建新的飞书 campaign 交付文档和跟进 Sheet。

`jd-talent-delivery` 不再是本 workflow 的默认 S10。它可以作为后续独立任务，用于从主人才库按某个 JD 做全库推荐，但不能代表 BOSS campaign 寻访交付闭环。

## 8. 输出产物

产物放在原 campaign root 下。

```text
data/campaigns/<campaign_id>/
  reports/
    boss-maimai-delivery-report.json
    boss-maimai-delivery-report.md
    boss-maimai-follow-up-queue.csv
    boss-maimai-follow-up-queue.md
    boss-maimai-delivery-quality-gates.json
  feishu/
    boss-maimai-delivery-manifest.json
    boss-maimai-delivery-dry-run-results.json
    boss-maimai-delivery-publish-results.json
```

其中 `feishu/` 产物只在发布阶段生成；设计和本地报告生成阶段不得写云端。

## 9. 报告结构

`boss-maimai-delivery-report.json` 使用 `boss_maimai_campaign_delivery_report_v1` schema，至少包含：

```json
{
  "schema": "boss_maimai_campaign_delivery_report_v1",
  "campaign_id": "...",
  "generated_at": "...",
  "source_files": {},
  "boss_funnel": {
    "list_card_count": 16,
    "detail_count": 16,
    "would_contact_count": 5,
    "real_contact_count": 5,
    "message_status_distribution": {"送达": 5}
  },
  "maimai_funnel": {
    "target_count": 5,
    "matched_count": 2,
    "auto_bound_count": 1,
    "confirmed_bound_count": 1,
    "no_match_count": 3
  },
  "main_db_sync": {
    "status": "applied",
    "created_candidates": 2,
    "created_details": 2,
    "created_source_profiles": 4,
    "conflicts": 0,
    "skipped": 0
  },
  "candidate_rows": []
}
```

Markdown 报告面向飞书阅读，包含：

1. 任务摘要。
2. BOSS 寻访漏斗。
3. 沟通执行结果。
4. 脉脉匹配结果。
5. 主库入库结果。
6. 候选人级交付表。
7. 后续跟进建议。

## 10. 跟进表结构

`boss-maimai-follow-up-queue.csv` 使用所有已沟通候选人为全集。每一行至少包含：

| 字段 | 说明 |
| --- | --- |
| `candidate_key` | BOSS campaign candidate key |
| `real_name` | 沟通页回采真实姓名 |
| `boss_display_name` | BOSS 展示名 |
| `boss_company` | BOSS 当前公司 |
| `boss_title` | BOSS 当前职位 |
| `city` | BOSS 城市 |
| `education` | BOSS 学历 |
| `boss_score` | BOSS 筛选分 |
| `contact_status` | 是否已沟通 |
| `message_status` | 送达/失败等 |
| `maimai_match_status` | `auto_bound`、`confirmed_bound`、`no_match`、`pending_confirmation` 等 |
| `maimai_profile_url` | 命中时填脉脉主页 |
| `maimai_platform_id` | 命中时填平台 id |
| `main_db_candidate_id` | 已写主库时填主库 candidate id |
| `follow_up_required` | 已沟通人选固定为 `true` |
| `preferred_channel` | `maimai` 或 `boss` |
| `follow_up_action` | 下一步动作 |
| `priority` | 跟进优先级 |
| `reasons` | 推荐理由摘要 |
| `risks` | 风险和需确认点 |

跟进规则：

- `maimai_match_status in ('auto_bound', 'confirmed_bound')`：`preferred_channel=maimai`，动作为优先脉脉触达并同步 BOSS 回复状态。
- `maimai_match_status='no_match'`：`preferred_channel=boss`，动作为继续 BOSS 会话跟进，并视需要后续补充脉脉人工搜索。
- `maimai_match_status='pending_confirmation'`：`preferred_channel=boss`，动作为先人工确认身份，再决定是否转脉脉触达。
- 所有已沟通人选 `follow_up_required=true`，不得因未命中脉脉或未入库而剔除。

## 11. 质量门禁

`boss-maimai-delivery-quality-gates.json` 使用 `boss_maimai_campaign_delivery_quality_gates_v1` schema。

必须通过的门禁：

1. 必需输入文件存在且可解析。
2. `follow_up_row_count == real_contact_count`。
3. `maimai_target_count == real_name_captured_count`，除非报告明确列出缺姓名阻塞项。
4. `maimai_matched_count <= maimai_target_count`。
5. `main_db_created_candidates <= maimai_matched_count`。
6. 所有 follow-up 行的 `follow_up_required` 都为 `true`。
7. 命中脉脉的人选必须有可打开的 `maimai_profile_url` 或明确原因。
8. 未命中脉脉的人选必须仍出现在跟进表。
9. 报告不得读取或引用全库 Top30 推荐结果目录。
10. 飞书 manifest 不得包含 raw payload、SQLite DB、sync zip、截图或平台原始文件路径。

任一门禁失败时，不允许发布飞书。

## 12. 飞书发布设计

发布只针对新的 BOSS campaign 交付包：

1. 创建一个新的飞书文档，标题包含 campaign 和 `BOSS寻访交付报告`。
2. 创建一个新的飞书 Sheet，标题包含 campaign 和 `BOSS跟进表`。
3. 文档内链接到跟进 Sheet。
4. 发布结果写入 `feishu/boss-maimai-delivery-publish-results.json`。
5. 发布后执行 readback，确认新文档/Sheet 存在且行数等于 `real_contact_count`。

旧 Top30 飞书包保持不动，不追加说明、不移动、不删除。

## 13. 契约修改点

需要修改：

- `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`
- `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`

修改原则：

1. skill 描述从“主库同步和 JD/飞书交付”改为“主库同步和 BOSS campaign 交付”。
2. 输出产物增加 campaign delivery report、follow-up queue 和 delivery quality gates。
3. 自动交接段删除默认 `jd-talent-delivery` handoff。
4. workflow S10 改名为 `BOSS campaign delivery / 飞书交付`。
5. 验收条件新增 follow-up row count 和发布边界门禁。

## 14. 实施边界

本设计确认后，实施计划再拆分具体任务。预计修改文件：

- 新增 `scripts/boss_maimai_campaign_delivery.py`
- 新增 `tests/test_boss_maimai_campaign_delivery.py`
- 修改 `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`
- 修改 `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`
- 视发布实现方式，新增或复用飞书发布脚本
- 修改 `tests/test_agent_architecture.py` 覆盖 S10 不再默认 `jd-talent-delivery`
- 修改 `tasks/todo.md` 记录实施进度

实施阶段仍不得重新跑平台搜索，不得再次写 `data/talent.db`。

## 15. 验证策略

本地验证：

1. 新增单测覆盖 5 人 follow-up 全集、2 人脉脉命中、3 人未命中仍保留、2 人主库写入子集。
2. 单测覆盖质量门禁：当 follow-up 行数少于已沟通人数时 blocked。
3. 单测覆盖契约：workflow S10 不再默认交接 `jd-talent-delivery`。
4. 对当前 campaign 运行报告生成器，检查 JSON/Markdown/CSV 产物。
5. `git diff --check`。
6. `.venv/bin/python -m pytest tests -q`。

飞书发布验证：

1. `lark-cli` auth/doctor 预检。
2. dry-run 生成新文档和新 Sheet 命令。
3. 真实发布只创建新 BOSS campaign 交付包。
4. readback 验证文档标题、Sheet 行数和关键字段。
5. 确认旧 Top30 飞书包未被修改。

## 16. 验收标准

1. BOSS-Maimai workflow 不再把全库 JD Top30 当作默认交付闭环。
2. 当前 campaign 能生成 5 行跟进表。
3. 报告显示：看过 16 人、沟通 5 人、脉脉匹配目标 5 人、脉脉命中 2 人、主库写入 2 人。
4. 未命中脉脉的 3 人仍在跟进表中。
5. 飞书只发布新的 BOSS campaign 交付包。
6. 旧 Top30 飞书包保持不动。
