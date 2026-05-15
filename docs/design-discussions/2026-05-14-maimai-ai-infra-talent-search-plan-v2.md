# Maimai AI Infra Cold-Start Talent Search V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在完全不依赖既有人才库数据的前提下，建立一条以脉脉列表抓取为主、列表粗筛评分、人工审核圈定详情补全范围、再生成最终寻访报告的 AI Infra 冷启动寻访流水线。

**Architecture:** 采用 campaign 隔离架构：每一轮寻访都有独立策略、搜索计划、原始 capture、冷启动工作库、初版列表报告、人工审核标注、详情任务包、详情 capture、最终报告。搜索侧优先抓列表并低速分页；详情侧只对人工圈定人选通过 popup 本地任务包执行；所有入库动作先 dry-run，用户确认后 apply。

**Tech Stack:** Python 3、SQLite `TalentDB`、`maimai-scraper` Chrome/Edge MV3 扩展、脉脉 `/api/ent/v3/search/basic` 被校准字段、`scripts/maimai_ai_infra_*`、`scripts/maimai_detail_*`、pytest、Markdown/JSON 报告。

---

## 需求理解

这份 V2 计划不延续当前 `data/talent.db` 的 3119 人历史结果，不把已有 A/B/C 分层、已有详情覆盖或历史候选人作为前提。它描述的是：如果今天从零开始为 AI Infra、大模型训练/推理、训练框架、推理框架、算子、异构计算、智算平台等方向寻访，应该如何用现在已经验证过的自动化能力执行。

核心路径是列表优先，而不是一上来补详情：

1. 先通过搜索列表批量采集候选人列表数据。
2. 只用列表字段做粗筛、评分、排行，生成初版报告。
3. 用户人工审核初版报告，指定哪些人进入详情补全范围。
4. 系统为指定范围创建详情抓取任务包。
5. 用户在人才银行页 popup 启动 safe 详情抓取并导出 capture。
6. 本地 dry-run/apply 补齐详情。
7. 对有完整信息的人做精挑细选，生成最终寻访报告。

## V1 到 V2 的关键变化

| 主题 | V1 初版 | V2 方案 |
| --- | --- | --- |
| 数据前提 | 手动记录 A/B 候选人 | 冷启动 campaign，从空工作库开始 |
| 主采集面 | 手动搜索 + 人工记录 | 自动/半自动列表抓取为主 |
| 搜索字段 | 公司、职位、关键词由人填 | 使用已确认 API 字段：`allcompanies`、`positions`、`degrees`、`worktimes_min/max`、`schools`、`major`、`min_age/max_age` |
| 评分阶段 | 人工判断 A/B/C | 列表粗筛先自动评分，人工只审核候选范围 |
| 详情补全 | 查看详情时人工判断 | 只对人工选中的候选人生成详情任务包 |
| 自动化边界 | 未定义 | 搜索可小步放大；详情必须走 popup 人工可见路径 |
| 报告 | 第一批可沟通名单 | 初版列表报告 + 最终寻访报告两阶段产出 |

## 已验证能力和硬边界

### 已验证能力

- 搜索接口为 `POST /api/ent/v3/search/basic`。
- 搜索请求头不本地合成 cookie、session 或 csrf token；复制最近一次真实搜索模板 requestHeaders，页面上下文 fetch 使用 `credentials=include`。
- 默认可自动生成字段：`search.query`、`search.search_query`、`search.paginationParam.page`、`search.paginationParam.size`、`search.page`、`search.size`。
- 已确认可显式写入的筛选字段：`allcompanies`、`degrees`、`degrees_min`、`degrees_max`、`only_bachelor_degree`、`min_only_bachelor_degree`、`max_only_bachelor_degree`、`positions`、`worktimes`、`worktimes_min`、`worktimes_max`、`min_age`、`max_age`、`schools`、`major`、`query_relation`。
- 字段语义：`query_relation=0` 表示 AND，`query_relation=1` 表示 OR；`major` 是专业名；年龄范围参数是 `min_age/max_age`，不使用 `age_min/age_max`。
- 搜索小样本门禁通过；详情无人自动化不通过；详情可落地路径是本地任务包服务 + 用户在人才银行页 popup 加载/启动 + 导出 + 本地 dry-run/apply。

### 禁止路径

- 不使用 `automation.html` 或 CDP 启动真实详情抓取。
- 不自动刷新、自动导航或自动激活人才银行页来修复状态。
- 不在登录页、验证码、安全页、403、429、非 JSON 后自动重试。
- 不写入 `search.age`，只允许 `min_age/max_age`。
- 年龄搜索只抓 `24-40` 周岁；`24-35` 为主力最佳区间，`35-40` 可抓取但进入第二梯队，超过 `40` 周岁不看。
- 毕业院校是硬门槛：必须命中 `985`、`211`、`QS Top500` 或海外 Top500；专科和非重点院校不进入主池、不进入最终推荐。
- 不把既有 `data/talent.db` 的候选人作为本轮初筛或最终报告来源。

## Campaign 隔离设计

每次冷启动寻访创建独立 campaign，例如：

