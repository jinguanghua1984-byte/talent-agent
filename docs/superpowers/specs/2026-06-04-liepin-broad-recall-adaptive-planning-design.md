# 猎聘宽召回 adaptive 搜索规划设计

## 背景

猎聘寻访当前已经补齐 P0/P1 搜索、搜索结果 Campaign DB dry-run/apply、详情 raw、详情 dry-run/apply、full detail pack 和 Campaign Summary。上一阶段 smoke campaign 已经形成 150 个搜索候选与 124 条详情，说明列表到详情的采集和 campaign-local 入库链路可用。

但当前猎聘搜索仍主要是 `jobId` 或固定 `page_plan` 驱动：先生成少量 `curPage`，再执行 `search-resumes`。这适合接口打通和小样本验证，不适合对标脉脉宽召回工作流。脉脉侧已有 `broad_recall_adaptive_v1`：用公司池、关键词包和探测页生成 search units，再按 wave 执行并根据页质决定是否继续。猎聘侧缺少等价的离线规划层，导致后续想扩大候选池时只能手工改搜索条件或简单翻页。

本设计新增猎聘宽召回 adaptive 搜索规划。第一期只做离线规划和 workflow contract，不触发猎聘请求，不连接 CDP，不写 Campaign DB 或主库。

## 目标

- 为猎聘新增显式策略模式：`strategy_mode=liepin_broad_recall_adaptive_v1`。
- 从 `strategy.json` 编译公司池、关键词包、城市/学历/年限等限制，生成猎聘 search units。
- 把 search units 拆成可恢复的 wave plan 与 live gate sidecar，供后续 live search runner 使用。
- 产出可审计报告，说明本次规划的 unit 数、probe 页数、潜在最大页数、策略覆盖和安全边界。
- 对齐脉脉宽召回的核心合同，但不复制脉脉数据模型中不适合猎聘的字段。
- 保持猎聘现有 jobId P0 固定页流程不变。

## 非目标

- 不在本阶段执行 `search-resumes` 或详情接口。
- 不连接 CDP，不读取 cookie、localStorage、sessionStorage、Chrome profile 或 session store。
- 不绕过登录、验证码、安全页、付费限制、搜索日限或平台风控。
- 不写 `data/campaigns/<campaign_id>/talent.db` 或 `data/talent.db`。
- 不做候选推荐、排名、外联队列或飞书交付。
- 不把 adaptive 模式设为默认流程；只有 `strategy_mode=liepin_broad_recall_adaptive_v1` 才启用。

## 方案选择

采用方案 A：新增猎聘专属 planner，并复用现有 orchestrator。

- 方案 A：新增 `scripts/liepin_broad_recall_adaptive.py`，在 `scripts/liepin_campaign_orchestrator.py` 增加 `plan-adaptive-search` 子命令。优点是与猎聘请求结构贴合，改动集中，可测试；推荐采用。
- 方案 B：抽象出跨平台 broad recall planner。优点是长期复用更强，但现在脉脉和猎聘请求体、分页、候选字段差异明显，过早抽象会增加风险。
- 方案 C：直接改 `run-live-search` 支持多 unit。优点是看似更快进入 live，但没有离线计划和报告，恢复与验收边界不清晰。

## 架构边界

新增模块只负责离线策略编译：

```text
strategy.json
  -> scripts.liepin_broad_recall_adaptive
  -> search-units.jsonl
  -> raw/search-live-runs/wave-plan.json
  -> raw/search-live-runs/search-wave-001-plan.json
  -> reports/broad-recall-plan.json
  -> reports/broad-recall-plan.md
```

`scripts/liepin_campaign_orchestrator.py` 只新增命令入口和 JSON 输出，不在规划命令内调用 `run_live_search()`。后续 live runner 需要另起确认点，并在实施后单独扩展。

## Strategy 合同

`strategy.json` 在 adaptive 模式下必须包含：

```json
{
  "strategy_mode": "liepin_broad_recall_adaptive_v1",
  "strategy_version": "2026-06-04",
  "search_scene": "broad_recall",
  "job_id": 75703601,
  "condition_source": "get-search-condition-by-job",
  "unit_order": "company_first",
  "company_pools": {
    "target": ["腾讯", "阿里云"],
    "adjacent": ["字节跳动"]
  },
  "keyword_packages": [
    {
      "id": "ai-product",
      "priority": "P0",
      "position_terms": ["产品经理", "产品负责人"],
      "keywords": ["大模型", "AI 应用"],
      "long_tail_keywords": ["Agent", "RAG"]
    }
  ],
  "condition_overrides": {
    "wantDqs": "010",
    "eduLevels": ["040"],
    "workYearsLow": "5",
    "workYearsHigh": "15",
    "sortType": "0",
    "resumetype": "0"
  },
  "adaptive_search": {
    "probe_pages": 2,
    "unit_max_pages": 15,
    "search_wave_max_pages": 50,
    "account_day_page_guardrail": 500
  }
}
```

`job_id` 可选；如果存在，planner 记录后续 live search 可以先复用 `raw/condition/job-<job_id>.json` 或执行条件生成。离线 planner 不要求该 raw 文件存在，因为它不能触发平台请求。

