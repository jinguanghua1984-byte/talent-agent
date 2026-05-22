# JD Talent Delivery Skill Design

## 背景

本设计新增一个仓库内业务 skill，用于把单个 JD 从需求输入推进到本地人才库推荐和飞书知识库交付。该流程不同于 `maimai-talent-search-campaign`：它不默认发起新的脉脉寻访 campaign，而是先基于 `data/talent.db` 做只读匹配、生成推荐报告和外联表，再把交付物发布到飞书知识库 `JD需求交付`。

目标是形成可复用、可审计、可验证的工作流：

1. 所有过程输出集中在 `data/output/<jd-slug>-<YYYY-MM-DD>/`。
2. 岗位画像复用 `hr-talent` 的岗位分析框架，结构参考 `docs/business-requirements/2026-05-21-llm-inference-role-deep-dive.md`。
3. 粗筛和精排共用同一份 `scorecard.json`，避免评分口径漂移。
4. 飞书发布默认真实执行，但发布前必须通过认证、目标 Wiki 和 dry-run 预检。

## 范围

本次实现包括：

- 新增 `skills/jd-talent-delivery/SKILL.md`。
- 新增 canonical workflow：`agents/workflows/jd-talent-delivery/AGENT.md`。
- 新增少量脚本，把 JD、岗位画像、评分卡、人才库匹配、外联 CSV 和飞书发布 manifest 串起来。
- 新增测试，覆盖 skill 触发、workflow 分层、评分一致性、输出目录、飞书发布边界。

本次不包括：

- 不发起新的脉脉搜索或浏览器抓取。
- 不自动写入或覆盖 `data/talent.db` 的候选人、详情或 `match_scores`。
- 不上传 SQLite DB、sync zip、raw capture 或包含平台原始 payload 的敏感文件。
- 不替代 `maimai-talent-search-campaign` 的无人值守寻访能力。

## 用户入口

Skill 名称：`jd-talent-delivery`。

典型触发语义：

- `按 JD 做人才库推荐`
- `基于这个 JD 生成岗位画像和 Top30 人才推荐`
- `把 JD 推荐结果推送到飞书 JD需求交付`
- `用本地人才库匹配这个岗位`
- `生成岗位画像、人才推荐报告和外联表`

参数：

- `jd_path`：本地 JD 文件路径，必填，除非用户在消息中直接粘贴 JD。
- `top_n`：推荐人数，默认 `30`。
- `output_root`：默认 `data/output/<jd-slug>-<YYYY-MM-DD>/`。
- `publish_feishu`：默认 `true`。
- `wiki_space_id`：默认 `7642607697183001542`，对应飞书知识库 `JD需求交付`。

## 输出目录

执行前创建工作目录：

```text
data/output/<jd-slug>-<YYYY-MM-DD>/
  source/
    jd.md
  profile/
    role-deep-dive.md
    role-profile.json
  scoring/
    scorecard.json
    coarse-screen.json
    detailed-rank.json
  reports/
    talent-recommendation.md
    talent-recommendation.json
    outreach-queue.csv
    outreach-queue.md
  feishu/
    publish-manifest.json
    dry-run-results.json
    publish-results.json
```

`<jd-slug>` 从 JD 标题、文件名或岗位名生成。文件夹名必须可重复推导，并在 manifest 中记录原始 JD 路径、生成时间、top_n 和 scoring 版本。

## 架构

采用 skill -> workflow -> scripts 的三层架构：

1. `skills/jd-talent-delivery/SKILL.md`
   - 负责识别业务意图、读取 JD 输入、声明默认值和交付边界。
   - 不直接执行数据库写入、浏览器动作或飞书发布。
   - 指向 canonical workflow。

2. `agents/workflows/jd-talent-delivery/AGENT.md`
   - 负责运行时中立的业务编排。
   - 规定必须先读取 `agents/capabilities.md`、`talent-library` 数据契约和飞书相关 skill。
   - 明确只读主库、发布前 dry-run、异常停机和可恢复状态。

3. `scripts/`
   - `jd_talent_delivery_profile.py`：把 JD 和 `hr-talent` 分析要求落成岗位画像 Markdown/JSON。
   - `jd_talent_delivery_scorecard.py`：从岗位画像生成统一评分卡。
   - `jd_talent_delivery_match.py`：读取 `data/talent.db`，基于同一评分卡执行粗筛和精排。
   - `jd_talent_delivery_feishu.py`：生成发布 manifest，执行飞书 dry-run 和真实发布。

脚本命名可以在实现时按现有模块风格微调，但职责边界不得合并成一个不可测试的大脚本。

## 数据流

1. 读取 JD。
2. 复制 JD 到 `source/jd.md`。
3. 生成岗位画像：
   - 结论摘要
   - 岗位真实问题
   - 能力模型
   - 候选人类型
   - 寻访关键点
   - 公司池与团队优先级
   - 搜索/匹配关键词
   - 排除项和风险项
4. 生成 `scorecard.json`：
   - `dimensions`
   - `weights`
   - `must_have_terms`
   - `nice_to_have_terms`
   - `company_pools`
   - `title_aliases`
   - `exclusion_terms`
   - `risk_rules`
   - `evidence_fields`
   - `label_thresholds`
5. 粗筛：
   - 读取候选人的基础字段、来源、简历详情和技能标签。
   - 用 `scorecard.json` 做召回、硬过滤和初步评分。
   - 输出 `coarse-screen.json`，包含进入精排候选池和被排除原因。