```text
campaign_id = ai-infra-v2-2026-05-14
campaign_root = data/campaigns/ai-infra-v2-2026-05-14/
```

建议目录：

```text
data/campaigns/ai-infra-v2-2026-05-14/
  strategy.json
  talent.db
  search-plan.json
  search-units.jsonl
  state/
    search-progress.json
    search-events.jsonl
    import-ledger.jsonl
    detail-progress.json
  raw/
    search-template.json
    search/
      unit-000001/
        page-001.json
        page-002.json
        page-003.json
    contacts/
      contacts-wave-001.json
    detail-targets-wave1.json
    detail-capture-wave1.json
  reports/
    import-list-dry-run.md
    import-list-apply.md
    initial-list-report.md
    detail-dry-run-wave1.md
    detail-apply-wave1.md
    final-search-report.md
  review/
    initial-human-review.json
```

执行约束：

- `data/campaigns/` 保存真实候选人、搜索 raw 和详情 capture，属于运行数据；实现时必须加入 `.gitignore`，不得提交到仓库。
- `talent.db` 是 campaign 私有冷启动库，可复用 `TalentDB` schema，但不能复用已有主库数据。
- 同一 campaign 内通过 `source_profiles.platform + platform_id` 去重。
- 原始 capture 必须归档；只保留报告不可复盘。
- 初版报告和最终报告都只读取该 campaign 的 `talent.db` 与 raw 文件。

## 搜索执行方案

### 搜索目标

第一轮冷启动目标按 V1 指标放大 10 倍，不再以“小批验证”作为业务规模目标。执行仍然小步提交，但最终 campaign 要形成足够大的可选池，支撑 200-500 人最终推荐。

| 指标 | 建议目标 |
| --- | --- |
| 原始列表联系人 | 15,000-30,000 |
| 去重联系人 | 8,000-18,000 |
| 列表 A 档 | 800-1,500 |
| 列表 A+B 档 | 2,000-4,000 |
| 人工审核详情候选 | 600-1,200 |
| 详情补全成功候选 | 500-1,000 |
| 最终强推荐/推荐 | 200-500 |

如果列表 A 档不足 800，继续扩搜索；如果列表 A+B 超过 4,000，先停下来审初版报告，不急着补详情。最终推荐人数低于 200 时，必须回看详情补全覆盖和搜索方向缺口；最终推荐人数达到 500 时，停止扩池，转入排序和外联优先级整理。

### 公司池

公司池沿用 V1 的二八原则，但 V2 不要求一次搜完所有公司。

| Tier | 用途 | 公司 |
| --- | --- | --- |
| T1 核心 | 主搜索池，约 45% 批次 | 字节跳动、阿里巴巴、快手、百度 |
| T2 高密度 | 主搜索池，约 35% 批次 | 月之暗面、DeepSeek、MiniMax、智谱、阶跃星辰、生数科技、爱诗科技、硅基流动、一流科技、上海人工智能实验室、华为、腾讯、蚂蚁金服、商汤科技、无问芯穹、Momenta、智元机器人、宇树科技 |
| T3 技术专向 | 补强算子/异构/智算，约 15% 批次 | 地平线、寒武纪、摩尔线程、壁仞科技、面壁智能、百川智能、零一万物、科大讯飞、旷视、依图、第四范式、潞晨科技 |
| T4 补充 | 只有缺口明显时使用，约 5% 批次 | 美团、小米、京东、拼多多、B站、蔚来、小鹏、Shopee、得物、天翼云、联通云、移动云 |

### 搜索字段默认值

| 字段 | 默认策略 | 说明 |
| --- | --- | --- |
| `allcompanies` | 每批 1-3 个公司，逗号 OR | 公司是主筛选条件；单公司优先，集团别名可放 query |
| `positions` | 每批 1 个职位名，必要时 2-3 个强同义词 OR | 保持归因清晰，避免泛岗位污染 |
| `degrees` | `1,2,3` | 本科、硕士、博士；专科不抓取 |
| `only_bachelor_degree` | `0` | 不强行只看统招本科 |
| `worktimes_min/max` | `2/10` | 主力年限；专家池可放宽到 `4/15` |
| `query_relation` | 默认 `1`，精确验证批次可用 `0` | OR 做召回，AND 做小批次质量验证 |
| `schools` | 默认空 | 学校 Top 质量主要本地硬筛；只在学校补强批次填重点院校 OR |
| `major` | 默认空 | 只用于计算机/软件/自动化/电子/数学补强批次 |
| `min_age/max_age` | 默认 `24/40` | `24-35` 最佳，`35-40` 第二梯队，`40+` 不看 |
| 城市相关字段 | 默认空 | 结果过多时再按北京、上海、杭州、深圳补强 |

### 搜索批次类型

#### P1：核心精准批次

用途：快速产出高质量 A/B 候选。

```json
{
  "batch_type": "P1_core_precision",
  "search_filters": {
    "allcompanies": "字节跳动",
    "positions": "大模型训练",
    "degrees": "1,2,3",
    "worktimes_min": "2",
    "worktimes_max": "10",
    "min_age": "24",
    "max_age": "40",
    "query_relation": 1
  },
  "query": "\"Seed\" \"AML\" \"豆包\" \"分布式训练\" \"训练框架\" \"GPU\"",
  "max_pages": 3,
  "page_size": 30
}
```