`company_pools` 和 `keyword_packages` 必须非空。`unit_order` 支持 `company_first` 和 `keyword_first`，默认 `keyword_first`。`condition_overrides` 只允许进入 `searchParamsInputVo` 已知搜索参数键；未知键必须报错，避免把临时字段混进请求体。

## Search Unit 合同

每个 unit 表示一组猎聘搜索条件。字段示例：

```json
{
  "unit_id": "unit-000001",
  "schema": "liepin_search_unit_v1",
  "strategy_mode": "liepin_broad_recall_adaptive_v1",
  "source_company_terms": ["腾讯"],
  "keyword_package": "ai-product",
  "priority": "P0",
  "query": "腾讯 产品经理 大模型 AI 应用",
  "search_params_overrides": {
    "keyword": "腾讯 产品经理 大模型 AI 应用",
    "wantDqs": "010",
    "eduLevels": ["040"],
    "workYearsLow": "5",
    "workYearsHigh": "15",
    "sortType": "0",
    "resumetype": "0",
    "pageSize": 30
  },
  "page_size": 30,
  "probe_pages": 2,
  "unit_max_pages": 15,
  "planned_pages": [0, 1],
  "adaptive_search": {
    "probe_pages": 2,
    "unit_max_pages": 15,
    "good_ratio_continue": 0.3,
    "good_ratio_observe": 0.1,
    "max_consecutive_low_quality_pages": 2
  }
}
```

`query` 采用宽召回，不把完整 JD must-have 全部压进关键词。首版只用公司词、前 2 个职位词、前 2 个宽关键词生成 keyword；长尾关键词保留在 unit 元数据中，供后续人工或二阶段 planner 使用。

`planned_pages` 只包含 probe 页。后续 live adaptive 执行如果发现页质好，可以在 `unit_max_pages` 内继续翻页；这个能力不在本阶段实现。

## Wave Plan 合同

规划命令将 unit 按 `adaptive_search.search_wave_max_pages` 拆成 waves。首版每个 unit 只计算 `probe_pages` 页数，避免离线阶段预先承诺 page 3-N。

`raw/search-live-runs/wave-plan.json` 包含：

- `schema=liepin_adaptive_search_wave_plan_v1`
- `strategy_mode`
- `campaign_id`
- `unit_count`
- `probe_page_count`
- `max_potential_page_count`
- `wave_count`
- `waves`

每个 wave sidecar 写为 `raw/search-live-runs/search-wave-001-plan.json`，供后续 live runner 使用。sidecar 不包含 cookie、header 值或浏览器状态，只包含 unit、页码、`search_params_overrides` 和执行边界。

## 报告

`reports/broad-recall-plan.json/.md` 是公开可读的离线规划摘要。必须包含：

- unit 数量、probe 页数量、最大潜在页数量。
- 公司池与关键词包覆盖统计。
- 按 wave 的页数分布。
- 本阶段副作用声明：`no_live_request=true`、`no_cdp_connection=true`、`no_database_write=true`。
- 下一阶段建议：先实现 live runner 对 single wave 的受控执行，再接标准化/import/详情。

报告不得包含 `ck_id/sk_id/fk_id`、详情 URL token、`rawPreview`、cookie、localStorage、sessionStorage、secret 或 Authorization 值。

## Workflow 更新

`agents/skills/liepin-talent-search-campaign/SKILL.md` 新增“宽召回 adaptive 规划边界”：

- 用户要求扩候选池、宽召回、多公司多关键词、对标脉脉宽召回时，生成 `strategy_mode=liepin_broad_recall_adaptive_v1`。
- 第一阶段只能运行 `plan-adaptive-search`。
- live 搜索必须另起确认点。

`agents/workflows/liepin-unattended-campaign/AGENT.md` 新增 S3a：

- S3a 编译 adaptive search units 和 wave plan。
- S3a 是离线阶段，不触发平台，不写数据库。
- S4 live 搜索仍维持现有安全停机规则；后续扩展 adaptive live runner 时再修改 S4。

## 验收标准

- 缺 `company_pools`、缺 `keyword_packages`、未知 `condition_overrides` 键或非法页数时，规划命令返回错误且不写部分产物。
- 默认策略能生成 `company_count * keyword_package_count` 个 unit。
- `company_first` 和 `keyword_first` 顺序可测试。
- wave plan 按 `search_wave_max_pages` 拆分，不超过单 wave 页数上限。
- 规划命令不连接 CDP、不触发猎聘请求、不写任何 DB。
- 猎聘现有 `init`、`plan-pages`、`run-live-search`、详情和 Campaign Summary 行为保持不变。
- 架构测试覆盖 skill/workflow 对 adaptive planning 的边界描述。

## 后续阶段

1. 实施本设计的离线 planner、orchestrator 命令、文档和测试。
2. 单独设计 adaptive live runner：读取 wave sidecar，逐 unit/page 执行搜索，按页质决定继续或停止。
3. 将 adaptive 搜索结果接入现有 `standardize -> import-search-dry-run/apply -> detail packs -> detail dry-run/apply -> campaign-summary`。
4. 在 Campaign DB 候选池足够大且详情覆盖达标后，再设计 ranking/delivery 和主库 sync。
