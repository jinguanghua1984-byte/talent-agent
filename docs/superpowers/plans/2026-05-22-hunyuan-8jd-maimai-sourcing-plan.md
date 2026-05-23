# Hunyuan 8JD Maimai Sourcing Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for execution work, or `superpowers:executing-plans` for inline execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 8 个混元 AI DATA 岗位，先用脉脉尽可能扩充高质量相关人才进入本地人才库，再在本地人才库内按每个 JD 做高精度匹配和推荐。

**Architecture:** 不把 8 个 JD 混成一个不可执行的大 campaign。采用“一个 batch 计划 + 8 个 JD campaign root”的结构，共享公司/产品线 registry、关键词簇、去重策略和主库同步边界；搜索阶段偏召回，入库后用每个 JD 的 `strategy.json` 独立精排。

**Tech Stack:** `skills/maimai-talent-search-campaign`、`agents/workflows/maimai-unattended-campaign`、`scripts.maimai_campaign_orchestrator`、`scripts.maimai_campaign_search_plan`、`scripts.maimai_campaign_rank`、Campaign DB、`scripts/talent_sync.py`、本地 `data/talent.db`。

---

## 输入范围

本计划已读取以下 8 个 JD：

| JD | 文件 | 岗位 | 需求数 | 地点 | 置信度 |
| --- | --- | --- | ---: | --- | --- |
| 01 | `docs/business-requirements/01-hunyuan-llm-data-strategy-lead.md` | 混元大模型数据策略负责人 | 10 | 北京/深圳/成都/上海 | 高 |
| 02 | `docs/business-requirements/02-hunyuan-llm-data-product-lead.md` | 混元大模型数据产品专家/leader | 1 | 北京/深圳 | 高 |
| 03 | `docs/business-requirements/03-hunyuan-data-labeling-platform-tech-lead.md` | 混元数据标注平台技术负责人 | 1 | 北京/深圳 | 低，正文待补充 |
| 04 | `docs/business-requirements/04-hunyuan-data-management-platform-tech-lead.md` | 混元数据管理平台技术负责人 | 1 | 北京/深圳 | 低，正文待补充 |
| 05 | `docs/business-requirements/05-hunyuan-llm-post-training-algorithm-expert.md` | 混元大模型后训练算法工程师/专家 | 5 | 北京/深圳 | 高 |
| 06 | `docs/business-requirements/06-hunyuan-data-algorithm-lead-3d.md` | 混元数据算法负责人-3D方向 | 1 | 北京/深圳/上海/杭州 | 高 |
| 07 | `docs/business-requirements/07-hunyuan-data-algorithm-lead-speech.md` | 混元数据算法负责人-语音方向 | 1 | 北京/深圳/上海/杭州 | 高 |
| 08 | `docs/business-requirements/08-hunyuan-multimodal-data-engineer.md` | 混元多模态数据工程师 | 3 | 北京/深圳 | 高 |

03/04 只能按标题、职级和人才画像制定扩库策略，不能在后续精排中当成完整 JD 使用；精排前应补正式职责或通过交付反馈校准画像。

## 核心策略

1. 先扩库，后精排。搜索阶段不按单 JD 过窄过滤，优先覆盖“大模型数据、后训练数据、数据平台、标注质检、数据管理、多模态数据算法、语音/3D 数据、分布式数据工程”这条共同人才带。
2. 每个 JD 一个 campaign root。共享批次预算和去重，但 `requirements.json`、`strategy.json`、`run-policy.json`、`search-implementation-plan.md`、`campaign-manifest.json` 必须按 JD 独立落盘，方便后续逐 JD 精排。
3. 查询采用 query-only。真实请求中 `allcompanies=""`、`positions=""`、地域结构化字段为空，避免严格公司/职位过滤导致高质量人选漏掉；公司和岗位用 query 文本锚定。
4. 列表人选尽量入 Campaign DB，详情人选控制质量。搜索列表 clean dry-run 后可按 policy 写 Campaign DB；详情默认 A/B 档，稀缺方向或 A+B+C 不超过 100 时抓 C 档。
5. 主库写入是人工边界。Campaign DB 到 `data/talent.db` 必须走 bundle export、verify、dry-run、backup、显式 apply，不能由无人值守流程自动写主库。

