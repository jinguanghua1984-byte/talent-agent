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
- 从 `agents/skills/jd-talent-delivery/SKILL.md` 完成业务入口解析后自动交接执行。

如果用户没有提供 JD 正文或可读路径，只问一个最小澄清问题。除非用户明确覆盖，默认 `top_n=30`、`publish_feishu=true`、`wiki_space_id=7642607697183001542`。

## 连续执行规则

输入齐全且所有门禁通过时，必须按 S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 顺序连续执行到完成。阶段成功输出即为进入下一阶段的授权，不得在 S1-S8 之间询问是否继续、是否发布或是否发送通知。

dry-run、回读和质量门禁都是自动验证门禁；通过即继续，失败才停止。停机条件是本 workflow 正常路径中的唯一中断来源；停机时保留已生成产物并写入阶段错误证据。除初始 JD 输入缺失时的最小澄清问题外，本 workflow 不要求人工二次确认。

## 资源索引

| 资源 | 用途 |
| --- | --- |
| `agents/capabilities.md` | 运行时中立能力契约 |
| `agents/workflows/talent-library/AGENT.md` | 本地人才库候选人读取、匹配和报告边界 |
| `agents/workflows/talent-library/references/data-contract.md` | `data/talent.db`、输出目录和 TalentDB API 契约 |
| `agents/workflows/talent-library/references/safety-rules.md` | 人才库写入、评分、详情和批量操作安全规则 |
| `agents/skills/jd-talent-delivery/SKILL.md` | 业务入口、默认参数和交接合同 |
| `data/talent.db` | 只读人才库主数据源 |
| `lark-cli` | 飞书 Docs、Sheets、Drive、Wiki 发布和 IM 通知能力 |

目标飞书知识库为 `JD需求交付`，默认 `space_id=7642607697183001542`。

## 阶段

### S0：前置检查

1. 解析 JD 输入、`top_n`、`publish_feishu` 和 `wiki_space_id`。
2. 读取 `agents/capabilities.md`，校验当前运行时具备文件读写、命令执行和错误证据落盘能力；该校验不得触发人工二次确认。
3. 读取 `agents/workflows/talent-library/AGENT.md`、`agents/workflows/talent-library/references/data-contract.md` 和 `agents/workflows/talent-library/references/safety-rules.md`。
4. 确认 `data/talent.db` 存在且本流程仅以只读方式打开。
5. 如果 `publish_feishu=true`，先执行 `lark-cli doctor` 和 `lark-cli auth status`；认证失败、权限不足、Sheets/Docs/Wiki/IM scope 缺失时停止。

### S1：建立输出目录

运行 `prepare` 入口创建独立输出目录。首次运行使用 `data/output/<jd-slug>-<YYYY-MM-DD>/`；如果该目录已经存在且非空，必须分配 `data/output/<jd-slug>-<YYYY-MM-DD>-run-NNN/`，不得复用非空目录。

运行时入口：

```powershell
python -m scripts.jd_talent_delivery prepare --jd-path <jd_path> --output-base data/output --top-n <N>
```

命令完成后必须读取 `run-manifest.json` 的实际 `output_dir`，并把它作为本次运行根目录。所有后续过程输出都必须写在该 `output_dir` 下，不得假设固定目录名，也不得把临时文件写到运行时私有目录。

S1 至少写入：

- `source/jd.md`
- `run-manifest.json`

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

本流程不要求存在 campaign `strategy.json`，也不要求存在历史 `*rank*.json`。这些 artifact 只能作为人工排障或历史参考，不能作为 S4/S5 的前置条件。标准执行入口必须能仅凭 `scoring/scorecard.json` 和只读 `data/talent.db` 生成粗筛、精排和 TopN 交付。

### S6：报告和外联表

生成：

- `reports/talent-recommendation.md`
- `reports/talent-recommendation.json`
- `reports/outreach-queue.csv`
- `reports/outreach-queue.md`
- `reports/quality-gates.json`

推荐报告必须展示 JD 摘要、评分卡版本、维度、权重、阈值、TopN 候选人证据、风险项和建议动作。外联表必须只包含交付所需字段，不包含平台原始 payload、raw detail 或数据库文件路径。

发布前质量门禁必须检查：

- 脉脉详情页 URL 必须保留可打开所需的 `trackable_token`，同时清洗 UTM、`show_tip` 和详情抓取用非必要参数，只保留 `dstu` 与 `trackable_token`。
- TopN 全部为 C/淘汰时必须停止发布，并报告需要人工复核或重跑评分卡。
- CSV 必须可解析且行数等于 TopN，关键列必须包含 `candidate_id`、公司、职位、分数、评级、外联角度和 profile URL。
- 候选人卡片必须包含可追溯关键证据，外联角度应包含公司和职位。
- 除 `profile_url` 字段里的脉脉详情页 `trackable_token` 外，发布包不得包含 token、cookie、DB/zip/raw/sync bundle 路径或乱码标记。

### S7：飞书发布