6. 精排：
   - 只对粗筛候选池做详细评分。
   - 仍使用同一份 `scorecard.json` 的维度和权重。
   - 输出 `detailed-rank.json`。
7. 报告：
   - 生成 TopN 推荐报告。
   - 生成外联 CSV 和 Markdown。
8. 飞书发布：
   - 创建或复用 `JD需求交付 / <JD一级目录>`。
   - 上传 JD、岗位画像、推荐报告。
   - 将外联 CSV 导入为 Sheet。
   - 将所有云端资源移动到 JD 一级目录下。
   - 回读 Wiki 子节点、Doc outline 和 Sheet 前几行作为验证。

## 评分一致性

评分一致性是核心验收点。

规则：

1. 粗筛和精排必须引用同一个 `scorecard.json`。
2. 粗筛不得引入精排没有的岗位维度；只能做召回、硬过滤、风险预标记和粗分。
3. 精排不得重新解释 JD；只能使用岗位画像和评分卡。
4. 报告必须展示评分维度、权重、推荐阈值、TopN 证据和风险。
5. 测试必须覆盖同一个候选人在粗筛和精排中的维度名称一致。

推荐标签：

- `强推荐`
- `推荐`
- `观察`
- `不推荐`

外联优先级：

- `P0`：强推荐且无硬风险。
- `P1`：推荐，或强推荐但需人工复核风险。
- `P2`：观察但有潜在价值。
- `P3`：不进入主动外联，仅保留为误判样本或后续校准。

## 飞书发布

目标知识库：

- 名称：`JD需求交付`
- `space_id=7642607697183001542`

目录结构：

```text
JD需求交付
  <JD一级目录>
    JD需求
    岗位画像
    人才推荐报告
    外联表
```

默认真实发布，但必须先执行：

1. `lark-cli doctor`
2. `lark-cli auth status`
3. Wiki space/node dry-run
4. Markdown/CSV 导入 dry-run

发布策略：

- Markdown 优先用 `drive +import --type docx`，再 `wiki +move`。
- CSV 优先用 `drive +import --type sheet`，再 `wiki +move`。
- 不依赖 `sheets +append --file`，因为当前环境已验证该 flag 不可用。
- 发布后必须回读 Wiki 子节点、Doc outline 和 Sheet 前几行。

如果认证、权限、scope、CLI flag、Wiki 节点或导入任务出现异常，workflow 必须停止，写入 `feishu/publish-manifest.json` 和错误证据，不继续真实发布。

## 安全边界

- `data/talent.db` 默认只读。
- 不写 `match_scores`，除非未来用户明确要求评分入库并单独确认。
- 不上传数据库、备份、sync bundle、raw search、raw detail、raw capture 或平台原始 payload。
- 发布 CSV 前必须过滤敏感路径字段和内部 raw 字段。
- 飞书发布用 `--as user` 优先，除非用户明确要求 bot。
- 遇到 `confirmation_required` 不自动追加 `--yes`，除非用户已对该高风险动作显式授权。

## 测试计划

新增测试：

- `tests/test_jd_talent_delivery_skill.py`
  - 验证 skill frontmatter、中文语义触发、输出目录、默认 top_n、飞书发布边界。
- `tests/test_jd_talent_delivery_workflow.py`
  - 验证 canonical workflow 存在、运行时中立、引用能力和安全边界。
- `tests/test_jd_talent_delivery_scorecard.py`
  - 验证岗位画像到 scorecard 的字段完整性。
  - 验证粗筛和精排共享维度、权重和阈值。
- `tests/test_jd_talent_delivery_feishu.py`
  - 验证 manifest 不包含 DB、zip、raw 路径。
  - 验证 CSV 发布走 `drive +import --type sheet` 而非 `sheets +append --file`。

聚焦验证命令：

```powershell
python -m pytest tests/test_jd_talent_delivery_skill.py tests/test_jd_talent_delivery_workflow.py tests/test_jd_talent_delivery_scorecard.py tests/test_jd_talent_delivery_feishu.py -q
```

最终回归：

```powershell
python -m pytest tests scripts -q
```

## 验收标准

1. 给定 JD 文件和默认参数，能生成 `data/output/<jd-slug>-<YYYY-MM-DD>/`。
2. 输出目录包含 JD 副本、岗位画像、评分卡、粗筛结果、精排结果、推荐报告、外联 CSV 和飞书 manifest。
3. TopN 默认 30，可通过参数覆盖。
4. 粗筛和精排的维度、权重和阈值来自同一份 `scorecard.json`。
5. 推荐报告格式接近 `data/output/talent-match-2026-05-21-llm-inference.md`，但标题、维度和证据来自当前 JD。
6. 外联 CSV 字段兼容 `data/campaigns/llm-inference-2026-05-20/reports/outreach-execution-queue-detail-all-pack-001.csv`。
7. 飞书知识库 `JD需求交付` 下出现以 JD 命名的一级目录，目录下有 JD、岗位画像、人才推荐报告和外联表。
8. 发布结果有本地 JSON 记录和云端回读证据。

## 迁移与扩展

后续可以扩展：

- 将人工反馈写成 `feedback/*.json`，用于下一轮 scorecard 校准。
- 增加可选的 `match_scores` 写库流程，但必须单独 dry-run 和确认。
- 在本地人才库推荐不足时，交接到 `maimai-talent-search-campaign` 发起外部寻访。
- 对飞书 Sheet 增加冻结表头、下拉状态和负责人字段，但不作为本次首版要求。