优先组合：

- T1/T2 公司 + 精准职位：`AI Infra`、`ML Infra`、`LLM Infra`、`大模型训练`、`大模型推理`、`分布式训练`、`训练框架`、`推理框架`、`深度学习框架`、`机器学习系统`。
- query 放产品词、部门词和 3-5 个技术词，使用 OR 召回。

#### P2：技术专向批次

用途：补足底层工程、算子、推理和智算平台人才。

```json
{
  "batch_type": "P2_technical",
  "search_filters": {
    "allcompanies": "华为",
    "positions": "异构计算",
    "degrees": "1,2,3",
    "worktimes_min": "2",
    "worktimes_max": "12",
    "min_age": "24",
    "max_age": "40",
    "query_relation": 1
  },
  "query": "\"昇腾\" \"MindSpore\" \"CANN\" \"算子\" \"推理\" \"加速\"",
  "max_pages": 3,
  "page_size": 30
}
```

职位顺序：`模型部署`、`推理引擎`、`训练平台`、`算子开发`、`CUDA`、`异构计算`、`高性能计算`、`分布式系统`、`智算平台`、`机器学习平台`。

#### P3：泛岗位强技术批次

用途：覆盖标题是算法/后端/平台但经历实际偏 AI Infra 的候选人。

```json
{
  "batch_type": "P3_generic_with_strong_query",
  "search_filters": {
    "allcompanies": "阿里巴巴",
    "positions": "算法工程师",
    "degrees": "1,2,3",
    "worktimes_min": "2",
    "worktimes_max": "10",
    "min_age": "24",
    "max_age": "40",
    "query_relation": 0
  },
  "query": "\"Qwen\" \"推理框架\"",
  "max_pages": 2,
  "page_size": 30
}
```

泛岗位只在 query 使用 AND 且包含强技术词时执行。前 1 页 A/B 密度低于 5% 时停止该批次。

#### P4：补洞批次

用途：初版报告显示某个方向不足时使用，不作为默认主搜索。

补洞类型：

- 学校补洞：`schools=清华大学,北京大学,浙江大学,上海交通大学`，仅用于重点院校补强；本地仍按 985/211/QS Top500/海外 Top500 硬筛。
- 专业补洞：`major=计算机,软件工程,自动化,电子信息,数学`。
- 城市补洞：北京、上海、杭州、深圳。
- 年限补洞：专家池 `worktimes_min=8/worktimes_max=15`；青年高潜池 `worktimes_min=0/worktimes_max=3`。
- 年龄补洞：不扩大到 40 岁以上；如需专家池，也只保留 `35-40` 第二梯队。

### 搜索子单元拆分

V2 允许长时任务执行，但搜索必须拆成明确、可恢复、可审计的子单元。

| 层级 | 名称 | 粒度 | 持久化文件 | 说明 |
| --- | --- | --- | --- | --- |
| Campaign | 一轮冷启动寻访 | 15,000-30,000 原始列表联系人 | `strategy.json`、`search-plan.json` | 业务边界和最终报告边界 |
| Wave | 一次可审查导入波次 | 25-50 个搜索单元，约 2,000-4,500 原始联系人 | `contacts/contacts-wave-NNN.json`、`reports/import-list-wave-NNN-*` | 每个 wave 单独 dry-run/apply |
| Search Unit | 公司 x 职位 x 关键词包 x 筛选组合 | 最多 3 页，最多 90 人 | `raw/search/unit-NNNNNN/` | 最小业务归因单元 |
| Page Task | 单个搜索单元的单页请求 | 1 页，最多 30 人 | `raw/search/unit-NNNNNN/page-PPP.json` | 最小恢复单元 |

搜索计划生成后写出 `search-units.jsonl`，每行一个不可变搜索单元：

```json
{
  "unit_id": "unit-000001",
  "wave_id": "wave-001",
  "tier": "T1",
  "company": "字节跳动",
  "position": "大模型训练",
  "keyword_pack": "training",
  "search_filters": {
    "allcompanies": "字节跳动",
    "positions": "大模型训练",
    "degrees": "1,2,3",
    "worktimes_min": "2",
    "worktimes_max": "10",
    "min_age": "24",
    "max_age": "40",
    "query_relation": 1
  },
  "query": "\"Seed\" \"AML\" \"豆包\" \"分布式训练\" \"训练框架\" \"GPU\"",
  "max_pages": 3,
  "page_size": 30
}
```

建议规模：

- P1 核心精准：120-160 个 unit。
- P2 技术专向：120-180 个 unit。
- P3 泛岗位强技术：80-120 个 unit。
- P4 补洞：按初版报告缺口追加 40-80 个 unit。
- 每个 wave 默认 40 个 unit，约 120 页，理论上最多 3,600 原始联系人；实际按去重和停止规则波动。

### 中断恢复和数据不丢机制

