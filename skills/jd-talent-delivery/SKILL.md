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

## 岗位画像 contract

岗位画像必须复用 `hr-talent` 的岗位分析框架，结构参考 `docs/business-requirements/2026-05-21-llm-inference-role-deep-dive.md`。画像至少覆盖结论摘要、岗位真实问题、能力模型、候选人类型、寻访关键点、公司池、关键词、排除项和风险项。

## 评分一致性

粗筛和精排必须引用同一个 `scorecard.json`。粗筛只做召回、硬过滤、风险预标记和粗分；精排不得重新解释 JD，只能使用岗位画像和评分卡。报告必须展示评分维度、权重、推荐阈值、TopN 证据和风险。

## 安全边界

- `data/talent.db 默认只读`。
- 不写 `match_scores`，除非用户未来单独明确授权。
- 不发起新的脉脉搜索。
- 不上传 SQLite DB、sync zip、raw search、raw detail、raw capture。

## 飞书发布边界

默认真实发布到飞书知识库 `JD需求交付`。发布前必须先执行 `lark-cli doctor` 和 `lark-cli auth status`，并完成 Wiki 目录 dry-run、Markdown 导入 dry-run、CSV 导入 dry-run。Markdown 发布使用 `drive +import --type docx` 后 `wiki +move`；CSV 发布使用 `drive +import --type sheet` 后 `wiki +move`。当前流程不依赖 `sheets +append --file`。

## 自动交接

确认输入和默认值后，读取并执行 `agents/workflows/jd-talent-delivery/AGENT.md`。不要把真实执行逻辑写在 Skill 中。

首个运行时检查命令：

```powershell
python -m scripts.jd_talent_delivery prepare --jd-path <jd_path> --output-base data/output --top-n 30
```
