# BOSS 优质人选补脉脉寻访与多渠道交付设计

> 日期：2026-06-04
> 状态：设计已确认，待实施计划
> 范围：BOSS App 已筛优质人选 -> 脉脉主页匹配 -> 多渠道 Campaign DB -> 自动主库同步 -> JD delivery -> 飞书交付

## 1. 背景

现有 BOSS App 推荐列表寻访 workflow 已能在本机 BOSS App 中浏览职位推荐人选、进入详情页筛选优质人选、记录 `would_contact` 或真实触达结果，并在沟通页回采真实姓名。现有脉脉寻访 workflow 已能执行脉脉搜索、详情抓取、Campaign DB 写入、报告和飞书交付。

新的需求是在 BOSS 已挑出的优质人选基础上，追加一个脉脉匹配步骤：用 BOSS 的高质量候选信息去脉脉搜索页匹配同一人。如果匹配到，就抓取脉脉信息，主要补齐脉脉主页链接，方便通过脉脉平台触达。整合后的候选人先写 Campaign DB，再在门禁通过后基于一次总授权自动写入 `data/talent.db`，并继续生成交付产物、推送飞书。

## 2. 目标

1. 从 BOSS campaign 中筛选 `contact` / `would_contact` 的优质人选，生成脉脉匹配清单。
2. 复用现有脉脉寻访能力，按高精准 query 优先策略匹配同一候选人的脉脉主页。
3. 扩展 `TalentDB` 支持多渠道整合：身份匹配审计、来源字段审计、来源 profile 和 canonical 字段共存。
4. merge 时 BOSS 为 primary，脉脉只补缺，重点补 `profile_url`、`platform_id`、求职/活跃状态和 BOSS 缺失字段。
5. Campaign DB clean 后，通过标准 sync bundle dry-run/apply 自动写入主库。
6. 主库写入后自动调用 `jd-talent-delivery` 生成推荐报告、外联表、质量门禁、飞书 Wiki/Sheet 和 IM 通知。

## 3. 非目标

1. 不重写 BOSS App sourcing workflow 的列表、详情、触达执行逻辑。
2. 不把 BOSS 网页端、BOSS API 或 CDP 搜索引入 BOSS App workflow。
3. 不绕过脉脉登录、验证码、429、432、安全页、权限或平台风控。
4. 不在身份匹配不确定、Campaign DB 不干净、sync dry-run 有冲突或交付质量门禁失败时写主库。
5. 不把脉脉字段静默覆盖 BOSS primary 字段。
6. 不上传 raw search、raw detail、SQLite DB、sync zip 或平台原始 payload 到飞书交付包。

## 4. 方案选择

推荐方案是新增 `boss-maimai-cross-channel-delivery` canonical skill/workflow，作为 BOSS workflow 的下游增强流程。

| 方案 | 说明 | 结论 |
| --- | --- | --- |
| 最小桥接 | BOSS 导入 Campaign DB 后单独跑脉脉匹配，只补 `source_profiles` | 快，但身份审计和字段冲突治理不足 |
| 新增 cross-channel workflow | 保留现有 BOSS/脉脉 workflow，新增跨平台匹配、审计和自动主库同步编排 | 推荐，复用最多且边界清楚 |
| 全量重构 TalentDB | 将 Candidate、SourceProfile、FieldValue、ContactMethod 全面模型化 | 长期方向，当前过重 |

## 5. 整体阶段

新增 workflow：`agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`。

阶段链路：

1. 读取 BOSS campaign，抽取 `contact` / `would_contact` 优质人选。
2. 生成 `structured/maimai-match-targets.jsonl`。
3. 对每个 target 按高精准 query 顺序执行脉脉搜索。
4. 对搜索结果做 identity scoring，输出自动绑定、待确认、未匹配。
5. 对自动绑定和人工确认绑定的人选，写入 Campaign DB。
6. 对绑定了 maimai `platform_id` 的候选人规划并执行脉脉详情抓取。
7. 详情 clean 后 apply 到 Campaign DB。
8. Campaign DB 校验通过后导出 sync bundle，并对 `data/talent.db` 做 dry-run。
9. dry-run clean 且无 open conflict 时，基于一次总授权自动 apply 到主库。
10. 主库验证通过后执行 `jd-talent-delivery`，生成交付系列产物并推送飞书。

## 6. 数据模型

保留现有 `TalentDB` 的 canonical 主表模型，不破坏现有交付链路：

- `candidates` 继续保存当前系统可直接消费的 canonical 字段。
- `candidate_details` 继续保存合并后的经历、项目、教育、summary 和 raw_data 命名空间。
- `source_profiles` 继续保存平台来源事实：`platform`、`platform_id`、`profile_url`、`raw_profile`、`sync_id`。

