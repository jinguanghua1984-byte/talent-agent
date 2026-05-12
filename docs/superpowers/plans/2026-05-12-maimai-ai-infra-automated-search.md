# Maimai AI Infra Automated Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `docs/design-discussions/2026-05-12-maimai-ai-infra-talent-search-plan.md` 中的手动脉脉搜索策略自动化执行，人工只参与策略确认和最终结果审查。

**Architecture:** 采用“策略配置 -> 搜索批次编译 -> 登录态浏览器内低速执行 -> 导入 dry-run/apply -> 本地规则评分 -> Top 候选详情补全 -> 最终审查报告”的流水线。网页访问只使用真实 Chrome 登录态和现有 `maimai-scraper`/CDP 能力，不绕过验证码、权限和风控；遇到 403、429、验证码、非 JSON 响应时熔断并进入最终异常报告。

**Tech Stack:** Python 3、SQLite `data/talent.db`、Playwright CDP、Chrome MV3 extension `extensions/maimai-scraper`、现有 `TalentDB`、`talent_library import/detail`、`maimai_detail_import.py`、pytest、node syntax check。

---

## 结论

技术上可落地，但不是直接拿现有脚本串起来就够。现有仓库已经具备 70% 能力：脉脉扩展可捕获列表和批量详情，`talent_library import` 可导入并去重，`talent_library detail` 可生成定向详情目标，`TalentDB` 可搜索、合并、详情补全，测试覆盖了关键契约。

缺口是 30%：需要新增一个 AI Infra 搜索 orchestrator，把公司梯队、职位名、关键词包、停止规则和评分规则编译成机器可执行批次，并用登录态 Chrome 自动跑搜索。

**2026-05-12 评审修订：上一版把 Python CDP runner 写得过于靠前。修订后，Python CDP 直接 `page.evaluate(fetch)` 不作为默认主路径，只能作为受控 POC；默认主路径改为“扩展/页面上下文内的请求模板重放或 UI 驱动 + 被动捕获”。** 原因是项目已有文档明确记录：脉脉详情补全“不使用 CDP”，Boss 渠道已有 `page.evaluate(fetch)` 触发强制登出的先例；因此任何直接 fetch 型 runner 必须先通过小样本反爬验证。

人工参与点固定为两个：

1. 策略确认：确认公司池、关键词、每日上限、dry-run 通过后是否自动 apply。
2. 最终审查：查看 A/B 档候选人、异常批次、失败原因和下一轮策略建议。

中途异常不让人工接手操作。自动化遇到平台权限、验证码、风控、字段结构异常时，只熔断、记录、跳过或终止当日批次，最终统一审查。

## 必须先完成的可行性门禁

实施前新增 Phase 0，不通过不进入主实现。

| 门禁 | 验证目标 | 通过标准 | 失败 Plan B |
| --- | --- | --- | --- |
| 搜索执行方式 | 验证是否能自动搜索且不触发登出/验证码 | 连续 3 个小批次、每批 1 页，登录态保持，返回 JSON，联系人可导入 | 放弃直接 fetch；改用 UI 填写/点击搜索 + 被动捕获；若 UI 自动化也不稳，则只做已有导出数据自动化和最终报告 |
| 扩展自动化桥 | 验证能否不点 popup 完成清空、导入目标、启动详情、查看状态、导出 | 能通过扩展内部消息或 automation page 执行 `clearAll -> importDetailContacts -> startDetailBatch -> getDetailBatchStatus -> exportFullJson` | 新增 `automation.html`/内部 bridge；未通过前不承诺详情无人执行 |
| 下载/导出 | 验证导出无需人工保存文件 | `exportFullJson` 支持 `saveAs:false` 或 `getFullExportData`，Python 能读到文件或 JSON | 修改扩展导出接口；当前 `saveAs:true` 不满足无人执行 |
| 搜索字段语义 | 验证 `company/title/degree/worktime/query_relation` 的真实传参 | 每个要自动设置的筛选字段都有真实请求 diff 证据 | 未验证字段不写入平台请求，只放到关键词和本地过滤 |
| 会话健康检查 | 验证能识别登录失效/风控 | 每批后能判断当前页是否仍登录；异常立即熔断 | 不自动重登，不自动重试；输出异常报告 |