长时执行必须满足：进程退出、机器重启、浏览器断开、平台异常或用户暂停后，能从最后一个已完成 page task 继续，并且已抓取数据不丢。

#### 状态文件

| 文件 | 写入时机 | 用途 |
| --- | --- | --- |
| `state/search-progress.json` | 每页开始、完成、失败时更新 | 当前 unit/page 状态、attempt、stop_reason、最后成功时间 |
| `state/search-events.jsonl` | 每个状态变化 append | 追踪执行历史，便于复盘中断原因 |
| `raw/search/unit-NNNNNN/page-PPP.json` | 每页响应成功后立即写入 | 页级原始数据，恢复时以它为准 |
| `state/import-ledger.jsonl` | 每个 wave dry-run/apply 后 append | 防止同一 wave 重复 apply |
| `reports/funnel-snapshot-wave-NNN.json` | 每个 wave 导入和评分后写入 | 可中途查看进度，不等最终跑完 |

#### 原子写入规则

- 每页响应先写 `page-PPP.json.tmp`。
- 校验 JSON、联系人列表和 batch metadata 后，原子改名为 `page-PPP.json`。
- 只有正式 `page-PPP.json` 存在，才把 page 标记为 `completed`。
- `search-progress.json` 损坏时，使用 `raw/search/**/page-*.json` 和 `search-events.jsonl` 重建进度。
- contacts payload 不作为唯一来源；它必须能从 raw page 文件重新生成。

#### Resume 规则

执行器必须支持：

```bash
python scripts/maimai_ai_infra_search_runner.py --campaign-root data/campaigns/ai-infra-v2-2026-05-14 --resume --max-runtime-minutes 180
```

恢复算法：

1. 读取 `search-units.jsonl`。
2. 扫描 `raw/search/**/page-*.json`，把存在且校验通过的页标为 completed。
3. 读取 `state/search-progress.json` 补充 failed/skipped 状态。
4. 从第一个 `pending` 或可重试 `failed` page task 开始。
5. 已 completed 的 page 永不重复请求。
6. 如果一个 unit 已触发业务停止规则，标记为 `stopped`，继续下一个 unit。
7. 如果触发平台异常，写入事件和进度后停止整个 runner。

#### 长时任务控制参数

Runner 需要支持以下控制参数：

| 参数 | 用途 |
| --- | --- |
| `--resume` | 从 campaign 状态恢复 |
| `--wave wave-001` | 只执行指定 wave |
| `--unit unit-000123` | 只执行指定 unit |
| `--max-units 20` | 本次最多执行多少 unit |
| `--max-pages 120` | 本次最多执行多少 page task |
| `--max-runtime-minutes 180` | 到时间后优雅停止并保存状态 |
| `--pause-after-platform-warning` | 出现 403/429/验证码/登录页时立即停止 |

### 门禁和放大节奏

| Gate | 执行范围 | 写库 | 通过标准 |
| --- | --- | --- | --- |
| S4a | 3 批 x 1 页 | 不写库 | HTTP 200 JSON，无登录/验证码/403/429，raw 可解析 |
| S4b | 1 个 wave，约 40 unit x 最多 3 页 | 先 dry-run，确认后写 campaign 库 | 去重联系人不少于 1,000，dry-run errors=0/pending=0 |
| S4c | 3-5 个 wave，约 120-200 unit | 每 wave 独立 dry-run/apply | 列表 A+B 不少于 1,200，异常批次可解释 |
| S4d | 8-10 个 wave，约 320-400 unit | 每 wave 独立 dry-run/apply | 原始列表联系人达到 15,000-30,000，列表 A+B 达到 2,000-4,000 |
| S4e | 按缺口补洞 | 先 dry-run，确认后写 campaign 库 | 只补初版报告暴露的公司/方向/年限缺口 |

搜索执行需要用户显式授权：

```text
确认执行 AI Infra V2 列表搜索
```

搜索结果写入 campaign 库需要用户显式授权：

```text
确认导入 AI Infra V2 列表结果
```

### 停止规则

单批停止：

- 连续 2 页新增联系人为 0。
- 连续 2 页列表 A/B 密度低于 5%。
- 当前批次已采集 90 人。
- 出现登录页、验证码、安全页、403、429、非 JSON。
- 请求体模板缺少 `sid/sessionid/data_version/highlight_exp` 等应保留字段。

当日停止：

- 连续 3 个批次触发平台异常。
- 30 分钟内 429 超过 2 次。
- 当前 wave dry-run 出现 `errors > 0` 或 `pending > 0`。
- 到达 `--max-runtime-minutes` 指定时长。
- 列表 A 档达到 1,500 且 A+B 达到 4,000。
- 原始列表联系人达到 30,000。

## 列表粗筛和初版报告

### 列表可用字段

粗筛只能使用列表数据和 source profile 中已有字段：

- 姓名/脉脉 ID/profile URL。
- 当前公司、曾任公司、当前职位。
- 列表摘要、技能标签、职位标签。
- 学历文本、学校文本、专业文本。
- 工作年限、城市。
- 命中的搜索批次、公司层级、职位批次、关键词包。