## Campaign 结构

建议新增 batch 计划目录：

```text
data/campaigns/hunyuan-ai-data-8jd-batch-2026-05-22/
  campaign-manifest.json
  batch-sourcing-plan.md
  jd-index.json
  reports/
  feedback/
```

每个 JD 独立 campaign root：

```text
data/campaigns/hunyuan-01-llm-data-strategy-lead-2026-05-22/
data/campaigns/hunyuan-02-llm-data-product-lead-2026-05-22/
data/campaigns/hunyuan-03-data-labeling-platform-tech-lead-2026-05-22/
data/campaigns/hunyuan-04-data-management-platform-tech-lead-2026-05-22/
data/campaigns/hunyuan-05-llm-post-training-algorithm-2026-05-22/
data/campaigns/hunyuan-06-data-algorithm-3d-2026-05-22/
data/campaigns/hunyuan-07-data-algorithm-speech-2026-05-22/
data/campaigns/hunyuan-08-multimodal-data-engineer-2026-05-22/
```

每个 campaign root 至少包含：

- `requirements.json`：岗位、来源文件、需求数、地点、硬性门槛、缺失字段。
- `strategy.json`：关键词包、公司池、公司/产品线映射、评分规则、交付标题、反馈合同。
- `run-policy.json`：`daily_search_request_budget=500`、`search_wave_max_pages=50`、`detail_pack_max_contacts=100`、`main_db_sync_mode="manual_only"`、`allow_main_db_write=false`。
- `search-implementation-plan.md`：wave、页数预算、恢复入口和验收。
- `campaign-manifest.json`：artifact map、workflow entry check、安全边界。

## 目标公司池

P0 公司/产品线来自 JD 明示目标，首轮必须覆盖：

- 字节：`字节 Seed`、`字节 DMC`、`字节 Global Data`、`字节 AIDP`
- 阿里：`阿里通义`、`阿里千问`、`通义实验室`
- 快手：`快手可灵`、快手数据平台/AI 数据团队
- 美团、小红书
- Kimi、MiniMax
- Surge AI、Scale AI
- Google、Meta
- Vast

P1 扩展池只作为第二轮补量，不抢首轮预算：

- 百度千帆、华为盘古、商汤、智谱、百川、零一万物、月之暗面相关数据/多模态/后训练团队
- 国内大厂数据平台、标注平台、数据治理、AI 平台团队
- 海外数据标注、RLHF、数据质量、模型评测相关团队

腾讯混元是本批 JD 所属业务，不作为首轮外部目标公司；可在 registry 中保留为解析当前业务语义和排除内部背景的辅助项。

## 人才画像簇

### C1 大模型数据策略/交付负责人

覆盖 JD：01，兼容 02/03/04 的上游数据交付负责人。

高质量信号：

- 管过后训练数据、分 Topic 数据策略、数据交付、数据标注、数据质检、数据合成、数据运营团队。
- 能把数据质量和模型评测结果闭环，推动数据配方、短板补齐和生产标准。
- 有产品/技术负责人复合背景，或有大模型数据创业/交付经验。

关键词包：

```text
大模型 数据策略 后训练 数据交付 数据质检 数据标注 数据合成 数据运营 数据质量体系
LLM RLHF SFT 训练数据 评测 数据闭环 Topic 数据 数据生产
```

职位别名：

```text
大模型数据负责人 / AI数据负责人 / 后训练数据负责人 / 数据交付负责人 / 数据质检负责人 / 数据运营负责人 / 标注质检负责人
```