Phase 0 的输出文件：

```text
data/output/maimai-ai-infra-feasibility-YYYY-MM-DD.md
data/output/raw/maimai-ai-infra-field-calibration-YYYY-MM-DD.json
```

未通过 Phase 0 时，最终交付只能称为“半自动数据处理方案”，不能称为“人工仅策略确认和最终审查”的端到端方案。

## 已验证的核心可行性

| 验证项 | 命令/依据 | 结果 |
| --- | --- | --- |
| 扩展、导入、详情目标、详情导入契约测试 | `python -m pytest tests/test_talent_library_cli.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py tests/test_maimai_scraper_extension.py -q` | 37 passed |
| 历史脉脉导出 dry-run 可导入 | `python scripts\talent_library.py import --input-dir C:\Users\Administrator\Downloads --pattern "maimai-capture-2026-05-12*.json" --db data\talent.db --out data\output\talent-import-2026-05-12-ai-infra-auto-feasibility-dry-run.md` | 11 个文件，原始 2519，去重 1795，新建 0，合并 1795，待确认 0，失败 0 |
| 推荐 Top10 可转详情目标 | `python scripts\talent_library.py detail --top10-file data\output\talent-match-2026-05-10-alibaba-cloud-ai-agent-pm-top10.json --db data\talent.db --out data\output\maimai-detail-targets-2026-05-12-ai-infra-auto-feasibility.json` | 联系人 10，缺失 0 |
| 详情写库历史结果可验证 | `data/output/talent-detail-2026-05-11-maimai-batch-result.json` | matched 33，written 33，verified 33 |
| 扩展 JS 语法 | `node --check extensions\maimai-scraper\idb.js; node --check ...` | 通过 |
| 搜索请求字段可自动化 | 从 `C:\Users\Administrator\Downloads\maimai-capture-2026-05-12.json` 解析 `/api/ent/v3/search/basic` 请求体 | 已确认存在 `search.query`、`positions`、`allcompanies`、`degrees`、`worktimes`、`age`、`query_relation`、`paginationParam`；但只验证字段存在，未验证精确语义 |
| 本地规则检索可跑 | 直接查询 `data/talent.db` | 当前库 2733 人，脉脉来源 2733，目标公司命中 1610，硬排除命中 309，宽口径策略交集 1306 |

注意：当前本地没有保留可重新 dry-run 的原始详情 capture 文件，只有写库结果文件；因此详情导入重新验证依赖现有单测和历史 `33 written/verified` 结果。后续自动化必须把扩展原始详情导出也归档到 `data/output/raw/`，不能只保留写库结果。

### 字段语义已知程度

基于 11 个历史搜索请求，目前只能得出以下结论：

| 字段 | 已观察值 | 当前判断 |
| --- | --- | --- |
| `search.query` / `search.search_query` | `"训练" "推理" "算法"` 等 9 种 | 高置信：顶部关键词 |
| `query_relation` | `0` 共 10 次，`1` 共 1 次 | 低置信：可能对应“任意/所有”，必须校准后使用 |
| `allcompanies` | `一线互联网公司` 或空 | 中置信：公司范围或公司集合，不等同于单个就职公司 |
| `degrees` | 空或 `2,3` | 中置信：学历筛选，但代码含义需校准 |
| `positions` | 历史样本均为空 | 未验证：不能直接填职位名称 |
| `worktimes` | 历史样本均为空 | 未验证：不能直接填工作年限 |
| `age` | 历史样本均为空 | 未验证，且不建议硬筛年龄 |
| `paginationParam.page` / `search.page` | `page=1` / `page=0` | 高置信：分页字段，二者可能一个 1-based、一个 0-based |

因此第一版搜索字段策略改为：

1. 已验证字段：只自动 patch `query/search_query`、分页和 page size。
2. 半验证字段：`degrees/allcompanies/query_relation` 先进入校准，不默认使用。
3. 未验证字段：`positions/worktimes/age/schools/major` 不进入自动请求。
4. 公司和职位要求先通过关键词组合扩大召回，再由本地规则过滤；只有字段校准成功后才写入平台筛选。

## 工具盘点

### 当前可用系统工具

