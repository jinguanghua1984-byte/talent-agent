# 人才库管理 Skill 设计

> **日期**: 2026-05-10
> **状态**: Draft
> **背景**: 面向猎头顾问用户，设计统一的人才库管理 skill，覆盖人才导入、查询、匹配、评分、详情抓取、更新和删除，且充分复用现有实现。

---

## 1. 目标

设计一个聚合型 `talent-library` skill，作为猎头顾问管理本地人才库的统一入口。

第一版覆盖：

- 人才导入：从插件导出、平台搜索结果、旧 JSON 数据导入 SQLite 人才库。
- 人才查询：按公司、职位、城市、学历、工作年限、技能、平台来源、数据完整度、综合分查询。
- 人才匹配：根据 JD、JD ID 或自然语言画像筛选候选人。
- 人才综合评分：维护候选人自身质量分。
- JD 匹配评分：维护候选人对具体 JD 的匹配分。
- 人才详情抓取：补全候选人的平台详情和履历信息。
- 人才信息更新：更新结构化字段、来源、详情和评分。
- 人才删除：确认后硬删除候选人及关联记录。

核心原则：

1. `talent-library` 只做业务编排，不复制底层平台搜索、评分、数据库逻辑。
2. SQLite `data/talent.db` 是第一版主数据源，旧 JSON 只作为迁移和兼容入口。
3. 运行时中立 workflow 是业务事实来源，具体 agent skill 只做薄适配。
4. 高风险动作先展示影响范围，再等待用户明确确认。

## 2. 非目标

- 不重写 `platform-match`、`screen` 或 `score_pipeline.py` 的现有能力。
- 不在 skill 文档里内嵌复杂评分公式或平台抓取细节。
- 不把业务脚本放进 `.claude/skills` 或其他运行时私有目录。
- 不在第一版实现软删除或两阶段删除。删除采用用户已确认的硬删除策略。
- 不要求第一版同时维护 SQLite 与旧 JSON 的双写一致性。

## 3. 架构

```
用户自然语言
  ↓
talent-library skill / workflow
  ↓
场景路由：import / search / match / score / detail / update / delete
  ↓
复用现有实现：
  - scripts/talent_db.py
  - scripts/talent_migrate.py
  - agents/workflows/platform-match/AGENT.md
  - agents/workflows/screen/AGENT.md
  - scripts/score_pipeline.py
  - scripts/data-manager.py
```

### 3.1 Canonical Workflow

新增：

```
agents/workflows/talent-library/
├── AGENT.md
├── references/
│   ├── scenarios.md
│   ├── data-contract.md
│   └── safety-rules.md
└── assets/
    ├── candidate-table-template.md
    ├── import-report-template.md
    └── delete-confirmation-template.md
```

`agents/workflows/talent-library/AGENT.md` 保存业务流程和场景路由。它只能引用通用能力契约，例如 `file.read`、`file.write`、`shell.run`、`browser.operate`、`human.confirm`，不能写入 Claude Code、Codex 或其他运行时私有工具名称。

### 3.2 Runtime Adapter

新增：

```
.claude/skills/talent-library/
└── SKILL.md
```

`.claude/skills/talent-library/SKILL.md` 只做薄适配：

1. 读取 `agents/capabilities.md`。
2. 读取 `agents/workflows/talent-library/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到当前运行时工具。
4. 严格按 canonical workflow 执行。

业务逻辑不得复制到 `.claude/skills/talent-library/SKILL.md`。

### 3.3 可安装 Codex Skill 包

如果后续需要把它做成可安装 Codex skill，按 `skill-creator` 标准结构生成：

```
talent-library/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── scenarios.md
    ├── data-contract.md
    └── safety-rules.md