示例 query：

```text
字节 DMC 大模型 后训练 数据策略 数据交付 数据质检
Scale AI RLHF 数据标注 数据质量 数据交付
阿里通义 大模型 数据合成 数据质检 后训练
```

### C2 Data Infra 产品负责人

覆盖 JD：02，兼容 03/04 平台方向。

高质量信号：

- 做过标注平台、标注插件/工具、自动化打标、RL playground、数据管理平台、自动化质检平台。
- 既懂数据生产全流程，又能把平台能力产品化、标准化、复制到多业务。
- 有 AI 平台、Agent 产品、数据平台产品或大模型应用产品经验。

关键词包：

```text
大模型 数据平台 产品 标注平台 自动化打标 数据管理 自动化质检 Agent RL playground
AI平台 数据产品 数据交付 产品化 用户研究 平台能力
```

职位别名：

```text
数据平台产品负责人 / AI平台产品经理 / 大模型数据产品 / 标注平台产品 / 数据管理平台产品 / Agent产品
```

示例 query：

```text
字节 AIDP 大模型 数据平台 产品 自动化质检 标注平台
阿里通义 数据产品 标注平台 数据管理 Agent
美团 AI平台 数据平台产品 数据交付
```

### C3 标注平台/数据管理平台技术负责人

覆盖 JD：03/04，低置信度画像，后续必须用补充 JD 校准。

高质量信号：

- T12 级平台技术负责人、架构师、技术 Lead。
- 做过标注平台、任务分发、审核质检、数据管理、元数据、版本、血缘、数据资产、数据治理。
- 能支撑大模型训练数据生产、管理、质量与可追溯。

关键词包：

```text
标注平台 技术负责人 数据管理平台 数据平台 架构师 元数据 数据治理 血缘 数据资产 质检平台 任务分发
大模型 数据管理 数据版本 数据追溯 数据标准 数据质量
```

职位别名：

```text
数据平台技术负责人 / 标注平台技术负责人 / 数据管理平台负责人 / 数据平台架构师 / 数据治理架构师 / 质检平台负责人
```

示例 query：

```text
字节 AIDP 标注平台 技术负责人 数据质检 任务分发
阿里 数据管理平台 架构师 元数据 血缘 数据治理
快手 数据平台 技术负责人 数据资产 数据质量
```

### C4 Agent 后训练算法/数据专家

覆盖 JD：05。

高质量信号：

- 做过 SFT/RL/RLHF、LLM Alignment、Agent 轨迹数据、工具调用、多轮交互、复杂轨迹生成、评测和数据飞轮。
- 既理解模型训练原理，也能用 Python/PyTorch/TensorFlow 做数据链路和算法落地。
- 顶会、开源贡献、高质量 HuggingFace/GitHub 项目是强加分。

关键词包：

```text
LLM 后训练 SFT RLHF Alignment Agent ReAct Reflexion 工具调用 轨迹数据 数据合成 自动质检 评测 数据飞轮
Transformer PyTorch TensorFlow 多智能体 多轮交互 复杂轨迹
```

职位别名：

```text
后训练算法工程师 / LLM Alignment工程师 / Agent算法工程师 / RLHF算法 / 大模型数据算法 / 评测算法
```

示例 query：

```text
字节 Seed Agent 后训练 RLHF 轨迹数据 工具调用
Kimi Alignment SFT RLHF Agent 评测 数据合成
MiniMax 大模型 后训练 Agent ReAct 数据质检
```

### C5 多模态数据算法负责人：3D 与语音

覆盖 JD：06/07。

3D 高质量信号：

- 3D 生成、多模态理解、3D 数据构建、Caption、embedding、质量评估、去重聚类、数据合成。
- 能建设数据采集、筛选清洗、标注、质量评估 pipeline，并通过数据实验改进模型效果。

语音高质量信号：

