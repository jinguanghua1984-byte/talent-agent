---
name: talent-library
description: "猎头顾问人才库管理。用于人才导入、人才查询、人才匹配、人才综合评分、JD 匹配评分、人才详情抓取、人才信息更新、人才删除，以及围绕本地 SQLite 人才库 data/talent.db 的候选人管理任务。触发词: 人才库、候选人库、导入人才、查询人才、匹配人才、人才评分、抓取详情、更新人才、删除人才、talent library、/talent-library"
---

# talent-library 工作流

`talent-library` 是本地人才库的运行时中立 canonical workflow。它只描述业务编排和安全边界，具体运行时必须先读取 `agents/capabilities.md`，再把通用能力映射到当前环境。

## 触发入口

以下意图进入本工作流：

- `/talent-library` 或包含 talent library 的明确调用。
- 围绕候选人库的自然语言任务，例如导入人才、查询人才、匹配人才、人才评分、抓取详情、更新人才、删除人才。
- 围绕 `data/talent.db` 的候选人管理任务。

入口解析后先判断场景：`import`、`search`、`match`、`score`、`detail`、`update`、`delete`。如果用户意图模糊，只问一个最小澄清问题。

## 前置检查

1. 读取 `agents/capabilities.md`，确认当前运行时可用的通用能力。
2. 确认主数据源 `data/talent.db` 是否存在；不存在时说明需要先初始化或执行迁移。
3. 对写库场景读取 `agents/workflows/talent-library/references/safety-rules.md`。
4. 对数据输入、输出和 API 边界读取 `agents/workflows/talent-library/references/data-contract.md`。
5. 对具体场景流程读取 `agents/workflows/talent-library/references/scenarios.md`。

## 资源索引

| 资源 | 用途 |
| --- | --- |
| `agents/capabilities.md` | 运行时中立能力契约 |
| `data/talent.db` | SQLite 人才库主数据源 |
| `agents/workflows/talent-library/references/scenarios.md` | 七类业务场景流程 |
| `agents/workflows/talent-library/references/data-contract.md` | 数据源、输出目录和 TalentDB API 契约 |
| `agents/workflows/talent-library/references/safety-rules.md` | 写库、删除、抓取和评分安全规则 |
| `agents/workflows/talent-library/assets/candidate-table-template.md` | 候选人列表展示模板 |
| `agents/workflows/talent-library/assets/import-report-template.md` | 导入报告模板 |
| `agents/workflows/talent-library/assets/delete-confirmation-template.md` | 删除确认模板 |
| `agents/workflows/platform-match/AGENT.md` | 平台搜索、详情抓取、限流、session 和熔断规则 |
| `agents/workflows/screen/AGENT.md` | JD 筛选和匹配评分 workflow |
| `scripts/score_pipeline.py` | 批量评分和排序流水线 |
| `docs/superpowers/specs/2026-05-10-talent-library-skill-design.md` | talent-library 设计规格 |

## 场景路由

| 场景 | 触发示例 | 主入口 |
| --- | --- | --- |
| `import` | 导入这批人才、把平台结果入库 | `TalentDB.batch_ingest()` |
| `search` | 查找某公司候选人、找上海 8 年以上 Java | `TalentDB.search()`、`TalentDB.fulltext_search()` |
| `match` | 用这个 JD 匹配人才库、找最适合的候选人 | `agents/workflows/screen/AGENT.md`、`scripts/score_pipeline.py` |
| `score` | 给候选人综合评分、计算 JD 匹配分 | `TalentDB.update_overall_score()`、`TalentDB.save_match_score()` |
| `detail` | 抓取候选人详情、补全履历 | `agents/workflows/platform-match/AGENT.md`、`TalentDB.enrich()` |
| `update` | 更新字段、合并来源、修正分数 | `TalentDB.update_candidate()`、`TalentDB.enrich()` |
| `delete` | 删除候选人、删除重复人才 | `TalentDB.delete_candidate()` |

路由原则：

1. 明确意图直接进入对应场景。
2. 一次请求包含多个场景时，先读后写，先 dry-run 后确认。
3. 任何删除、批量写入、批量更新、评分覆盖都必须先展示影响范围。
4. 不确定身份、来源或匹配置信度时，不自动合并或写入详情。

## 主数据源

`data/talent.db` 是第一版主数据源。旧 JSON 只作为迁移、兼容读取或用户明确要求的输入来源，不作为默认写入目标。

输出报告统一写入 `data/output/`，短查询可以只在对话中展示。报告命名遵循 `talent-{scenario}-{YYYY-MM-DD}-{slug}.md`。

## 场景执行

执行具体场景时，必须读取 `agents/workflows/talent-library/references/scenarios.md` 并按对应二级标题执行。涉及平台抓取和详情补全时，复用 `agents/workflows/platform-match/AGENT.md`；涉及 JD 匹配评分时，复用 `agents/workflows/screen/AGENT.md` 或 `scripts/score_pipeline.py`。

`detail` 场景支持扩展参数：

- `--ids <candidate_id,candidate_id>`：从人才库候选人 ID 生成脉脉批量详情目标 JSON。
- `--top10-file <path>`：从 `talent-library match/search` 的 TopN 结构化推荐 JSON 生成脉脉批量详情目标 JSON。
- `--recommendation-file <path>`：从包含 `top10`、`candidates`、`matches`、`results` 或 `items` 的推荐 JSON 生成脉脉批量详情目标 JSON。
- `--out <path>`：指定给 `maimai-scraper` 导入的目标 JSON 路径；未指定时写入 `data/output/maimai-detail-targets-{YYYY-MM-DD}.json`。

运行时接收到上述参数时，应调用本仓库统一业务入口 `scripts/talent_library.py detail`，而不是要求用户直接调用底层转换脚本。

所有数据库读写都通过 TalentDB API 完成，不在 workflow 中拼接 SQL。

## 安全执行

写库前读取 `agents/workflows/talent-library/references/safety-rules.md`。删除必须二次确认；批量写必须 dry-run；来源只追加；评分必须写事件或匹配记录；平台抓取必须遵守 `agents/workflows/platform-match/AGENT.md` 的限流、session 和熔断规则；写库失败必须报告已完成和未完成范围。