| 工具 | 用法 |
| --- | --- |
| PowerShell shell | 运行 pytest、node check、Python CLI、文件检索、SQLite 验证 |
| `apply_patch` | 写入方案、后续代码改动 |
| `update_plan` | 跟踪任务阶段 |
| gstack `/browse` 技能 | 后续需要真实网页 QA 时使用；本轮未浏览网页 |
| Web 工具 | 不需要联网；本任务基于本地仓库和本地历史数据 |

### 项目内已存在工具

| 工具/文件 | 当前能力 | 自动化中复用方式 |
| --- | --- | --- |
| `extensions/maimai-scraper` | 捕获搜索请求、联系人、批量详情、导出 JSON、熔断/日志/重置 | 继续作为浏览器采集和详情补全执行器 |
| `extensions/maimai-scraper/autopager.js` | 基于真实请求模板低速翻页 | 搜索 runner 的分页策略参考 |
| `extensions/maimai-scraper/detail_batch.js` | safe/test 批量详情、批间休息、429 处理、任务日志 | Top 候选详情补全复用 |
| `scripts/talent_library.py import` | 脉脉导出 dry-run/apply 入库 | 搜索结果入库标准入口 |
| `scripts/talent_library.py detail` | candidate/top10 -> 详情目标 JSON | Top A/B 候选详情补全入口 |
| `scripts/maimai_detail_import.py` | 扩展详情导出 dry-run/apply | 详情写库标准入口 |
| `scripts/talent_db.py` | SQLite 人才库、去重、检索、详情、评分记录 | 本地候选人筛选、评分、报告数据源 |
| `scripts/platform_match/search.py` | CDP 登录态搜索框架、限流、熔断 | 新搜索 runner 可复用 CDP 和限流思想，但需换成 `/api/ent/v3/search/basic` 字段 |
| `scripts/platform_match/adapters/maimai.py` | 脉脉字段映射 | 导入、评分前标准化复用 |
| `tests/test_maimai_scraper_extension.py` | 扩展契约测试 | 修改扩展后必须跑 |
| `tests/test_talent_library_cli.py` | import/detail CLI 测试 | 修改导入和详情目标生成后必须跑 |
| `tests/test_maimai_detail_import.py` | 详情导入测试 | 修改详情补全链路后必须跑 |

### 已沉淀实践经验

1. 批量写库必须先 dry-run；dry-run 统计为 `pending=0/errors=0` 时，才允许在已授权策略内自动 apply。
2. 详情补全必须走真实 Chrome 登录态和低速顺序执行，不做主动绕过验证码。
3. 扩展重载后页面 content script 会失效，必须刷新业务页面。
4. `maimai-scraper` 导出必须使用完整导出，包含 `contacts`、`details`、`detailJobs`、`requests`。
5. 批量详情 reset 必须清理 IndexedDB 和 storage 中的旧 jobs/details，避免旧批次污染。
6. `source_profiles.platform + platform_id` 是最可靠去重键，不能靠姓名模糊合并。
7. 只保留写库结果不够，原始 capture 必须归档，否则后续不能复盘请求和详情 payload。
8. 现有 `score_candidates.py` 没有标准 CLI help，执行 `--help` 会直接跑默认评分并写文件；自动化方案不能把它作为稳定入口。

## 自动化数据流

```text
策略确认
  -> configs/maimai-ai-infra-search-strategy.json
  -> 生成搜索批次 data/output/maimai-ai-infra-search-plan-YYYY-MM-DD.json
  -> 登录态 Chrome 内自动执行 /api/ent/v3/search/basic
  -> 原始搜索结果 data/output/raw/maimai-ai-infra-search-run-YYYY-MM-DD.json
  -> talent_library import dry-run
  -> dry-run 通过则自动 apply
  -> 本地 AI Infra 规则评分
  -> A/B 档候选人 data/output/maimai-ai-infra-shortlist-YYYY-MM-DD.json/md
  -> talent_library detail 生成详情目标
  -> maimai-scraper safe 模式批量详情
  -> maimai_detail_import dry-run/apply
  -> 最终审查报告 data/output/maimai-ai-infra-final-review-YYYY-MM-DD.md
```

## 搜索策略如何机器化

### 批次生成规则

搜索批次由四个维度组成：