新增跨平台审计表。

### 6.1 candidate_identity_matches

记录“BOSS target 是否匹配某个脉脉候选人”的过程和结论。

建议字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 自增主键 |
| `candidate_id` | Campaign DB / TalentDB candidate id，可为空直到绑定完成 |
| `source_platform` | 例如 `boss_app` |
| `source_candidate_key` | BOSS campaign 内的 `candidate_key` |
| `target_platform` | 例如 `maimai` |
| `target_platform_id` | 脉脉候选人 id |
| `target_profile_url` | 脉脉主页 URL |
| `query_text` | 命中的搜索 query |
| `query_level` | `name_company_title`、`name_company_title_core`、`name_recent_company_title`、`name_school_title_core`、`name_company_fallback` |
| `confidence` | 0-100 |
| `score_breakdown` | JSON，记录姓名、公司、职位、城市、学历、经历重叠、结果数、第一二名差距 |
| `match_status` | `auto_bound`、`pending_confirmation`、`confirmed_bound`、`rejected`、`not_found` |
| `decision_reason` | 判定摘要 |
| `confirmed_by` | 人工确认来源，可为空 |
| `confirmed_at` | 人工确认时间，可为空 |
| `created_at` / `updated_at` | 审计时间 |

### 6.2 candidate_field_values

记录不同平台对同一字段给出的值和 merge 决策。主表仍保存 canonical 值。

建议字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 自增主键 |
| `candidate_id` | 候选人 id |
| `field_name` | canonical 字段名，例如 `current_company` |
| `platform` | `boss_app`、`maimai` 等 |
| `source_profile_id` | 来源 profile id，可为空 |
| `field_value` | JSON 字段值 |
| `confidence` | 来源可信度 |
| `merge_decision` | `primary_kept`、`filled_empty`、`supplement_added`、`conflict_recorded`、`ignored_empty` |
| `decision_reason` | 决策说明 |
| `created_at` | 记录时间 |

## 7. Merge 策略

BOSS 为 primary，脉脉为 supplement。

主表字段处理：

- BOSS 已有且非空的 `name`、`current_company`、`current_title`、`city`、`work_years`、`education` 不被脉脉覆盖。
- 脉脉只填补 BOSS 空字段，或补充 `hunting_status`、活跃状态、`profile_url`、`platform_id`。
- `skill_tags`、`work_experience`、`education_experience`、`project_experience` 采用去重并集。
- 同字段冲突写入 `candidate_field_values` 和必要的 `sync_conflicts`，不静默覆盖。
- `candidate_details.raw_data` 按命名空间保存：`boss_app_detail_capture`、`maimai_detail_capture`、`cross_channel_identity_match`。

交付 URL 规则：

1. 优先返回可打开的脉脉 `profile_url`。
2. 其次返回其他平台 URL。
3. 脉脉 URL 保留打开必需的 `dstu` 和 `trackable_token`，清理 UTM、`show_tip` 和详情抓取临时参数。

## 8. 脉脉匹配策略

匹配时优先精准 query，不从宽 query 起步。

query 顺序：

1. `真实姓名 + 当前公司 + 当前职位`
2. `真实姓名 + 当前公司 + 职位核心词`
3. `真实姓名 + BOSS 详情中的最近公司 + 最近职位`
4. `真实姓名 + 学校/学历 + 职位核心词`
5. `真实姓名 + 公司`

第 5 级 `姓名+公司` 只作为低优先级 fallback。它可能产生过多同名结果，不允许直接自动绑定。

自动绑定规则：

- 只有 query level 属于前 4 级，且 identity score `>=95`，才允许 `auto_bound`。
- 如果结果数过多、第一名与第二名差距小、或只靠 `姓名+公司` 命中，即使分数高也进入 `pending_confirmation`。
- `70-94` 一律 `pending_confirmation`。
- `<70` 标记 `not_found` 或 `rejected`。
- 没有真实姓名时，不跑自动匹配，只生成待补姓名清单。

identity score 至少包含：

- 姓名精确度。
- 公司匹配度，含公司别名。
- 职位匹配度，含核心词。
- 城市匹配。
- 学历/学校匹配。
- 工作经历时间或公司重叠。
- 搜索结果数量惩罚。
- 第一名和第二名分差。

## 9. 脚本拆分

新增脚本按职责拆分。

| 脚本 | 职责 |
| --- | --- |
| `scripts/boss_maimai_targets.py` | 从 BOSS campaign 生成脉脉匹配 target 清单 |
| `scripts/cross_channel_identity.py` | 生成 query、解析脉脉搜索结果、评分、输出绑定决策 |
| `scripts/cross_channel_import.py` | 将 BOSS primary + maimai supplement 写入 Campaign DB |
| `scripts/campaign_to_delivery.py` | Campaign DB clean 后自动 sync 主库并调用 `jd-talent-delivery` |