```

`SKILL.md` 必须包含且仅包含必要 frontmatter：

```yaml
---
name: talent-library
description: "猎头顾问人才库管理工作流。用于人才导入、人才查询、人才匹配、人才综合评分、JD 匹配评分、人才详情抓取、人才信息更新、人才删除，以及围绕本地 SQLite 人才库 data/talent.db 的候选人管理任务。"
---
```

正文保持简洁，指向本仓库 canonical workflow 和 references。详细场景、数据契约和安全规则放入 references。不要额外创建 README、安装指南或 changelog。

## 4. 场景路由

`talent-library` 根据用户意图路由到 7 个场景。用户无需记命令。

| 场景 | 触发示例 | 主入口 |
| --- | --- | --- |
| `import` | "导入这批脉脉人才"、"把插件导出的 JSON 入库" | `TalentDB.batch_ingest()`、`talent_migrate.py` |
| `search` | "查一下阿里 P8 架构师"、"找上海 8 年以上 Java" | `TalentDB.search()`、`TalentDB.fulltext_search()` |
| `match` | "把人才库和这个 JD 匹配一下" | `screen` workflow、`score_pipeline.py` |
| `score` | "给这些候选人综合评分"、"计算 JD 匹配分" | `update_overall_score()`、`save_match_score()` |
| `detail` | "抓取这个候选人的详情"、"补全这 20 人履历" | `platform-match` workflow、`TalentDB.enrich()` |
| `update` | "更新张三现在在字节"、"合并这个来源" | `TalentDB.enrich()`、新增局部更新 API |
| `delete` | "删除这个候选人"、"删掉重复的人才" | 新增硬删除 API |

路由规则：

1. 意图明确时直接进入对应场景。
2. 意图涉及多个候选人且会写库时，先 dry-run 展示影响范围。
3. 意图模糊时只问一个最小澄清问题。
4. 任何删除、批量更新、评分覆盖都必须等待用户确认。

## 5. 场景流程

### 5.1 人才导入 `import`

支持输入：

- 脉脉 Chrome 插件导出 JSON。
- Boss/脉脉平台搜索结果 JSON。
- 旧 `data/candidates/*.json`。
- 用户提供的单个候选人 JSON。

流程：

1. 识别输入类型和平台来源。
2. 校验 JSON 结构，抽取候选人列表。
3. 平台原始数据先经适配器字段映射；旧 JSON 使用迁移兼容逻辑。
4. 调用 `TalentDB.batch_ingest(candidates, platform)`。
5. 展示 `created`、`merged`、`pending`、`errors` 汇总。
6. 如果存在 `pending_merges`，展示人工确认队列。
7. 生成导入报告到 `data/output/talent-import-{YYYY-MM-DD}-{slug}.md`。

复用：

- `scripts/talent_db.py`
- `scripts/talent_migrate.py`
- `scripts/platform_match/enrich.py map`

实施缺口：

- 如插件导出格式与平台适配器输入不一致，新增轻量解析函数，放在 `scripts/`。
- 不在 skill 文档里写临时 JSON 解析代码。

### 5.2 人才查询 `search`

支持查询维度：

- 基本字段：姓名、公司、职位、城市、学历、工作年限。
- 技能字段：包含任一技能、同时包含多个技能。
- 状态字段：求职状态、数据级别、平台来源、更新时间。
- 评分字段：综合分范围、JD 匹配分范围。
- 关键词：全文搜索。

流程：

1. 将自然语言转为 `CandidateFilter` 和 `SortSpec`。
2. 用户要求关键词搜索时调用 `TalentDB.fulltext_search()`。
3. 用户要求结构化过滤时调用 `TalentDB.search()`。
4. 默认分页展示，每页 20 条。
5. 默认输出字段：姓名、公司、职位、城市、年限、学历、数据级别、综合分、来源平台。
6. 用户要求导出时，生成 `data/output/talent-search-{YYYY-MM-DD}-{slug}.md`。

复用：

- `CandidateFilter`
- `SortSpec`
- `TalentDB.search()`
- `TalentDB.fulltext_search()`

### 5.3 人才匹配 `match`

输入形式：

- `--jd-id <id>` 或用户自然语言提供 JD ID。
- 本地 JD 文件。
- 用户粘贴 JD 文本。
- 用户提供自然语言画像，例如 "AI Infra 方向，10 年以上，大厂技术负责人"。

流程：

1. 读取 JD 或画像。
2. 从人才库初筛候选池。
3. 候选池较大时先按结构化条件和 `overall_score` 粗筛。
4. 需要完整评分时调用 `score_pipeline.py` 或按 `screen` workflow 执行。
5. 写入 `TalentDB.save_match_score()`。
6. 输出 Top N、匹配理由、关键差距、风险点。
7. 生成 `data/output/talent-match-{YYYY-MM-DD}-{jd-slug}.md`。

复用：

- `agents/workflows/screen/AGENT.md`
- `scripts/score_pipeline.py`
- `scripts/jd_analyzer.py`
- `scripts/coarse_screener.py`
- `scripts/llm_ranker.py`
- `scripts/report_generator.py`

### 5.4 人才评分 `score`

评分分为两类：

| 类型 | 含义 | 存储 |
| --- | --- | --- |
| 综合评分 `overall_score` | 候选人自身质量，与具体 JD 无关 | `candidates.overall_score`、`score_events` |
| JD 匹配评分 `match_score` | 候选人对具体 JD 的匹配度 | `match_scores` |

默认规则：

1. 用户提到 JD、职位、岗位匹配时，默认执行 JD 匹配评分。
2. 用户提到"综合评分"、"人才质量"、"候选人质量分"时，执行综合评分。
3. 用户表述不清时，先询问要做哪一种评分。

综合评分第一版可基于候选人完整度、职业轨迹、公司背景、职级、技能稀缺性、求职状态等维度计算。若现有模块无法覆盖，实施阶段新增一个小的业务模块，例如 `scripts/talent_scorer.py`，并通过 `TalentDB.update_overall_score()` 写回。

### 5.5 详情抓取 `detail`

流程：

1. 查询候选人的 `source_profiles`。
2. 已有平台 ID 或 profile URL 时，优先用对应平台详情抓取能力。
3. 没有平台线索时，调用 `platform-match` 搜索并做身份确认。
4. 详情数据经字段映射后调用 `TalentDB.enrich()`。
5. 更新数据级别：`lead` → `core` → `detailed`。
6. 记录来源和抓取时间。

安全边界：

- 身份置信度不足时不得自动写入详情。
- 多结果匹配时必须展示候选项让用户选择。
- 平台抓取遵循 `platform-match` 的 session、限流和熔断规则。

### 5.6 人才更新 `update`

支持：

- 更新结构化字段。
- 补充履历、教育、项目经历。
- 合并来源。
- 修正综合评分。
- 修正 JD 匹配评分。
- 处理待确认合并。

流程：

1. 查询并展示当前记录摘要。
2. 解析用户更新意图。
3. 对写入内容做字段校验。
4. 执行 dry-run，展示将被修改的字段。
5. 用户确认后写入。
6. 写入后展示变更摘要。

复用：

- `TalentDB.enrich()`
- `TalentDB.resolve_merge()`
- `TalentDB.update_overall_score()`
- `TalentDB.save_match_score()`

实施缺口：

- `TalentDB` 当前缺少通用局部更新方法。实施阶段应新增结构化字段更新 API，避免在 workflow 中拼 SQL。

### 5.7 人才删除 `delete`

按用户确认的第一版策略：确认后硬删除。

流程：

1. 根据用户输入定位候选人。
2. 若命中多条，展示候选列表并要求用户选择。
3. 展示删除影响范围：
   - `candidates` 主记录。
   - `candidate_details` 详情。
   - `source_profiles` 来源。
   - `score_events` 综合评分事件。
   - `match_scores` JD 匹配评分。
   - `candidate_vectors` 向量记录，如存在。
   - 旧 JSON 中是否存在对应记录。
4. 要求用户明确确认，例如 "确认删除候选人 123"。
5. 调用数据层硬删除 API。
6. 输出删除摘要。

实施缺口：

- `TalentDB` 当前没有公开删除 API。实施阶段新增 `delete_candidate(candidate_id: int) -> DeleteResult`。
- 删除 API 内部使用事务，并依赖外键级联删除关联表。
- 旧 JSON 同步删除必须单独确认，不作为 SQLite 删除的隐式副作用。

## 6. 数据契约

### 6.1 主库

主数据源为：

```
data/talent.db
```

核心表沿用本地人才库设计：

- `candidates`
- `candidate_details`
- `source_profiles`
- `score_events`
- `match_scores`
- `pending_merges`
- `merge_log`
- `candidate_fts`
- `candidate_vectors`

### 6.2 旧 JSON

旧数据路径：

```
data/candidates/*.json
```

使用规则：

1. 只作为导入、迁移、兼容读取来源。
2. 新增人才默认写 SQLite，不写旧 JSON。
3. 用户明确要求处理旧 JSON 时，才调用 `data-manager.py`。
4. SQLite 删除不自动删除旧 JSON，除非用户单独确认。

### 6.3 输出报告

输出目录：

```
data/output/
```

命名：

| 场景 | 文件名 |
| --- | --- |
| 导入 | `talent-import-{YYYY-MM-DD}-{slug}.md` |
| 查询 | `talent-search-{YYYY-MM-DD}-{slug}.md` |
| 匹配 | `talent-match-{YYYY-MM-DD}-{slug}.md` |
| 评分 | `talent-score-{YYYY-MM-DD}-{slug}.md` |
| 详情补全 | `talent-detail-{YYYY-MM-DD}-{slug}.md` |
| 更新 | `talent-update-{YYYY-MM-DD}-{slug}.md` |
| 删除 | `talent-delete-{YYYY-MM-DD}-{slug}.md` |

短查询可以只在对话中展示，不强制落文件。

## 7. 安全规则

1. 删除必须二次确认。
2. 批量更新和批量删除必须先 dry-run。
3. 来源数据只追加，不静默覆盖。
4. 评分覆盖必须写入事件或匹配记录，不能只改最终分。
5. 平台抓取遵守现有 `platform-match` 限流、session 和熔断规则。
6. 身份匹配置信度不足时，不自动合并或写入详情。
7. 写库操作失败时，必须输出失败原因和已完成/未完成范围。

## 8. 需要新增或调整的实现

第一版尽量复用现有实现，但有三个合理缺口需要补齐：

1. `TalentDB.delete_candidate(candidate_id)`
   支持事务化硬删除，并返回删除影响统计。

2. `TalentDB.update_candidate(candidate_id, patch)`
   支持结构化字段局部更新，避免 workflow 拼 SQL 或整行覆盖。

3. `scripts/talent_library.py` 或等价 CLI
   可选。用于把导入、查询、删除等常用动作封装为稳定命令，降低 agent 直接调用 Python API 的复杂度。如果实现成本过高，第一版 workflow 可先通过短 Python 片段调用 `TalentDB`，但长期应收敛到 CLI。

## 9. 验证策略

实施完成后运行：

```bash
python -m pytest tests scripts -q
```

新增测试建议：

- `test_talent_library_workflow_docs.py`：验证 workflow 不包含运行时私有工具名称。
- `test_talent_db_delete.py`：验证硬删除候选人及关联表。
- `test_talent_db_update.py`：验证局部更新不破坏来源和详情。
- `test_talent_library_import.py`：验证插件导出或平台结果可批量入库。

手动 smoke：

1. 导入 3 条候选人，其中 1 条重复。
2. 查询某公司候选人。
3. 对一个 JD 做匹配评分。
4. 给一个候选人补详情。
5. 更新一个字段。
6. 删除一个测试候选人并确认关联记录消失。

## 10. 实施顺序

1. 新增 `agents/workflows/talent-library/AGENT.md` 和 references/assets。
2. 新增 `.claude/skills/talent-library/SKILL.md` 薄适配器。
3. 补齐 `TalentDB.delete_candidate()` 和测试。
4. 补齐 `TalentDB.update_candidate()` 和测试。
5. 视复杂度新增 `scripts/talent_library.py` CLI。
6. 增加 workflow 架构扫描测试。
7. 跑全量测试。

## 11. 已确认决策

| 决策 | 结果 |
| --- | --- |
| Skill 入口 | 单一聚合 skill：`talent-library` |
| 场景拆分 | 内部 7 个场景路由，不拆成多个独立 skill |
| 主数据源 | SQLite `data/talent.db` |
| 旧 JSON | 迁移和兼容入口 |
| 删除策略 | 用户明确确认后硬删除 |
| 业务逻辑位置 | `agents/workflows/talent-library/AGENT.md` |
| 运行时适配 | `.claude/skills/talent-library/SKILL.md` 薄适配 |

## 12. Spec 自检

- 无待定项或占位符。
- 架构与仓库现有运行时中立约定一致。
- Skill 结构符合 `skill-creator` 标准模板：`SKILL.md` frontmatter、正文说明、`agents/openai.yaml` 可选、references 按需加载、无额外 README。
- 范围聚焦在人才库管理 skill 设计，不包含平台抓取重写或评分模型重构。
- 已明确 SQLite 主库、旧 JSON 兼容边界和硬删除安全规则。