1. `company_group`：公司梯队和别名。
2. `title`：职位名称，一次只放一个。
3. `keyword_pack`：产品词或技术词。
4. `search_body_patch`：写入脉脉请求体的字段。

脉脉请求体字段已经从真实导出中验证：

```json
{
  "search": {
    "query": "\"训练\" \"推理\" \"算法\"",
    "positions": "",
    "allcompanies": "一线互联网公司",
    "degrees": "2,3",
    "worktimes": "",
    "age": "",
    "query_relation": 0,
    "paginationParam": {
      "page": 1,
      "size": 30
    },
    "page": 0,
    "size": 30
  }
}
```

第一版不要假设 `degrees=2,3` 的平台含义完全稳定。搜索时学历字段先不做硬限制，入库后用本地规则淘汰大专并优先 C9/985/211。

### 批次优先级

1. 第一梯队公司 + 第一批职位名 + K1/K2/K3。
2. 第二梯队高密度公司 + 第一批职位名 + 公司产品词/K2/K3。
3. 第一、二梯队 + 第二批技术专向职位。
4. 泛岗位只在产品词或技术词强命中时跑。
5. 第三梯队只跑技术专向职位。
6. 第四、五梯队默认不自动跑，除非策略确认时打开补充池。

### 自动停止规则

每个搜索批次最多 3 页。

以下情况停止当前批次：

- 连续 2 页新增联系人为 0。
- 连续 2 页 A/B 档候选人为 0。
- 当前批次已采集 90 人。
- 返回 403、429、验证码、HTML 页面或非 JSON。
- `total` 明显异常，例如 0 但页面模板显示存在结果。

以下情况停止当天任务：

- 连续 3 个批次触发权限或验证码异常。
- 30 分钟内 429 超过 2 次。
- 导入 dry-run 出现 `errors > 0` 或 `pending > 0`，且无法自动隔离异常记录。
- 请求体结构和已知模板不兼容。

## 候选人评分规则

本地评分不依赖 LLM，先用可解释规则做 A/B/C 分层；LLM 只能作为后续增强，不作为第一版必须项。

总分 100：

| 维度 | 分值 | 规则 |
| --- | --- | --- |
| 公司 | 30 | 第一梯队 30，第二梯队 24，第三梯队 16，第四梯队 8，第五梯队 4 |
| 职位名称 | 25 | 精准 AI Infra/大模型/训练/推理/框架 25，技术专向 20，泛岗位 10，排除岗位直接淘汰 |
| 技术证据 | 25 | 命中训练、推理、分布式、框架、算子、异构、智算、加速、vLLM、SGLang 等，按命中数量和字段来源加权 |
| 学历 | 10 | C9 10，985 8，211 6，本科 4，大专淘汰 |
| 年限/职级 | 10 | 2-10 年 10，0-2 年但强校/强项目 7，10-15 年 7，15 年以上 3 |

分层：

```text
A 档：80 分及以上，且公司、职位/技术证据均通过
B 档：65-79 分，或技术证据强但标题/学校略弱
C 档：50-64 分，只入备选池
淘汰：目标公司不命中、排除岗位、大专且无强证据、技术证据为空
```

## 第一版需要新增/修改的文件

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `configs/maimai-ai-infra-search-strategy.json` | 新增 | 公司梯队、别名、产品词、职位名、关键词包、排除词、配额、授权策略 |
| `scripts/maimai_ai_infra_search_plan.py` | 新增 | 读取策略配置，生成可执行搜索批次 |
| `scripts/maimai_ai_infra_search_runner.py` | 新增 | 连接登录态 Chrome，按批次低速执行 `/api/ent/v3/search/basic`，写原始结果 |
| `scripts/maimai_ai_infra_rank.py` | 新增 | 从 `TalentDB` 读取候选人，执行 A/B/C 分层并输出 shortlist |
| `scripts/maimai_ai_infra_pipeline.py` | 新增 | 串联 plan -> run -> import dry-run/apply -> rank -> detail targets -> reports |
| `extensions/maimai-scraper/inject.js` | 可选修改 | 如果选择扩展内执行搜索，需要支持通用 `search` body patch，不只替换 query/page |
| `extensions/maimai-scraper/background.js` | 可选修改 | 如果选择扩展内执行搜索，需要保存批次执行状态和批次日志 |
| `tests/test_maimai_ai_infra_strategy.py` | 新增 | 策略编译、停止规则、评分规则测试 |
| `tests/test_maimai_ai_infra_runner.py` | 新增 | 用真实 capture body fixture 验证请求体 patch 和分页 |
| `tests/test_maimai_ai_infra_pipeline.py` | 新增 | 用临时 DB 验证 dry-run/apply/rank/report 主链路 |