粗筛阶段不得假设候选人的项目细节已经可信完整；项目、教育、工作经历结构化明细必须等详情补齐后再进入最终判断。

### 硬筛条件

列表粗筛先执行硬筛，再进入分数排序：

| 条件 | 规则 |
| --- | --- |
| 毕业院校 | 必须命中 985、211、QS Top500 或海外 Top500；专科和非重点院校不看 |
| 年龄 | `24-35` 周岁为最佳；`35-40` 周岁可进入第二梯队；超过 `40` 周岁淘汰 |
| 学历 | `degrees=1,2,3` 只保证本科及以上；最终仍以学校质量硬筛为准 |
| 证据缺失 | 列表字段无法判断学校质量或年龄时，进入 `hold_for_manual_school_age_check`，不进入 A 档 |

### 列表评分

总分 100：

| 维度 | 分值 | 规则 |
| --- | --- | --- |
| 公司/组织密度 | 25 | T1=25，T2=20，T3=14，T4=6 |
| 职位标题 | 25 | 精准 AI Infra/大模型/训练/推理/框架=25，技术专向=20，泛岗位=8 |
| 列表技术证据 | 25 | 命中训练、推理、分布式、框架、算子、异构、智算、GPU、vLLM、SGLang、DeepSpeed、Triton 等，每类加权 |
| 学校/学历 | 10 | 985/QS Top100/海外 Top100=10，211/QS Top500/海外 Top500=8；非重点和专科直接淘汰 |
| 年龄/年限/层级 | 10 | 24-35 岁且 2-10 年=10；35-40 岁或 10-15 年=6 并标第二梯队；40+ 淘汰 |
| 列表可信度 | 5 | profile URL、平台 ID、公司/职位字段完整、批次来源清晰 |

分层：

| 分层 | 标准 |
| --- | --- |
| 列表 A | 80+，且公司、职位或技术证据都不为空 |
| 列表 B | 65-79，或技术证据强但年龄在 35-40 岁第二梯队 |
| 列表 C | 50-64，只作为备选池 |
| 淘汰 | 排除岗位、目标公司不命中、专科、非重点院校、40+、技术证据为空、低于 50 |

### 初版报告内容

输出：`reports/initial-list-report.md` 和 `reports/initial-list-report.json`。

必须包含：

- campaign 范围、策略版本、执行时间、搜索字段版本。
- 搜索批次清单、每批页数、联系人数量、停止原因。
- raw -> 去重 -> 入库 -> A/B/C/淘汰 funnel。
- A 档 Top 100，B 档 Top 150，按分数和方向分组。
- 每个候选人的列表证据：公司、职位、命中技术词、学历/学校、年限、来源批次、风险点。
- 方向覆盖：训练、推理、框架、算子/异构、智算平台、开源工程栈。
- 公司覆盖：T1/T2/T3 的 A/B 数量。
- 建议详情补全名单：默认 A 全量 + B Top 若干 + 方向补洞名额。
- 明确标注：初版报告只基于列表，不作为最终寻访结论。

## 人工审核和详情范围圈定

人工审核初版报告时，只做三类标注：

| 标注 | 含义 |
| --- | --- |
| `detail_now` | 进入本轮详情任务包 |
| `hold` | 暂存，下一轮视缺口决定 |
| `reject` | 不再进入详情 |

推荐详情范围：

- 列表 A：优先进入详情；当 A 档超过 1,200 人时，先按方向均衡和分数选 P0/P1。
- 列表 B：按分数、公司稀缺性、方向稀缺性选 Top 300-800。
- 列表 C：只允许作为方向补洞，每轮不超过 10 人。
- 总详情目标建议 600-1,200 人；拆成 5-10 个详情 wave。
- 单个详情 wave 建议 80-150 人；每 30 人 safe 批间休息，用户可在 wave 边界暂停。

人工审核输出：`review/initial-human-review.json`。

示例结构：

```json
{
  "campaign_id": "ai-infra-v2-2026-05-14",
  "reviewed_at": "2026-05-14T20:00:00",
  "items": [
    {
      "candidate_id": 123,
      "decision": "detail_now",
      "reason": "T1 公司 + 推理框架标题 + GPU/Token 调度列表证据",
      "priority": "P0"
    }
  ]
}
```

## 详情任务包和补全执行

### 任务包生成

从人工审核文件生成详情任务包：

```bash
python scripts/maimai_detail_targets.py from-ids --ids <candidate_ids> --db data/campaigns/ai-infra-v2-2026-05-14/talent.db --out data/campaigns/ai-infra-v2-2026-05-14/raw/detail-targets-wave1.json
```

通过标准：

- `total_contacts` 等于人工选择人数。
- `missing=0`；若不为 0，缺失项写入报告，不能静默忽略。
- 每个 contact 包含 `id`、`trackable_token`、`name`、`company`、`position`、`detail_url`。
- 每个 wave 写入 `state/detail-progress.json`，记录 `pending/running/exported/dry_run_clean/applied` 状态。

### Popup 执行

详情补全使用已验证路径：

