# BOSS-Maimai 召回匹配优化设计（2026-06-05）

## 背景

本轮腾讯游戏训练推理数据工程 BOSS-Maimai campaign 中，BOSS 已沟通人选周超在脉脉实际存在，但第一轮精确检索没有召回。复盘使用现有 CDP live gate 脚本只读验证：

- `周超 亥姆霍兹信息安全中心 大模型算法` 返回 0。
- `周超 亥姆霍兹信息安全中心` 返回 0。
- `周超 海姆霍兹信息安全中心` 返回 1，命中 `dstu=239360802`。
- `周超 伦敦大学学院` 返回 1，命中同一人。

详情接口显示脉脉主字段为 `海姆霍兹信息安全中心 / 博士后`，BOSS 主字段为 `亥姆霍兹信息安全中心 / 大模型算法`。根因不是登录、接口或解析失败，而是召回 query 把 BOSS 原始公司和职位作为硬 AND 条件，导致字段差异直接把真实候选人过滤掉。

## 目标

第一阶段只优化 BOSS 已筛/已沟通人选补脉脉主页匹配链路：

1. 提高 `structured/maimai-match-targets.jsonl` 生成的 query plan 召回率。
2. 对公司译名、别字、国家后缀等轻量 alias 做确定性归一。
3. 从 BOSS 详情文本中抽取学校证据，用作低风险降级召回层。
4. 让职位字段更多用于身份打分，而不是召回阶段的必选硬条件。
5. 保持身份绑定保守：低精度、fallback、字段冲突或候选过多时不得自动绑定。

非目标：

1. 不改通用 `maimai-talent-search-campaign` 宽召回寻访流程。
2. 不写 `data/talent.db`，不变更主库同步门禁。
3. 不绕过脉脉登录、验证码、安全页、CDP live gate 或平台风控边界。
4. 不引入 LLM 参与自动身份绑定。
5. 不让脉脉字段覆盖 BOSS primary 非空核心字段。

## 当前链路判断

### Target 生成

`scripts/boss_maimai_targets.py` 从 BOSS `structured/candidates.jsonl` 中挑选 contact / would-contact 人选，生成 `structured/maimai-match-targets.jsonl`。现有逻辑已经保留：

- BOSS candidate key
- 真实姓名
- 当前公司
- 当前职位
- 城市、学历
- `recent_companies`
- `schools`
- BOSS payload
- `query_plan`

问题是 `_schools()` 只读取结构化 `schools` / `education_experience` 容器。周超这类 BOSS 详情里有“伦敦大学学院”文本，但未形成 `schools` 字段，导致 `name_school_title_core` 没有生成。

### Query plan

`scripts/cross_channel_identity.py` 当前 query 层级是：

1. `name_company_title`
2. `name_company_title_core`
3. `name_recent_company_title`
4. `name_school_title_core`
5. `name_company_fallback`

这套层级适合字段一致的人选，但对 BOSS/脉脉字段不一致的场景过窄。尤其是：

- 公司别名未进入 query plan。
- `name_company_fallback` 仍只使用 BOSS 原公司写法。
- 学校 query 要求同时带 title core，周超这类“学校强、职位字段不一致”的人选仍可能漏掉。

### 身份判定

`decide_match()` 当前保守性是正确的：

- `name_company_fallback` 不自动绑定。
- 高精度层命中但分数 70-94 进入 `pending_confirmation`。
- 候选过多、第二名分差过小进入 `pending_confirmation`。
- 低于 70 写 `no_match`。

本设计不放松自动绑定门槛，重点只在召回阶段增加可审计候选证据。

## 推荐方案

采用“分层召回 + 保守绑定”。

```text
BOSS contact candidate
  -> target 抽取增强：公司 alias、学校证据、近期公司
  -> query plan 扩展：精确层、alias 层、学校层、非自动 fallback
  -> 脉脉搜索 live gate 逐层执行
  -> identity scoring 保守判定
  -> auto_bound / pending_confirmation / no_match
  -> Campaign DB supplement merge
```

这个方案解决周超类漏召回，同时不扩大自动合并风险。

## 设计细节

### 1. 公司 alias 归一

新增确定性公司 alias 生成，不做泛化模糊匹配。首版规则只覆盖低风险、可解释场景：

- `亥姆霍兹信息安全中心` -> `海姆霍兹信息安全中心`
- `海姆霍兹信息安全中心` -> `亥姆霍兹信息安全中心`
- 去除括号国家/地区后缀，例如 `亥姆霍兹信息安全中心(德国)` -> `亥姆霍兹信息安全中心`
- 中英文括号都处理：`()`、`（）`

输出要求：

- alias 只能用于生成 query 和公司打分候选。
- alias 不改写 BOSS primary `current_company`。
- alias 命中必须写入 identity ledger 的 `score_breakdown` 或后续 evidence 字段，方便审计。

### 2. 学校证据抽取

`boss_maimai_targets.py` 增强 `_schools()`，读取以下来源：

- `detail_sections.schools`
- `detail_sections.education_experience`
- `detail_sections.education`
- `detail_sections.summary`
- `detail_sections.work_experience[].description`
- 顶层 `education_detail` / `school` / `school_name`，如果未来存在

首版不做无限字典，只抽当前 BOSS 详情里高可信学校名。可用规则：

- 对字段中出现的学校名称做字符串抽取，例如 `伦敦大学学院`。
- 保留现有结构化学校优先级。
- 去重并保持原始出现顺序。

学校 query 只作为召回层，不直接替代公司一致性。