建议第一版优先走 Phase 0 POC：先验证扩展/页面上下文模板重放和 UI 驱动 + 被动捕获；Python CDP 直接 fetch 只作为低优先级受控实验，不作为默认实现。这样可以先把反爬风险隔离在最小样本内。

## 实施任务

### Task 1: 策略配置文件

**Files:**
- Create: `configs/maimai-ai-infra-search-strategy.json`
- Test: `tests/test_maimai_ai_infra_strategy.py`

- [ ] **Step 1: 写策略配置 fixture 测试**

创建测试，断言配置必须包含公司梯队、职位批次、关键词包、排除词和配额。

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_strategy.py -q
```

Expected: FAIL，因为配置和加载器尚不存在。

- [ ] **Step 2: 新增配置文件**

配置必须包含：

```json
{
  "human_gates": {
    "strategy_confirmed": false,
    "auto_apply_after_clean_dry_run": false
  },
  "limits": {
    "pages_per_batch": 3,
    "page_size": 30,
    "max_contacts_per_batch": 90,
    "max_batches_per_day": 80,
    "min_delay_seconds": 8,
    "max_delay_seconds": 20
  },
  "company_tiers": {
    "tier1": ["字节跳动", "阿里巴巴", "快手", "百度"],
    "tier2_priority": ["月之暗面", "DeepSeek", "MiniMax", "智谱", "阶跃星辰", "生数科技", "爱诗科技", "硅基流动", "一流科技", "上海人工智能实验室", "华为", "腾讯", "蚂蚁金服", "商汤科技", "无问芯穹", "Momenta", "智元机器人", "宇树科技"]
  },
  "company_aliases": {
    "字节跳动": ["字节", "火山引擎", "Seed", "AML", "豆包", "扣子", "Coze"],
    "阿里巴巴": ["阿里", "阿里云", "达摩院", "PAI", "通义", "Qwen", "夸克"],
    "百度": ["Paddle", "飞桨", "ERNIE", "文心", "Apollo", "千帆"],
    "腾讯": ["混元", "腾讯云", "TEG", "AI Lab"],
    "华为": ["昇腾", "MindSpore", "CANN", "盘古", "ModelArts"]
  },
  "title_batches": {
    "precision": ["AI Infra", "ML Infra", "LLM Infra", "大模型训练", "大模型推理", "分布式训练", "训练框架", "推理框架", "深度学习框架", "机器学习系统", "训推平台", "AI 基础设施"],
    "technical": ["模型部署", "推理引擎", "训练平台", "算子开发", "CUDA", "异构计算", "高性能计算", "分布式系统", "智算平台", "机器学习平台"],
    "generic": ["算法工程师", "机器学习工程师", "深度学习工程师", "平台开发工程师", "系统研发工程师", "后端开发工程师"]
  },
  "keyword_packs": {
    "framework": ["AI Infra", "机器学习", "深度学习", "训练框架", "推理框架"],
    "training": ["大模型", "分布式训练", "RL", "SFT", "微调", "训推"],
    "inference": ["推理", "Token调度", "算子", "异构", "CUDA", "加速"],
    "cluster": ["智算", "GPU", "集群", "调度", "训练平台", "推理平台"],
    "opensource": ["vLLM", "SGLang", "Megatron", "DeepSpeed", "TensorRT", "Triton"]
  },
  "exclude_titles": ["训练师", "运营", "HR", "人事", "招聘", "销售", "数据标注", "审核"],
  "exclude_education": ["大专"]
}
```

- [ ] **Step 3: 配置加载器测试通过**

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_strategy.py -q
```

Expected: PASS。

### Task 2: 搜索批次编译器

**Files:**
- Create: `scripts/maimai_ai_infra_search_plan.py`
- Test: `tests/test_maimai_ai_infra_strategy.py`

- [ ] **Step 1: 测试 80/20 批次生成**

断言：