1. 启动本地任务包服务。
2. 用户手动打开并保持人才银行页可见。
3. 用户打开扩展 popup。
4. 在批量详情页点击加载任务包。
5. 用户确认数量后点击开始详情。
6. safe 模式执行，每 30 人批间休息。
7. 完成后用户点击导出 JSON。
8. 本地归档 capture。

服务命令：

```bash
python scripts/maimai_detail_plan_server.py --plan data/campaigns/ai-infra-v2-2026-05-14/raw/detail-targets-wave1.json --port 8765
```

详情 wave 恢复规则：

- `detail-targets-waveN.json` 已生成但未导出 capture：重新启动 plan server，用户继续在 popup 加载同一任务包。
- `detail-capture-waveN.json` 已归档但未 dry-run：直接从 capture 执行 dry-run，不重新抓详情。
- dry-run clean 但未 apply：等待用户确认后 apply，不重新抓详情。
- apply ledger 已记录 waveN：禁止重复 apply，只允许重新生成报告。
- 任一 wave 出现 failed jobs：该 wave 停止，失败项进入下一轮补抓任务包，不影响已 clean 的其他 wave。

### 详情导入门禁

先 dry-run：

```bash
python scripts/maimai_detail_import.py dry-run --capture-file data/campaigns/ai-infra-v2-2026-05-14/raw/detail-capture-wave1.json --db data/campaigns/ai-infra-v2-2026-05-14/talent.db --out data/campaigns/ai-infra-v2-2026-05-14/reports/detail-dry-run-wave1.md
```

通过标准：

- `failed_jobs=0`。
- `unmatched=0`。
- `matched` 等于导出详情条数。
- trace 中没有登录页、验证码、安全页证据。

写入详情需要用户显式授权：

```text
确认写入 AI Infra V2 脉脉详情
```

apply：

```bash
python scripts/maimai_detail_import.py apply --capture-file data/campaigns/ai-infra-v2-2026-05-14/raw/detail-capture-wave1.json --db data/campaigns/ai-infra-v2-2026-05-14/talent.db --out data/campaigns/ai-infra-v2-2026-05-14/reports/detail-apply-wave1.md --json-out data/campaigns/ai-infra-v2-2026-05-14/reports/detail-apply-wave1.json --confirm "确认写入脉脉详情"
```

## 详情后精筛

详情后评分不再沿用列表粗筛权重。最终评分必须读完整详情中的工作经历、项目经历、教育经历和 raw detail payload。

总分 100：

| 维度 | 分值 | 规则 |
| --- | --- | --- |
| AI Infra 方向证据 | 30 | 训练/推理/框架/算子/异构/智算/调度/加速在项目或工作经历中有明确职责 |
| 项目复杂度和规模 | 20 | GPU 集群、大模型训练、推理服务、框架研发、吞吐/延迟优化、跨团队平台化 |
| 角色深度 | 15 | 主导/核心研发/架构/owner 高于参与/使用/业务调用 |
| 公司与团队密度 | 15 | T1/T2 高密度团队加分，低密度公司需要更强项目证据 |
| 院校和专业 | 8 | 必须 985/211/QS Top500/海外 Top500；计算机/软件/自动化/电子/数学等专业加分 |
| 年龄、年限和层级 | 7 | 24-35 岁最佳；35-40 岁可推荐但默认第二梯队；40+ 淘汰 |
| 沟通优先级 | 5 | 当前职位稳定性、方向稀缺性、可切入话术 |

最终标签：

| 标签 | 标准 |
| --- | --- |
| 强推荐 | 85+，且详情中有明确 AI Infra 项目和角色深度 |
| 推荐 | 75-84，证据充分但有一项风险 |
| 观察 | 65-74，可作为补充或二轮确认 |
| 不推荐 | 低于 65，或详情证据推翻列表判断 |

硬淘汰：

- 详情显示训练师、运营、招聘、销售、数据标注、审核。
- 只有业务算法、广告/推荐策略，没有训练、推理、框架、系统、算子、智算等底层证据。
- 毕业院校不是 985、211、QS Top500 或海外 Top500。
- 学历为专科。
- 年龄超过 40 周岁。
- 公司命中只是短暂外包、实习或弱相关供应商经历。

## 最终寻访报告

输出：`reports/final-search-report.md` 和 `reports/final-search-report.json`。

报告结构：

1. 执行摘要：本轮冷启动覆盖范围、搜索规模、详情补全规模、最终推荐人数。
2. 方法说明：列表优先、人工审核、详情补全、人机门禁和安全边界。
3. Funnel：raw、去重、列表 A/B/C、人工 detail_now、详情成功、强推荐/推荐/观察/不推荐。
4. 强推荐候选人卡片：姓名/平台 ID、公司、职位、方向、关键证据、风险、建议话术。
5. 推荐候选人卡片：按训练、推理、框架、算子/异构、智算平台分组。
6. 公司覆盖和方向覆盖。
7. 被详情推翻的典型误判：用于下一轮优化列表评分。
8. 未覆盖缺口：公司、方向、城市、年龄段、年限或重点院校来源。
9. 下一轮搜索建议：只围绕缺口，不重复抓已覆盖方向。

候选人卡片模板：