- ASR、语音识别、音频数据清洗、语音质量评估、语音数据合成、音频多模态。
- 同样需要数据 pipeline、质量评估、实验分析和模型训练理解。

关键词包：

```text
3D 多模态 数据算法 Caption embedding 去重 聚类 数据筛选 质量评估 数据合成
ASR 语音 音频 多模态 数据算法 语音识别 数据清洗 质量评估
Spark Ray HiveSQL PyTorch TensorFlow 模型训练 数据处理
```

职位别名：

```text
多模态数据算法负责人 / 3D数据算法 / 语音数据算法 / ASR算法负责人 / 数据算法Lead / 多模态算法专家
```

示例 query：

```text
Vast 3D 多模态 数据算法 数据合成 质量评估
字节 Seed 3D Caption embedding 数据筛选
阿里通义 ASR 语音 数据算法 质量评估
Kimi 多模态 数据算法 数据清洗 评测
```

### C6 多模态大数据工程骨干

覆盖 JD：08，兼容 06/07 的数据 pipeline 工程侧。

高质量信号：

- TB/PB 级多模态数据处理、ETL/DAG、批流处理、Spark/Ray/Flink、Python/Linux/Shell。
- 懂 CPU/GPU、IO、并行化、批处理、流水线、数据质量、元数据、版本管理和可追溯。
- 能把抽象模型需求拆成工程方案并跨算法/模型/平台团队落地。

关键词包：

```text
多模态 数据工程 数据管线 ETL DAG Spark Ray Flink TB PB 分布式 GPU 数据质量 元数据 版本管理 数据追溯
Python Linux Shell 批处理 流式处理 性能优化
```

职位别名：

```text
多模态数据工程师 / 大模型数据工程师 / 数据管线工程师 / 分布式数据工程师 / 数据平台工程师 / 数据质量工程师
```

示例 query：

```text
快手可灵 多模态 数据工程 Spark Ray 数据质量
小红书 大模型 数据管线 ETL DAG 分布式
阿里通义 多模态 数据工程 TB PB 数据追溯
```

## 排除规则

搜索阶段不依赖脉脉的排除语法；排除主要在导入后粗筛和精排中执行。

全局排除：

```text
BI / 报表 / 商业分析 / 数据录入 / 标注员 / 审核员 / 众包运营 / 外包项目经理 / 纯前端 / 客户端 / Java CRUD / 测试工程师 / 安全合规 / Prompt运营 / AI绘画运营 / 校招 / 实习 / 初级
```

工程方向例外：

- 08 可保留 `ETL`、`数仓`、`数据平台`，但必须同时命中 `多模态`、`大模型`、`TB/PB`、`Spark/Ray/Flink`、`数据质量`、`元数据/版本/追溯` 中至少一个。
- 03/04 可保留传统数据平台背景，但必须出现平台负责人、架构、治理、资产化、质量或可追溯证据。

算法方向排除：

- 05/06/07 排除纯论文研究、纯模型调参、纯 CV/NLP 训练且无数据构建/质量/评测/数据 pipeline 证据的人。
- 06/07 不把通用推荐/广告算法作为强匹配，除非候选人有多模态、语音、3D 或训练数据质量相关证据。

## 首轮 500 页预算分配

首轮目标是扩库，不是立刻给最终推荐。按需求数、稀缺性和共用程度分配：

| JD | 页数 | 目的 |
| --- | ---: | --- |
| 01 数据策略负责人 | 150 | 需求数最大，且能覆盖数据交付、质检、运营、平台上游人群 |
| 05 后训练算法专家 | 100 | 技术门槛高，需覆盖大模型/Agent/RLHF 稀缺人群 |
| 08 多模态数据工程师 | 60 | 需求数 3，且可为 06/07 补 pipeline 人才 |
| 06 3D 数据算法负责人 | 45 | 稀缺方向，先用公司锚点和 3D/多模态关键词控质量 |
| 07 语音数据算法负责人 | 45 | 稀缺方向，先覆盖 ASR/音频数据算法 |
| 02 数据产品专家/leader | 40 | 需求数小，但可从平台产品扩库 |
| 03 标注平台技术负责人 | 30 | JD 缺正文，先小预算低置信度扩库 |
| 04 数据管理平台技术负责人 | 30 | JD 缺正文，先小预算低置信度扩库 |