- 第一梯队优先于第二梯队。
- 泛岗位必须带技术关键词包。
- 每个 batch 只有一个职位名。
- 每个 batch 有 `company`、`position`、`query`、`priority`、`max_pages`。

- [ ] **Step 2: 实现批次生成**

输出结构：

```json
{
  "generated_at": "2026-05-12T00:00:00",
  "strategy_version": "ai-infra-v1",
  "batches": [
    {
      "batch_id": "tier1-bytedance-precision-001",
      "tier": "tier1",
      "company": "字节跳动",
      "position": "大模型训练",
      "query": "\"Seed\" \"AML\" \"豆包\" \"训练框架\" \"分布式训练\"",
      "query_relation": 0,
      "max_pages": 3,
      "page_size": 30,
      "priority": 100
    }
  ]
}
```

- [ ] **Step 3: CLI 输出计划文件**

Run:

```bash
python scripts/maimai_ai_infra_search_plan.py --config configs/maimai-ai-infra-search-strategy.json --out data/output/maimai-ai-infra-search-plan-smoke.json
```

Expected: 生成 JSON，批次数不超过 `max_batches_per_day`。

### Task 3: 搜索执行器可行性 POC

**Files:**
- Create: `scripts/maimai_ai_infra_search_runner.py`
- Test: `tests/test_maimai_ai_infra_runner.py`

- [ ] **Step 1: 用历史请求体写 body patch 测试**

fixture 使用历史 capture 中的 `/api/ent/v3/search/basic` 请求体，断言 patch 后：

- `search.query` 更新为 batch query。
- `search.positions` 更新为 batch position。
- `search.allcompanies` 更新为 batch company。
- `search.paginationParam.page` 和 `search.page` 按脉脉格式同步更新。
- 原有 `sid/sessionid/data_version/highlight_exp` 保留。

- [ ] **Step 2: 实现 dry-run-template-only**

只做请求体 patch，不访问脉脉网络。该步骤用于验证字段不会误删 `sid/sessionid/data_version/highlight_exp`。

- [ ] **Step 3: 实现搜索执行 POC**

POC 必须同时实现两条候选路径，并记录哪条通过：

路径 A：扩展/页面上下文模板重放。

- 复用 `inject.js` 已捕获的真实搜索模板。
- 通过 content script 发 `__MAIMAI_SEARCH_CMD__`。
- 只 patch `query/search_query/page/pagesize`。
- 连续 3 个小批次不登出、不验证码、不 403/429 才通过。

路径 B：UI 驱动 + 被动捕获。

- 自动在真实页面填写顶部关键词并点击搜索。
- 只监听真实页面发出的搜索响应，不主动 `fetch`。
- 若字段控件 selector 不稳定，则只保留顶部关键词自动化。

Python CDP 直接 `page.evaluate(fetch)` 只能作为路径 C 低优先级 POC：

- 单批 1 页。
- 执行后立即做登录态检查。
- 任何登出、验证码、403/429、非 JSON 均判定失败，并永久降级到路径 A/B。

输出结构：

```json
{
  "run_id": "maimai-ai-infra-2026-05-12",
  "status": "completed",
  "batches": [
    {
      "batch_id": "tier1-bytedance-precision-001",
      "status": "completed",
      "pages_fetched": 3,
      "contacts": 77,
      "ab_stop_reason": "max_pages"
    }
  ],
  "contacts": []
}
```

- [ ] **Step 3: runner smoke**

Run:

```bash
python scripts/maimai_ai_infra_search_runner.py --plan data/output/maimai-ai-infra-search-plan-smoke.json --out data/output/raw/maimai-ai-infra-search-run-smoke.json --dry-run-template-only
```

Expected: 不访问网络，只输出 patched body 样例，用于确认字段。

### Task 4: 搜索结果入库流水线

**Files:**
- Create: `scripts/maimai_ai_infra_pipeline.py`
- Test: `tests/test_maimai_ai_infra_pipeline.py`

- [ ] **Step 1: 测试 run result -> import payload**

输入 runner JSON，输出标准 `contacts` JSON，确保可被 `talent_library import` 解析。

- [ ] **Step 2: 串联 import dry-run**

调用：