发布前必须生成 `feishu/publish-manifest.json`，并完成 Wiki 目录 dry-run、Markdown 导入 dry-run、Sheet 创建 dry-run 和 Sheet UTF-8 JSON 写入 dry-run。dry-run 成功后必须直接执行真实发布，不得要求人工二次确认；只有认证失败、权限不足、scope 缺失、dry-run 失败、质量门禁 blocked 或回读不一致时才停止。

Markdown 使用 `drive +import --type docx` 后移动到 Wiki。外联表禁止使用 `drive +import --type sheet` 或任何 CSV 文件导入路径；必须使用 `sheets +create` 创建空电子表格，再把本地 `reports/outreach-queue.csv` 解析为二维数组，通过 `sheets +write --values <UTF-8 JSON>` 分块写入，最后 `wiki +move` 到目标目录。

lark-cli 必须通过 argv list 调用，不得把 JSON、中文、URL 拼成 PowerShell 字符串执行。包含中文 JSON payload 的 `sheets +create` / `sheets +write` 必须走显式 Node `@larksuite/cli/scripts/run.js` 入口或等价 UTF-8 argv runner，避免 Windows `.cmd` shim 和 PowerShell 编码链路。发布后必须回读 Wiki 子节点、Doc outline 和 Sheet；Sheet 回读必须比对本地 CSV 表头和前几行。回读是验证，不是乱码修复兜底；如果回读不一致，视为发布失败，必须修正发布器而不是手工改云端数据。

发布后写入：

- `feishu/dry-run-results.json`
- `feishu/publish-results.json`

发布完成后回读 Wiki 子节点、文档 outline 和表格前几行，确认交付包位于 `JD需求交付` 下。发布成功并回读通过后继续 S8。

### S8：飞书完成通知

S7 全部发布和回读通过后，必须发送飞书 IM 完成通知。默认通知目标为 `JD需求协同` 群，必须先用 user 身份搜索群并解析 `chat_id`；如果运行参数提供 `--notify-user-id` 或 `--notify-chat-id`，使用显式目标。默认发送方式固定为：

```powershell
lark-cli im +chat-search --as user --query "JD需求协同" --disable-search-by-user --search-types "private,public_joined,external" --page-size 10 --format json
lark-cli im +messages-send --as user --chat-id <chat_id> --text <message> --idempotency-key <stable_key>
```

显式个人覆盖目标时才使用：

```powershell
lark-cli im +messages-send --as user --user-id <open_id> --text <message> --idempotency-key <stable_key>
```

消息模板固定包含以下段落：

```text
<JD标题> 推荐结果已发布

任务执行结果：<发布状态、质量门禁、外联表行数>
成果物清单：
- Wiki目录：<wiki_url>
- JD：<jd_docx_url>
- 岗位画像：<profile_docx_url>
- 推荐报告：<recommendation_docx_url>
- 外联表：<sheet_url>

推荐报告摘要：
- 匹配口径：本地人才库只读；粗筛 <coarse_total> 人，精排 <total_scored> 人。
- Top<N>：A=<A>/B=<B>/C=<C>/淘汰=<淘汰>
- 注意：<低置信或风险说明；无则写“无”>
```

通知发送后必须写入：

- `feishu/im-notification-message.txt`
- `feishu/im-notification-results.json`

通知发送失败属于任务失败，不得只在聊天窗口口头说明。

### S9：猎头反馈回收（可选后续）

S9 不属于默认连续执行链路，只有用户要求回收或编译猎头反馈时才执行。S9 读取已发布的外联表反馈列或本地反馈 JSON，生成本地反馈产物：

- `feedback/delivery-feedback.json`
- `feedback/parse-review-queue.json`
- `feedback/feedback-summary.json`
- `feedback/calibration-suggestions.json`

外联表对业务只暴露一个反馈列：`feedback_note`。不得再要求业务填写 `feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note` 或布尔跟进列。回收外联表后，使用解析命令：

```bash
python -m scripts.jd_feedback_note_parser parse-csv --run-root <run_root>
```

解析器按规则优先、复杂反馈批量 AI 解析的顺序，把 `feedback_note` 转为内部结构化字段：`feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note`。低置信度、被降级或需要人工复核的行写入 `feedback/parse-review-queue.json`，默认不得进入校准统计。

反馈编译指标至少包含 `accepted_at_30`、`bad_at_10`、原因分布和 grade acceptance rate。输出只能作为下一轮岗位画像、评分卡和匹配策略的校准建议。S9 不得写入 data/talent.db，不得写入 `data/talent.db`，不得自动修改 `scoring/scorecard.json`，不得把猎头备注自动发布到 Wiki。

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
- 本 workflow 正常路径不包含需要 `--yes` 的高风险写操作。
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
- `lark-cli` 返回 `confirmation_required` 或要求追加 `--yes`。
- `lark-cli` flag 漂移或返回不可解释错误。
- `feishu/publish-manifest.json` 中出现 SQLite、sync zip、raw search、raw detail、raw capture 或平台原始 payload 路径。
- `reports/quality-gates.json` 状态为 blocked。
- Sheet 回读与本地 CSV 表头或前几行不一致。
- 外联表发布步骤出现 `drive +import --type sheet`。
- 飞书完成通知发送失败或未写入 `feishu/im-notification-results.json`。