复用现有能力：

- 脉脉搜索、阻断、恢复和 raw 落盘复用 `maimai-unattended-campaign` 的安全边界。
- 脉脉 detail target/detail import 复用现有 detail 能力，但必须先绑定 `source_profiles(platform='maimai', platform_id=...)`。
- 主库写入复用 `talent_sync export/import` bundle dry-run/apply，不直接复制 SQLite。
- 飞书交付复用 `jd-talent-delivery`。

## 10. 产物

在原 BOSS campaign root 下新增跨平台目录和报告：

```text
data/campaigns/<campaign_id>/
  structured/
    maimai-match-targets.jsonl
    cross-channel-bound-candidates.jsonl
  raw/
    maimai-match-search/
      <target_id>/query-*.json
  state/
    cross-channel-identity-ledger.jsonl
    main-db-sync-ledger.jsonl
    continuation-plan.json
  reports/
    maimai-match-summary.json
    maimai-match-summary.md
    cross-channel-import-dry-run.json
    cross-channel-import-dry-run.md
    campaign-db-quality-gates.json
    main-db-sync-dry-run.json
    main-db-sync-result.json
    interruption-*.json
```

## 11. 自动主库写入

用户已确认：Campaign DB 干净后，可以基于一次总授权自动写入 `data/talent.db` 并继续生成飞书交付。

自动写入必须同时满足：

1. 无 `pending_confirmation` identity match。
2. 无 `missing_real_name` 且需要匹配的人选都已完成目标状态。
3. Campaign DB `PRAGMA integrity_check=ok`。
4. Campaign DB 中 `source_profiles`、identity match、field value audit 数量符合预期。
5. sync bundle `verify-bundle` 通过。
6. 主库 import dry-run 无 pending、无 open conflict、无错误。
7. 主库备份或同步前证据已落盘。

写入后验证：

- `PRAGMA integrity_check=ok`。
- 新增/合并数量与 dry-run 预期一致。
- `source_profiles.platform in ('boss_app', 'maimai')` 的新增/合并计数符合预期。
- 脉脉 profile URL 可被 `jd-talent-delivery` 作为优先 URL 读取。
- 写入结果记录到 `state/main-db-sync-ledger.jsonl`。

## 12. 停机条件

任一条件出现时停止，写 interruption report 和 continuation plan：

- 脉脉登录失效、验证码、403、429、432、安全页、非 JSON、HTML、partial capture。
- BOSS target 缺真实姓名，无法自动匹配。
- identity match 进入 `pending_confirmation`。
- `姓名+公司` fallback 命中但无人工确认。
- Campaign DB import/detail apply 有 blocker。
- sync dry-run 产生 pending、open conflict 或错误。
- 主库写入后验证不一致。
- `jd-talent-delivery` quality gate blocked。
- 飞书 dry-run、真实发布、回读或 IM 通知失败。

## 13. 测试策略

新增或扩展测试：

- `tests/test_cross_channel_identity.py`
  - query 生成顺序。
  - `姓名+公司` fallback 不自动绑定。
  - 结果过多和第一二名差距小进入待确认。
  - `>=95` 高精准命中自动绑定。
- `tests/test_cross_channel_import.py`
  - BOSS primary 字段不被脉脉覆盖。
  - 脉脉补 profile URL 和缺失字段。
  - 字段冲突写 audit，不静默覆盖。
- `tests/test_talent_db.py`
  - 新增 identity match 和 field value audit schema。
  - 多平台 source profile 可导出/导入 sync bundle。
- `tests/test_jd_talent_delivery_match.py`
  - 多 source 时优先返回脉脉 profile URL。
- `tests/test_agent_architecture.py`
  - 新增 canonical skill/workflow/adapter 覆盖。

验证命令：

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py tests/test_cross_channel_import.py tests/test_talent_db.py tests/test_jd_talent_delivery_match.py tests/test_agent_architecture.py -q
.venv/bin/python -m pytest tests -q
git diff --check
```

## 14. 验收标准

1. dry-run 可以从 BOSS campaign 生成脉脉匹配清单。
2. 自动绑定只发生在高精准 query + 高置信匹配。
3. `姓名+公司` fallback 不会自动写入绑定。
4. Campaign DB 能保存 BOSS primary、maimai source、identity audit 和 field value audit。
5. Campaign DB clean 后，workflow 能基于总授权自动同步主库。
6. 主库写入后，交付产物优先使用脉脉 profile URL。
7. 飞书交付沿用 `jd-talent-delivery` 的 dry-run、发布、回读和通知门禁。
8. 任一不确定状态都有 continuation plan，不能静默跳过。