```bash
python scripts/talent_library.py import --input data/output/raw/maimai-ai-infra-search-run-smoke.contacts.json --db data/talent.db --out data/output/talent-import-ai-infra-smoke.md
```

Expected: 生成 dry-run 报告，不写真实库。

- [ ] **Step 3: 自动 apply 策略**

只有策略确认时设置：

```json
"auto_apply_after_clean_dry_run": true
```

且 dry-run 满足：

```text
errors = 0
pending = 0
pre_errors = 0
```

才自动执行：

```bash
python scripts/talent_library.py import --input <contacts.json> --db data/talent.db --out <report.md> --apply --confirm "确认导入人才"
```

否则停止写库，把异常写入最终审查报告。

### Task 5: AI Infra 本地评分和 Shortlist

**Files:**
- Create: `scripts/maimai_ai_infra_rank.py`
- Test: `tests/test_maimai_ai_infra_strategy.py`

- [ ] **Step 1: 写评分 fixture**

构造 6 类候选人：

- 第一梯队 + 精准岗位 + 多技术词 -> A。
- 第二梯队 + 技术专向岗位 -> A/B。
- 泛岗位 + 技术词强 -> B。
- 运营/HR/训练师 -> 淘汰。
- 大专 -> 淘汰。
- 目标公司不命中 -> 淘汰。

- [ ] **Step 2: 实现评分**

评分必须返回：

```json
{
  "candidate_id": 123,
  "tier": "tier1",
  "grade": "A",
  "score": 86,
  "evidence": {
    "company": "字节跳动",
    "title": "大模型训练框架工程师",
    "tech_keywords": ["分布式训练", "训练框架", "GPU"],
    "education": "硕士"
  },
  "risk_flags": []
}
```

- [ ] **Step 3: 输出 Markdown 和 JSON**

Run:

```bash
python scripts/maimai_ai_infra_rank.py --db data/talent.db --config configs/maimai-ai-infra-search-strategy.json --out-json data/output/maimai-ai-infra-shortlist-smoke.json --out-md data/output/maimai-ai-infra-shortlist-smoke.md
```

Expected: Markdown 按 A/B/C 分组，包含证据和风险点。

### Task 6: 扩展自动化桥与 Top 候选详情补全

**Files:**
- Modify: `scripts/maimai_ai_infra_pipeline.py`
- Optional Modify: `extensions/maimai-scraper/background.js`
- Optional Create: `extensions/maimai-scraper/automation.html`
- Optional Create: `extensions/maimai-scraper/automation.js`
- Test: `tests/test_maimai_ai_infra_pipeline.py`

- [ ] **Step 1: 从 shortlist 生成详情目标**

对 A 档和前 30 个 B 档生成 ids：

```bash
python scripts/talent_library.py detail --ids <candidate_ids> --db data/talent.db --out data/output/maimai-ai-infra-detail-targets-smoke.json
```

Expected: `missing=0` 或 missing 明细进入最终报告。

- [ ] **Step 2: 先验证扩展是否能无人控制**

现有扩展后台已经有可复用消息：

```text
clearAll
importDetailContacts
startDetailBatch
pauseDetailBatch
resumeDetailBatch
stopDetailBatch
getDetailBatchStatus
exportFullJson
```

但这些消息目前主要由 popup UI 触发；本地 Python 还没有稳定通道直接调用。必须先验证以下任一方案：

1. CDP 打开 `chrome-extension://<extension-id>/popup.html` 或 `automation.html`，在扩展上下文执行 `chrome.runtime.sendMessage`。
2. 新增扩展内 `automation.html`/`automation.js`，专门暴露自动化入口，避免依赖 popup DOM。
3. 新增 `getFullExportData` 或让 `exportFullJson` 支持 `saveAs:false`，避免人工保存文件。

未验证通过前，不把详情补全列为无人执行闭环。

- [ ] **Step 3: 扩展批量详情执行**

第一版可以保留扩展作为详情执行器，但不要求人工导入文件：

可选实现路径：

1. Python CDP 打开扩展 automation page，调用内部消息导入目标 JSON 并启动。
2. 或给扩展增加 automation bridge，允许本地 runner 发送 `importDetailContacts/startDetailBatch/exportFullJson` 指令。

推荐路径是 2，因为稳定性更高。实现前继续保持人工不介入原则：如果 automation bridge 不可用，当日只输出详情目标文件，不中途要求人工操作。

