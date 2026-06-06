---
name: jd-talent-delivery
description: Use when the user asks to turn a JD into a local talent-library recommendation package, generate a role profile and TopN talent recommendation, build an outreach queue, or publish the result to Feishu Wiki JD需求交付.
---

# jd-talent-delivery

## 目标

把一个 JD 从业务输入推进到本地人才库推荐和飞书知识库交付。这个 Skill 只负责业务入口、默认参数、输出 contract、安全边界和自动交接；真实执行逻辑由 canonical workflow `agents/workflows/jd-talent-delivery/AGENT.md` 编排。

## 语义触发

用户没有显式写出 Skill 名称时，只要语义是在“根据 JD 做本地人才库推荐并交付飞书”，也应使用本 Skill。典型触发包括：

- `按 JD 做人才库推荐`
- `基于这个 JD 生成岗位画像和 Top30 人才推荐`
- `把 JD 推荐结果推送到飞书 JD需求交付`
- `用本地人才库匹配这个岗位`
- `生成岗位画像、人才推荐报告和外联表`

## 默认参数

- `top_n=30`
- `publish_feishu=true`
- `wiki_space_id=7642607697183001542`
- 输入齐全后自动从 S0 连续执行到 S8，不需要阶段间人工二次确认。
- 输出目录：首次运行使用 `data/output/<jd-slug>-<YYYY-MM-DD>/`；如果该目录已经存在且非空，必须分配 `data/output/<jd-slug>-<YYYY-MM-DD>-run-NNN/`。
- 后续所有产物必须使用 `run-manifest.json` 中的实际 `output_dir`，不得假设固定目录名。

## 输出产物

每次执行必须创建独立输出目录，并至少写入这些产物：

- `run-manifest.json`
- `source/jd.md`
- `profile/role-deep-dive.md`
- `profile/role-profile.json`
- `scoring/scorecard.json`
- `scoring/coarse-screen.json`
- `scoring/detailed-rank.json`
- `reports/talent-recommendation.md`
- `reports/outreach-queue.csv`
- `feishu/publish-manifest.json`
- `feishu/publish-results.json`
- `feishu/im-notification-results.json`

## 猎头反馈后续

当用户要求回收或分析猎头反馈时，外联表对业务只暴露 `feedback_note` 一个反馈列。使用 `python -m scripts.jd_feedback_note_parser parse-csv --run-root <run_root>` 调用 `jd_feedback_note_parser`，按规则优先、复杂反馈批量 AI 解析的顺序，把自然语言反馈解析为内部 `feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note`。低置信度、被降级或需要人工复核的行写入 `feedback/parse-review-queue.json`，默认不得进入校准统计。

本步骤输出 `feedback/delivery-feedback.json`、`feedback/parse-review-queue.json`、`feedback/feedback-summary.json` 和 `feedback/calibration-suggestions.json`。指标至少包含 `accepted_at_30`、`bad_at_10`、原因分布和 grade acceptance rate。本步骤只生成校准建议，不写 `data/talent.db`，不自动修改评分卡，不自动发布猎头备注。

## 岗位画像 contract

岗位画像必须复用 `hr-talent` 的岗位分析框架，结构参考 `docs/business-requirements/2026-05-21-llm-inference-role-deep-dive.md`。画像至少覆盖结论摘要、岗位真实问题、能力模型、候选人类型、寻访关键点、公司池、关键词、排除项和风险项。

## 评分一致性

粗筛和精排必须引用同一个 `scorecard.json`。粗筛只做召回、硬过滤、风险预标记和粗分；精排不得重新解释 JD，只能使用岗位画像和评分卡。报告必须展示评分维度、权重、推荐阈值、TopN 证据和风险。

本 Skill 不要求 campaign `strategy.json` 或历史 `*rank*.json` 作为前置流程。标准路径必须能仅凭 JD 生成的 `scorecard.json` 和只读 `data/talent.db` 完成匹配、精排、报告和外联表；历史 campaign artifact 只能作为参考或排障材料。

脉脉详情页 URL 必须保留可打开所需的 `trackable_token`，同时清洗 UTM、`show_tip` 和详情抓取用非必要参数，只保留 `dstu` 与 `trackable_token`。发布前必须检查 `reports/quality-gates.json`，包括 TopN 分层、CSV 行数、关键列、外联角度、敏感路径/token 和乱码标记；除 `profile_url` 字段里的脉脉详情页 `trackable_token` 外，其他 token 仍必须拦截。

## 安全边界

- `data/talent.db 默认只读`。
- 不写 `match_scores`，除非用户未来单独明确授权。
- 不发起新的脉脉搜索。
- 不上传 SQLite DB、sync zip、raw search、raw detail、raw capture。

## 飞书发布边界

默认真实发布到飞书知识库 `JD需求交付`。发布前必须先执行 `lark-cli doctor` 和 `lark-cli auth status`，并完成 Wiki 目录 dry-run、Markdown 导入 dry-run、Sheet 创建 dry-run 和 Sheet UTF-8 JSON 写入 dry-run。dry-run 成功后必须直接真实发布，不需要人工二次确认；发布成功并回读通过后继续发送完成通知。

Markdown 发布使用 `drive +import --type docx` 后 `wiki +move`。外联表禁止使用 `drive +import --type sheet` 或 CSV 文件导入；必须使用 `sheets +create` 创建空表，再把 `reports/outreach-queue.csv` 解析成二维数组，用 `sheets +write --values` 写入 UTF-8 JSON，最后 `wiki +move`。当前流程不依赖 `sheets +append --file`。

飞书发布完成且 Wiki/Doc/Sheet 回读通过后，必须用 `im +chat-search --as user` 搜索默认通知群 `JD需求协同`，解析 `chat_id` 后用 `im +messages-send --as user --chat-id <chat_id>` 发送完成通知。显式 `--notify-user-id` 或 `--notify-chat-id` 仍可覆盖默认目标。通知模板必须包含任务执行结果、成果物清单、Wiki目录链接和推荐报告摘要，并把 `feishu/im-notification-message.txt`、`feishu/im-notification-results.json` 落盘。

## 自动交接

解析输入和默认值后，读取并执行 `agents/workflows/jd-talent-delivery/AGENT.md`。不要把真实执行逻辑写在 Skill 中；只要没有触发 workflow 停机条件，就按 canonical workflow 连续推进到完成。

首个运行时检查命令：

```powershell
python -m scripts.jd_talent_delivery prepare --jd-path <jd_path> --output-base data/output --top-n 30
```