```text
候选人：<name> / <platform_id>
当前：<company> / <title>
方向：训练框架 / 推理引擎 / 算子异构 / 智算平台
推荐级别：强推荐
关键证据：
- <工作经历或项目经历中的硬证据>
- <技术关键词与职责>
风险：
- <年限、稳定性、方向偏差或证据缺口>
建议切入：
- <面向外联或深审的话术角度>
```

## 已实现 CLI 映射

当前工程实现已把 V2 冷启动 campaign 流程拆成以下本地入口。除 dry-run 和离线报告外，真实脉脉列表搜索、列表导入 apply 和详情导入 apply 仍必须经过对应人工授权门禁。

| 流程 | 命令入口 | 说明 |
| --- | --- | --- |
| 生成搜索计划和 Search Units | `python scripts/maimai_ai_infra_search_plan.py --config configs/maimai-ai-infra-v2-cold-start-strategy.json --out <campaign_root>/search-plan.json --out-units <campaign_root>/search-units.jsonl` | 读取 V2 策略，输出传统 plan 和可恢复的 `search-units.jsonl`。 |
| 离线校验搜索请求体 | `python scripts/maimai_ai_infra_search_runner.py --dry-run-template-only --campaign-root <campaign_root> --units <campaign_root>/search-units.jsonl --resume --max-runtime-minutes 180` | 在 campaign raw 目录写入 page task dry-run 结果；按已落盘 raw 恢复，不触发真实搜索。 |
| 按 wave 生成联系人 payload 并导入 campaign 库 | `python scripts/maimai_ai_infra_pipeline.py run-campaign --campaign-root <campaign_root> --config configs/maimai-ai-infra-v2-cold-start-strategy.json --wave wave-001 --db <campaign_root>/talent.db` | 从页级 raw 重建 wave contacts，先走 dry-run；`--apply` 仍受 ledger 和授权约束保护。 |
| 从人工审核生成详情任务包 | `python scripts/maimai_detail_targets.py from-review --review <campaign_root>/review/initial-human-review.json --db <campaign_root>/talent.db --out <campaign_root>/raw/detail-targets-wave1.json` | 只接受 `detail_now/hold/reject`，重复、非法或不存在的 candidate id 会报错。 |
| 详情 wave dry-run | `python scripts/maimai_ai_infra_pipeline.py detail-wave dry-run --campaign-root <campaign_root> --wave wave-001 --capture-file <capture.json> --db <campaign_root>/talent.db` | 复用详情导入 dry-run，只有 `failed_jobs=0` 且 `unmatched=0` 才记录 `dry_run_clean`。 |
| 详情 wave apply | `python scripts/maimai_ai_infra_pipeline.py detail-wave apply --campaign-root <campaign_root> --wave wave-001 --capture-file <capture.json> --db <campaign_root>/talent.db --confirm "确认写入脉脉详情"` | 检查 `import-ledger.jsonl` 防重复写入；未确认或已 apply 的 wave 会被阻止。 |

## 工程落地任务

### Task 1: Campaign 目录和冷启动 DB

**Files:**
- Modify: `.gitignore`
- Create: `data/campaigns/<campaign_id>/strategy.json`
- Create: `data/campaigns/<campaign_id>/talent.db`
- Modify: `scripts/maimai_ai_infra_pipeline.py`
- Test: `tests/test_maimai_ai_infra_pipeline.py`

- [ ] 将 `data/campaigns/` 加入 `.gitignore`，避免真实候选人和详情 capture 被提交。
- [ ] 增加 `--campaign-root` 参数，所有输出写入 campaign 目录。
- [ ] 确保传入新的 `talent.db` 路径时自动创建 schema。
- [ ] 测试：同一候选人在 campaign 库内去重，但不读取主库候选人。

### Task 2: V2 搜索策略配置

**Files:**
- Create: `configs/maimai-ai-infra-v2-cold-start-strategy.json`
- Modify: `scripts/maimai_ai_infra_search_plan.py`
- Test: `tests/test_maimai_ai_infra_strategy.py`

- [ ] 增加 P1/P2/P3/P4 批次类型、公司配额、职位配额和补洞规则。
- [ ] 每个 batch 生成显式 `search_filters`，只使用已确认白名单字段。
- [ ] 测试：不得生成 `age`、未确认字段或超过 3 页的默认批次。

### Task 3: 列表搜索执行和导入

**Files:**
- Modify: `scripts/maimai_ai_infra_search_runner.py`
- Modify: `scripts/maimai_ai_infra_pipeline.py`
- Test: `tests/test_maimai_ai_infra_runner.py`

- [ ] 增加 S4a/S4b/S4c/S4d/S4e gate 参数。
- [ ] 读取 `search-units.jsonl`，按 Search Unit 和 Page Task 执行。
- [ ] 每页响应以 `.tmp -> .json` 原子写入 campaign `raw/search/unit-NNNNNN/page-PPP.json`。
- [ ] 每页更新 `state/search-progress.json` 并 append `state/search-events.jsonl`。
- [ ] 支持 `--resume`、`--wave`、`--unit`、`--max-units`、`--max-pages`、`--max-runtime-minutes`。
- [ ] 导入前强制 dry-run，dry-run clean 后等待用户确认再 apply。
- [ ] 测试：进程中断后 resume 跳过已完成 page，只继续 pending page。
- [ ] 测试：平台异常时停止当前 gate，不重试、不写库。

