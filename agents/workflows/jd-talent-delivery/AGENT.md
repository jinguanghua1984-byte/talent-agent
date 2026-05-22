---
name: jd-talent-delivery
description: "JD 本地人才库推荐和飞书知识库交付。用于读取 JD、生成岗位画像、构建评分卡、匹配 data/talent.db、输出 TopN 推荐和外联表，并发布到飞书知识库 JD需求交付。"
---

# jd-talent-delivery 工作流

`jd-talent-delivery` 是运行时中立的 canonical workflow。它只描述业务编排、产物合同和安全边界；运行时适配器必须先读取 `agents/capabilities.md`，再把通用能力映射到当前环境。

## 触发入口

以下意图进入本工作流：

- 按 JD 做本地人才库推荐、匹配、评分或 TopN 候选人交付。
- 基于 JD 生成岗位画像、评分卡、人才推荐报告和外联表。
- 将 JD 推荐结果发布到飞书知识库 `JD需求交付`。
- 从 `skills/jd-talent-delivery/SKILL.md` 完成业务入口解析后自动交接执行。

如果用户没有提供 JD 正文或可读路径，只问一个最小澄清问题。除非用户明确覆盖，默认 `top_n=30`、`publish_feishu=true`、`wiki_space_id=7642607697183001542`。

## 资源索引

| 资源 | 用途 |
| --- | --- |
| `agents/capabilities.md` | 运行时中立能力契约 |
| `agents/workflows/talent-library/AGENT.md` | 本地人才库候选人读取、匹配和报告边界 |
| `agents/workflows/talent-library/references/data-contract.md` | `data/talent.db`、输出目录和 TalentDB API 契约 |
| `agents/workflows/talent-library/references/safety-rules.md` | 人才库写入、评分、详情和批量操作安全规则 |
| `skills/jd-talent-delivery/SKILL.md` | 业务入口、默认参数和交接合同 |
| `data/talent.db` | 只读人才库主数据源 |
| `lark-cli` | 飞书 Docs、Sheets、Drive、Wiki 发布能力 |

目标飞书知识库为 `JD需求交付`，默认 `space_id=7642607697183001542`。

## 阶段

### S0：前置检查

1. 解析 JD 输入、`top_n`、`publish_feishu` 和 `wiki_space_id`。
2. 读取 `agents/capabilities.md`，确认当前运行时具备文件读写、命令执行和人工确认能力。
3. 读取 `agents/workflows/talent-library/AGENT.md`、`agents/workflows/talent-library/references/data-contract.md` 和 `agents/workflows/talent-library/references/safety-rules.md`。
4. 确认 `data/talent.db` 存在且本流程仅以只读方式打开。
5. 如果 `publish_feishu=true`，先执行 `lark-cli doctor` 和 `lark-cli auth status`；认证失败、权限不足或 scope 缺失时停止。

### S1：建立输出目录

创建 `data/output/<jd-slug>-<YYYY-MM-DD>/`，并写入：

- `source/jd.md`
- `run-manifest.json`

所有后续过程输出都必须在该目录下。不得把临时文件写到运行时私有目录。

### S2：岗位画像

复用 `hr-talent` 的岗位分析框架生成：

- `profile/role-deep-dive.md`
- `profile/role-profile.json`

岗位画像至少包含结论摘要、岗位真实问题、能力模型、候选人类型、寻访关键点、公司池、关键词、排除项和风险项。岗位画像是后续评分卡、粗筛、精排和报告的唯一 JD 解释来源。

### S3：评分卡

从岗位画像生成 `scoring/scorecard.json`。评分卡至少包含：

- 评分维度和权重。
- must-have、nice-to-have、排除项和风险规则。
- 目标公司池、标题别名、关键词和证据字段。
- A/B/C/淘汰或强推荐/推荐/观察/不推荐的推荐阈值。

评分卡写入后，后续阶段只能读取该文件，不得在粗筛或精排阶段重新发明维度。

### S4：人才库粗筛

以只读方式读取 `data/talent.db`，输出：

- `scoring/coarse-screen.json`
- `scoring/coarse-screen.md`

粗筛和精排必须读取同一个 `scoring/scorecard.json`。粗筛只做召回、硬过滤、风险预标记和粗分；粗筛不得新增精排不存在的评分维度。粗筛命中不足时，应报告召回缺口和可调参数，不得发起新的平台搜索。

### S5：人才库精排

对粗筛候选池生成：

- `scoring/detailed-rank.json`
- `scoring/detailed-rank.md`

精排不得重新解释 JD，只能使用 `profile/role-profile.json` 和 `scoring/scorecard.json`。精排证据必须可追溯到人才库字段或已生成的岗位画像。维度、权重、阈值必须写入报告。

### S6：报告和外联表

生成：

- `reports/talent-recommendation.md`
- `reports/talent-recommendation.json`
- `reports/outreach-queue.csv`
- `reports/outreach-queue.md`

推荐报告必须展示 JD 摘要、评分卡版本、维度、权重、阈值、TopN 候选人证据、风险项和建议动作。外联表必须只包含交付所需字段，不包含平台原始 payload、raw detail 或数据库文件路径。

### S7：飞书发布

发布前必须生成 `feishu/publish-manifest.json`，并完成 Wiki 目录 dry-run、Markdown 导入 dry-run 和 CSV 导入 dry-run。Markdown 使用 `drive +import --type docx` 后移动到 Wiki；CSV 使用 `drive +import --type sheet` 后移动到 Wiki。

发布后写入：

- `feishu/dry-run-results.json`
- `feishu/publish-results.json`

发布完成后回读 Wiki 子节点、文档 outline 和表格前几行，确认交付包位于 `JD需求交付` 下。

## Scorecard 一致性

1. 粗筛和精排必须读取同一个 `scoring/scorecard.json`。
2. 粗筛不得新增精排不存在的评分维度。
3. 精排不得重新解释 JD。
4. 维度、权重、阈值必须写入报告。
5. 如需修改维度、权重或阈值，必须回到 S3 重新生成评分卡，并让 S4-S6 全量重跑。

## 安全边界

- `data/talent.db` 只读。
- 不写 `match_scores`。
- 不发起新的脉脉搜索、Boss 搜索或浏览器抓取。
- 不上传 SQLite DB。
- 不上传 sync zip。
- 不上传 raw search。
- 不上传 raw detail。
- 不上传 raw capture 或平台原始 payload。
- 不自动追加 `--yes`。
- 不绕过 `lark-cli` dry-run 直接发布。
- 不把候选人隐私字段扩散到非交付文档。

## 停机条件

遇到以下情况必须停止，保留已生成产物，并在当前输出目录写入阶段错误证据：

- JD 输入缺失或不可读。
- `data/talent.db` 缺失、不可读或无法以只读方式打开。
- `scoring/scorecard.json` 缺失、无法解析或与粗筛/精排维度不一致。
- 推荐报告或外联表缺少必要字段。
- 认证失败。
- 权限不足。
- scope 缺失。
- Wiki 目标不存在且不能创建。
- dry-run 失败。
- `lark-cli` flag 漂移或返回不可解释错误。
- `feishu/publish-manifest.json` 中出现 SQLite、sync zip、raw search、raw detail、raw capture 或平台原始 payload 路径。