### 3. Query plan 扩展

建议 query 层级调整为：

1. `name_company_title`：原始高精度。
2. `name_company_title_core`：原始公司 + title core。
3. `name_company_alias`：姓名 + 公司 alias，不带 title，`allow_auto_bind=false`。
4. `name_company_alias_title_core`：姓名 + 公司 alias + title core，`allow_auto_bind=false`。
5. `name_recent_company_title`：近期公司 + title core。
6. `name_school_title_core`：学校 + title core，保持高精度但需要学校明确存在。
7. `name_school_fallback`：姓名 + 学校，不带 title，`allow_auto_bind=false`。
8. `name_company_fallback`：姓名 + 原始公司，`allow_auto_bind=false`。

排序原因：

- 先保留现有高精度路径，避免影响稳定命中。
- alias 层放在 recent/school 前，优先解决公司写法差异。
- 学校 fallback 放在最后，因为同名同校仍可能有误绑风险。

对周超，期望 query plan 至少包含：

```text
周超 亥姆霍兹信息安全中心 大模型算法
周超 亥姆霍兹信息安全中心
周超 海姆霍兹信息安全中心
周超 伦敦大学学院
```

### 4. 身份打分调整

公司打分 `_company_score()` 应把 target 的公司 alias 纳入可匹配集合：

- hit company 精确等于 target current company：满分。
- hit company 精确等于 target alias：接近满分，但保留 alias 证据。
- hit company 与 recent company/alias 命中：略低分。
- 只靠学校命中、公司不一致时不能自动绑定。

自动绑定保持原规则，不因 alias 放宽：

- 只有 `allow_auto_bind=true` 的高精度层才可能 `auto_bound`。
- `name_company_alias`、`name_company_alias_title_core`、`name_school_fallback`、`name_company_fallback` 默认进入 `pending_confirmation`，除非后续设计专门引入“详情强证据自动绑定”门槛。
- 字段冲突时进入 `pending_confirmation` 或记录为 supplement conflict，不覆盖 BOSS primary。

### 5. 搜索执行策略

现有问题之一是实际只执行了第一条 `name_company_title`。执行层应按 target 的 `query_plan` 顺序逐层尝试：

- 当前层命中并 `auto_bound`：停止该 target。
- 当前层命中但 `pending_confirmation`：保留候选，继续或停止由策略决定；首版建议停止并进入人工确认，避免平台请求过多。
- 当前层 `no_hits`：继续下一层。
- 平台阻断：停止整个阶段并写 continuation plan。

本设计只定义策略；实现时可先在现有批次计划生成中保证 query_plan 全量展开，再由现有 live gate 执行。

## 数据与产物

新增或增强字段建议：

- `company_aliases`: target 级别公司 alias 列表。
- `school_evidence`: target 级别学校抽取来源，例如字段路径和原文片段。
- `query_plan[].allow_auto_bind`: 继续作为搜索层安全门禁。
- `query_plan[].evidence_type`: 可选，标注 `original_company`、`company_alias`、`school`、`fallback`。

不要求第一阶段改变 DB schema。若需要审计 alias 命中，可先写入 JSONL ledger 的 `score_breakdown` 或 `hit.raw` 摘要。

## 测试设计

新增或更新以下测试：

1. `tests/test_cross_channel_identity.py`
   - `test_query_plan_includes_company_alias_fallback_for_helmholtz`
   - `test_alias_company_hit_scores_company_without_auto_bind_for_alias_level`
   - `test_school_fallback_hit_requires_confirmation`

2. `tests/test_boss_maimai_targets.py`
   - `test_export_extracts_school_from_boss_detail_summary_text`
   - `test_export_includes_company_aliases_in_query_plan`

3. 可选架构/契约测试
   - 确认 `boss-maimai-cross-channel-delivery` workflow 中仍声明 fallback 不自动绑定、BOSS primary 不被覆盖。

验证命令：

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py tests/test_boss_maimai_targets.py -q
.venv/bin/python -m pytest tests -q
```

## 风险与约束

1. 公司 alias 规则不能无限泛化。首版只做明确规则和括号后缀归一，避免误把不同组织合并。
2. 学校 fallback 会增加同名风险，不能自动绑定。
3. title 不作为召回硬条件后，候选数可能增加；执行层要遵守分页和平台阻断规则。
4. 周超 profile 详情证据只能作为 supplement，不覆盖 BOSS primary 字段。
5. 主库 apply 仍需要 `reports/main-db-sync-dry-run.json` 和用户授权。

## 验收标准

设计落地后，针对周超类样例应满足：

1. BOSS target 能抽到 `伦敦大学学院` 作为学校证据。
2. Query plan 能生成 `周超 海姆霍兹信息安全中心` 和 `周超 伦敦大学学院`。
3. 原始精确 query `no_hits` 后，执行计划不会直接把 target 判为永久 `no_match`。
4. 通过 alias 或学校召回的候选不自动写入主库；需要进入 `pending_confirmation` 或后续详情强证据流程。
5. BOSS primary 的公司、职位、城市、学历不被脉脉字段覆盖。

## 后续实现建议

实施时按 TDD 执行：

1. 先补周超回归测试，确认当前代码红灯。
2. 增加公司 alias 纯函数和 query plan 扩展。
3. 增强 BOSS 学校证据抽取。
4. 调整公司打分使用 alias，但不放宽 auto-bind。
5. 跑局部测试和全量测试。

本设计文档通过后，再写实施计划，不在设计阶段改业务代码。