### Task 4: 列表粗筛和初版报告

**Files:**
- Modify: `scripts/maimai_ai_infra_rank.py`
- Modify: `scripts/maimai_ai_infra_pipeline.py`
- Test: `tests/test_maimai_ai_infra_strategy.py`

- [ ] 增加 `--mode list`，只用列表字段评分。
- [ ] 输出 `initial-list-report.md/json`。
- [ ] 报告包含 funnel、A/B/C、方向覆盖、公司覆盖和建议详情名单。
- [ ] 测试：没有详情数据时仍可生成初版报告。

### Task 5: 人工审核输入

**Files:**
- Create: `scripts/maimai_ai_infra_review.py`
- Test: `tests/test_maimai_ai_infra_pipeline.py`

- [ ] 读取 `initial-human-review.json`。
- [ ] 只允许 `detail_now/hold/reject` 三类决策。
- [ ] 生成去重后的 candidate_id 列表。
- [ ] 测试：未知 candidate_id、重复 candidate_id、非法 decision 都报错。

### Task 6: 详情任务包和详情导入

**Files:**
- Modify: `scripts/maimai_detail_targets.py`
- Modify: `scripts/maimai_ai_infra_pipeline.py`
- Test: `tests/test_maimai_detail_targets.py`

- [ ] 从人工审核结果生成 wave 详情任务包。
- [ ] 本地 plan server 只服务当前 wave。
- [ ] 维护 `state/detail-progress.json` 和 `state/import-ledger.jsonl`，防止重复抓取和重复 apply。
- [ ] 详情 capture dry-run clean 后等待用户确认再 apply。
- [ ] 测试：`missing > 0` 会进入报告并阻止自动 apply。
- [ ] 测试：capture 已存在时可跳过抓取，直接恢复 dry-run/apply。

### Task 7: 详情后精筛和最终报告

**Files:**
- Modify: `scripts/maimai_ai_infra_rank.py`
- Modify: `scripts/maimai_ai_infra_pipeline.py`
- Test: `tests/test_maimai_ai_infra_pipeline.py`

- [ ] 增加 `--mode detailed`，使用工作/项目/教育详情评分。
- [ ] 输出 `final-search-report.md/json`。
- [ ] 报告包含强推荐、推荐、观察、不推荐，以及下一轮搜索建议。
- [ ] 测试：详情推翻列表判断时，候选人能从推荐池降级并记录原因。

## 验收命令

```bash
python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_detail_targets.py -q
python -m pytest tests/test_maimai_search_api_spec.py tests/test_maimai_detail_import.py tests/test_maimai_detail_plan_server.py -q
python -m py_compile scripts/maimai_ai_infra_search_plan.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_detail_targets.py scripts/maimai_detail_plan_server.py scripts/maimai_detail_import.py
git diff --check
```

上线前再跑：

```bash
python -m pytest tests scripts -q
```

## 执行顺序建议

1. 先实现 campaign 隔离和 V2 策略编译，不触发真实脉脉搜索。
2. 生成 `search-units.jsonl`，用 dry-run-template-only 验证所有 unit 的请求体 patch。
3. 用户授权后跑 S4a 小样本列表搜索。
4. S4a 通过后按 wave 跑 S4b/S4c/S4d；每个 wave 独立 raw 归档、contacts 生成、dry-run、确认 apply、funnel snapshot。
5. 长时运行中可用 `--max-runtime-minutes` 主动切片；中断后用 `--resume` 继续。
6. 达到 15,000-30,000 原始列表联系人或 2,000-4,000 列表 A+B 后生成初版列表报告并人工审核。
7. 生成 5-10 个详情 wave 任务包，按 popup 本地任务包路径补详情。
8. 每个详情 wave dry-run/apply 后刷新最终评分，详情补全 500-1,000 人或最终推荐 200-500 人后生成最终寻访报告。
9. 用最终报告中的误判和缺口反向修正下一轮搜索策略。

## 自检

- 覆盖了用户要求的冷启动前提、列表抓取、列表粗筛评分、初版报告、人工审核、详情任务包、详情补全、最终精选报告。
- 明确区分了搜索可自动化和详情必须 popup human-in-the-loop 的边界。
- 使用的搜索字段均来自 2026-05-14 已确认白名单，年龄范围使用 `min_age/max_age`。
- 没有把当前主库候选人、当前 A/B/C 统计或已有详情覆盖作为 V2 执行前提。
- 搜索目标已按 10 倍规模设计，最终推荐目标为 200-500 人。
- 长时任务已拆为 campaign、wave、search unit、page task，并设计了页级 raw、进度文件、事件日志、import ledger 和 resume 机制。
- 新增筛选条件已落入搜索、列表粗筛和详情精筛：毕业院校必须 985/211/QS Top500/海外 Top500；年龄默认抓 24-40，24-35 最佳、35-40 第二梯队、40+ 淘汰。