首轮执行拆为 3 类 wave：

| Wave | 页数 | 策略 | 验收 |
| --- | ---: | --- | --- |
| W0 smoke | 16-24 | 每个画像簇 2-4 页，验证 query-only 请求、公司锚点和结果质量 | 非登录/验证码/非 JSON；每簇有可读候选样本 |
| W1 P0 直接公司锚点 | 300 | P0 公司/产品线 + 核心关键词，优先字节/阿里/快手/美团/小红书/Kimi/MiniMax/Scale/Surge/Vast | 候选人可按 JD 归入 A/B/C/淘汰 |
| W2 标题和能力补漏 | 176-184 | 去掉部分公司锚点，用职位别名和技术能力扩召回 | 重复率低于 70%，有效画像不明显劣化 |

若 W0 出现单簇结果严重跑偏，停止该簇并调整关键词，不把错误 query 扩大到 W1。

## 执行步骤

### Task 1: 写 batch manifest 和 8 个 campaign 合同

**Files:**

- Create: `data/campaigns/hunyuan-ai-data-8jd-batch-2026-05-22/campaign-manifest.json`
- Create: `data/campaigns/hunyuan-ai-data-8jd-batch-2026-05-22/jd-index.json`
- Create: `data/campaigns/hunyuan-*/requirements.json`
- Create: `data/campaigns/hunyuan-*/strategy.json`
- Create: `data/campaigns/hunyuan-*/run-policy.json`
- Create: `data/campaigns/hunyuan-*/search-implementation-plan.md`
- Create: `data/campaigns/hunyuan-*/campaign-manifest.json`

- [ ] Step 1: 为每个 JD 写 `requirements.json`，03/04 的 `missing_fields` 必须包含 `岗位职责正文`、`任职要求正文`、`技术栈细节`。
- [ ] Step 2: 为每个 JD 写 `strategy.json`，把上面的 C1-C6 画像映射到 `keyword_packages`、`company_pools`、`position_aliases`、`screening_rules`、`delivery_targets.direction_rules`。
- [ ] Step 3: 为每个 JD 写 `run-policy.json`，保持 `allow_main_db_write=false` 和 `main_db_sync_mode="manual_only"`。
- [ ] Step 4: 写 batch `jd-index.json`，包含 `campaign_ids[]`、`priority_order`、`first_round_page_budget`、`cross_jd_dedupe_policy`。

### Task 2: 编译 search plan 并做离线校验

**Commands:**

```powershell
python -m scripts.maimai_campaign_orchestrator status --campaign-root data/campaigns/<campaign_id>
python -m scripts.maimai_campaign_orchestrator plan-waves --campaign-root data/campaigns/<campaign_id> --units data/campaigns/<campaign_id>/search-units.jsonl --out data/campaigns/<campaign_id>/state/search-wave-plan.json
python -m pytest tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py tests/test_maimai_search_filter_clearing.py -q
```

- [ ] Step 1: 逐 JD 编译 `search-plan.json` 和 `search-units.jsonl`。
- [ ] Step 2: 校验全部 unit 的 `search_filters.allcompanies == ""`、`search_filters.positions == ""`、`query_relation == 0`。
- [ ] Step 3: 校验 03/04 在报告中标记低置信度，不进入高优先级外联承诺。
- [ ] Step 4: 校验计划文档和策略文件不出现不属于混元 8JD 的样板字段。

### Task 3: 执行脉脉搜索并写 Campaign DB

执行必须走 canonical workflow；真实平台阶段不自动导航、刷新、点击业务页面。