- [ ] **Step 3: 详情导入**

扩展导出原始 capture 后自动执行：

```bash
python scripts/maimai_detail_import.py dry-run --capture-file <raw-detail-capture.json> --db data/talent.db --out data/output/talent-detail-ai-infra-dry-run.md
```

若 `matched > 0`、`unmatched=0` 且无失败或失败低于策略阈值，再执行：

```bash
python scripts/maimai_detail_import.py apply --capture-file <raw-detail-capture.json> --db data/talent.db --out data/output/talent-detail-ai-infra-result.md --json-out data/output/talent-detail-ai-infra-result.json --confirm "确认写入脉脉详情"
```

### Task 7: 最终审查报告

**Files:**
- Modify: `scripts/maimai_ai_infra_pipeline.py`
- Test: `tests/test_maimai_ai_infra_pipeline.py`

- [ ] **Step 1: 报告内容测试**

最终 Markdown 必须包含：

- 策略版本和确认时间。
- 执行批次数、成功批次、熔断批次。
- 搜索总联系人、去重联系人、入库 created/merged/pending/errors。
- A/B/C/淘汰数量。
- A 档候选表。
- B 档候选表。
- 详情补全结果。
- 异常批次和原因。
- 下一轮建议。

- [ ] **Step 2: 输出最终报告**

Run:

```bash
python scripts/maimai_ai_infra_pipeline.py run --config configs/maimai-ai-infra-search-strategy.json --db data/talent.db --out-dir data/output
```

Expected:

```text
data/output/maimai-ai-infra-final-review-YYYY-MM-DD.md
data/output/maimai-ai-infra-shortlist-YYYY-MM-DD.json
data/output/raw/maimai-ai-infra-search-run-YYYY-MM-DD.json
data/output/raw/maimai-ai-infra-detail-capture-YYYY-MM-DD.json
```

## 验收命令

实现完成后必须运行：

```bash
python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py -q
python -m pytest tests/test_talent_library_cli.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py tests/test_maimai_scraper_extension.py -q
node --check extensions/maimai-scraper/idb.js
node --check extensions/maimai-scraper/detail_batch.js
node --check extensions/maimai-scraper/background.js
node --check extensions/maimai-scraper/content.js
node --check extensions/maimai-scraper/inject.js
node --check extensions/maimai-scraper/popup.js
python -m py_compile scripts/maimai_ai_infra_search_plan.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py
git diff --check
```

最终上线前再跑：

```bash
python -m pytest tests scripts -q
```

## 运行前置条件

1. 真实 Chrome 已登录脉脉。
2. Chrome 使用远程调试端口启动，或 runner 能连接到已打开的 CDP。
3. `extensions/maimai-scraper` 已加载并刷新过脉脉业务页面。
4. 策略配置中的 `strategy_confirmed=true`。
5. 若允许自动写库，`auto_apply_after_clean_dry_run=true` 必须由策略确认阶段显式设置。

## 风险和约束

1. 不承诺绕过验证码、权限、风控和平台限制。
2. 脉脉请求字段可能变化，runner 必须先做模板校验；字段不兼容时停止。
3. `query_relation` 的 0/1 语义需要在策略确认阶段用真实请求模板校准。
4. 学历学校质量需要从 raw profile/详情中抽取，第一版只能先按已有字段和标签评分。
5. 现有库里有大量非 AI Infra 候选人，因此第一版必须使用本地评分，不能只依赖搜索命中。
6. 详情补全需要保留原始 capture；只保留结果文件不可复盘。

## 推荐落地顺序

1. 先做 Phase 0 可行性门禁：搜索执行方式、扩展自动化桥、字段语义校准、导出无人工保存。
2. 再做 `strategy.json + search_plan.py + rank.py`，不碰浏览器，验证规则质量。
3. 做 `search_runner.py` 的 dry-run-template-only，确认请求体 patch。
4. 小批量真实跑 3 个 batch，导入 dry-run，不 apply。
5. 策略确认授权后，打开 clean dry-run 自动 apply。
6. 最后接入详情 automation bridge。

这个顺序可以把平台风险、数据污染风险和实现风险拆开，不需要在第一天就改扩展详情执行器。