- [ ] Step 1: 用户确认 search plan 后，按 workflow 自动启动浏览器、加载 `data/session/maimai-cdp-profile` 和 `extensions/maimai-scraper`。
- [ ] Step 2: 人工完成登录、验证码、进入稳定人才银行页和首个搜索模板。
- [ ] Step 3: W0 smoke 通过后执行 W1/W2；每个成功页面写入 `raw/search/unit-*/page-*.json`。
- [ ] Step 4: 每个 wave 标准化后 dry-run，clean 时按 policy 自动 apply 到该 JD 的 Campaign DB。
- [ ] Step 5: 若登录、验证码、安全页、403、429、432、非 JSON、HTML、模板漂移或 partial capture 出现，停止并写 `reports/interruption-*.json` 与 `state/continuation-plan.json`。

### Task 4: 粗筛、详情和 Campaign DB 质量控制

- [ ] Step 1: 每个 JD 独立跑 `maimai_campaign_rank --mode list`，生成 A/B/C/淘汰。
- [ ] Step 2: A/B 必抓详情；C 档仅在 `A+B+C <= 100` 或该 JD 方向明显供给不足时抓详情。
- [ ] Step 3: 详情 health check、dry-run clean 后写 Campaign DB；不把 partial detail 写入下游。
- [ ] Step 4: 每个 JD 输出 `reports/list-rank*.md/json`、`reports/detailed-rank*.md/json` 和候选人 CSV。

推荐命令形态：

```powershell
python -m scripts.maimai_campaign_rank --db data/campaigns/<campaign_id>/talent.db --config data/campaigns/<campaign_id>/strategy.json --out-json data/campaigns/<campaign_id>/reports/list-rank.json --out-md data/campaigns/<campaign_id>/reports/list-rank.md --mode list --limit 500
python -m scripts.maimai_campaign_rank --db data/campaigns/<campaign_id>/talent.db --config data/campaigns/<campaign_id>/strategy.json --out-json data/campaigns/<campaign_id>/reports/detailed-rank.json --out-md data/campaigns/<campaign_id>/reports/detailed-rank.md --mode detailed --limit 300
```

### Task 5: Campaign DB 合并进主库

主库整合只能在用户明确授权后执行。

```powershell
python scripts/talent_sync.py export --db data/campaigns/<campaign_id>/talent.db --out data/campaigns/<campaign_id>/reports/campaign-to-main-sync.zip
python scripts/talent_sync.py verify-bundle --bundle data/campaigns/<campaign_id>/reports/campaign-to-main-sync.zip
python scripts/talent_sync.py import --db data/talent.db --bundle data/campaigns/<campaign_id>/reports/campaign-to-main-sync.zip
python scripts/talent_sync.py import --db data/talent.db --bundle data/campaigns/<campaign_id>/reports/campaign-to-main-sync.zip --apply --confirm "确认同步人才库"
```

- [ ] Step 1: 每个 Campaign DB 单独导出 bundle。
- [ ] Step 2: 先 verify bundle，再对 `data/talent.db` dry-run。
- [ ] Step 3: 备份 `data/talent.db` 后 apply。
- [ ] Step 4: 记录 created/merged/conflicts/skipped 和 `PRAGMA integrity_check`。

### Task 6: 本地人才库逐 JD 高精度匹配

主库扩充后，用每个 JD 的 `strategy.json` 对 `data/talent.db` 独立精排，不复用扩库阶段的粗筛结果作为最终结论。

```powershell
python -m scripts.maimai_campaign_rank --db data/talent.db --config data/campaigns/<campaign_id>/strategy.json --out-json data/output/<campaign_id>-main-db-match.json --out-md data/output/<campaign_id>-main-db-match.md --mode detailed --limit 800
```

逐 JD 输出：

- `强推荐`：目标公司/产品线、岗位职责、核心技术或数据交付证据三者至少两项强匹配。
- `推荐`：岗位方向和技术/平台证据匹配，但缺团队规模、数据闭环或详情证据。
- `观察`：有相邻能力，可进入补充深审。
- `不推荐`：命中排除规则或证据不足。

每个 JD 的精排报告必须包含：

- Top 20 强推荐/推荐候选人。
- 每人匹配路径：公司/产品线、岗位职责、关键词证据、风险项。
- 与其他 JD 的复用关系：例如 01/02/03/04 共用数据平台人才，06/07/08 共用多模态数据 pipeline 人才。
- 需要补抓详情或人工核验的字段。

## 质量门槛

搜索质量门槛：

- W0 中每个画像簇至少出现可解释的相关候选样本，否则该簇不扩大。
- 单个 search unit 的排除命中率超过 50%，降权或停止。
- 单个 search unit 的重复率超过 70%，停止继续翻页。
- 单个 search unit 连续 2 页无新增有效候选，停止该 unit。

入库质量门槛：

- `dry-run` 必须 `errors=0` 且无 pending blockers 才能 apply Campaign DB。
- 详情抓取不得 partial apply。
- 主库同步必须 `verify-bundle` 通过、dry-run 可解释、备份完成、用户显式确认。

精排质量门槛：

- 01/05/06/07/08 必须优先看详细经历证据，不只看标题关键词。
- 02 必须区分产品负责人和纯运营。
- 03/04 必须把正文缺失写入风险，不给过强结论。

## 交付形态

本地交付：

- Batch 总览：`data/campaigns/hunyuan-ai-data-8jd-batch-2026-05-22/reports/batch-summary.md`
- 每个 JD：`reports/list-rank.md`、`reports/detailed-rank.md`、候选人 CSV、outreach queue CSV。
- 主库匹配：`data/output/<campaign_id>-main-db-match.md/json`

飞书交付：

- 一篇中文总览云文档：说明扩库规模、候选人结构、8 个 JD 的推荐数量和风险。
- 一个候选人 Sheet：候选人、公司、岗位、数据层级、可匹配 JD、推荐等级、证据摘要。
- 一个 outreach queue Sheet：按 JD、优先级、外联角度和需核验问题排序。

## 停机和复盘

必须停机：

- 登录页、登录失效、验证码、安全页、403、429、432、非 JSON、HTML 响应、模板漂移、详情 partial capture。

必须复盘：

- 某 JD 首轮 `强推荐+推荐` 少于 5 人。
- 03/04 的高分候选集中跑偏到传统数仓/BI。
- 05 的高分候选集中跑偏到纯算法训练而缺少数据构建/评测闭环。
- 08 的高分候选集中跑偏到传统 ETL 且缺多模态/大模型证据。

复盘输出写入：

```text
data/campaigns/hunyuan-ai-data-8jd-batch-2026-05-22/feedback/delivery-feedback-<date>.json
data/campaigns/hunyuan-ai-data-8jd-batch-2026-05-22/feedback/strategy-adjustment-<date>.json
```

## 验收清单

- [ ] 8 个 JD 均有独立 campaign root 和可恢复 manifest。
- [ ] 首轮 500 页预算有明确分配，且未突破平台阻断边界。
- [ ] 所有 query-only unit 明确清空结构化公司/职位/地域过滤。
- [ ] Campaign DB 入库前后有 dry-run/apply 报告和 import ledger。
- [ ] 主库写入只在用户确认后执行，并保留 backup、dry-run、apply、integrity evidence。
- [ ] `data/talent.db` 中新增/合并人选可被 8 个 JD 独立精排。
- [ ] 每个 JD 都有 Top 候选人、推荐理由、风险项和下一轮补抓建议。

## 当前状态

本计划阶段只完成 JD 阅读和寻访计划制定；未执行真实脉脉搜索，未写 Campaign DB，未写主库 `data/talent.db`。
