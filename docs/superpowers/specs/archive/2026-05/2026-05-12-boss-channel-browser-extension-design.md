# Boss 渠道浏览器插件扩展设计

日期：2026-05-12

状态：待用户评审

## 背景

当前仓库已经具备两类相关能力。

脉脉侧已经形成完整闭环：浏览器插件在真实 Chrome 登录态中捕获列表和详情接口，支持自动分页、批量详情、运行日志、完整 JSON 导出，并由本地 `maimai_detail_import.py` 做 dry-run、确认写入和写后验证。

Boss 侧已有 Python adapter 和文档基础：`BossAdapter` 能在已打开的 Boss 页面中模拟关键词输入，并被动拦截 `geeks.json` 搜索结果；`map_to_schema()` 已能把 `geekCard` 映射到统一候选人字段。但 Boss 详情端点尚不可用，现有资料明确 `page.evaluate(fetch)`、新开页面、导航详情页都可能触发风控或强制登出。

因此，Boss 渠道第一版采用“列表闭环 + 详情被动捕获实验区”的边界：稳定交付搜索结果采集、导出和入库；详情只在用户自然操作触发请求时被动记录，不主动请求、不自动访问详情页。

## 目标

1. 让 Boss 渠道具备与脉脉列表抓取一致的业务闭环：捕获、查看状态、导出、dry-run、确认入库、写后验证。
2. 保证底层数据一致性：统一导出 envelope、统一候选人字段、统一来源记录、统一入库安全门。
3. 保留渠道机制差异：脉脉可主动重放接口，Boss 只做被动监听和低风险页面辅助。
4. 将现有单渠道插件演进为多渠道插件，避免为 Boss 复制一套完全独立的 UI、存储和导出逻辑。
5. 为 Boss 详情能力预留被动捕获实验区，但不把详情批量抓取作为第一版验收条件。

## 非目标

1. 第一版不实现 Boss 批量详情主动抓取。
2. 第一版不使用 `fetch` 主动请求 Boss 搜索或详情接口。
3. 第一版不自动打开 Boss 详情页、不新开 tab、不通过导航探测登录态。
4. 第一版不做跨渠道自动强合并；跨渠道疑似同人仍进入现有保守合并或待合并流程。
5. 第一版不重写 `TalentDB` 的核心合并策略，只在导入层补齐 Boss capture 的转换和安全检查。

## 方案选择

推荐方案：将现有 `maimai-scraper` 渠道化，演进为多渠道浏览器插件。

不推荐新建完全独立的 `boss-scraper`。独立插件隔离性好，但会复制导出、状态、日志、IndexedDB、run token、重置、报告和入库适配，后续新增渠道时维护成本会继续上升。

也不推荐只做 Python/CDP。现有 Boss adapter 能完成部分搜索，但 Boss 的可靠路径依赖真实页面上下文和被动请求监听。浏览器插件更适合用户手动筛选、自然搜索、自然点击详情时的捕获场景。

## 插件架构

第一版建议新建 `extensions/talent-channel-scraper`，从 `extensions/maimai-scraper` 迁移公共能力；旧目录可在过渡期保留，避免破坏当前可用插件。

目标结构：

```text
extensions/talent-channel-scraper/
  manifest.json
  popup.html
  popup.css
  popup.js
  background.js
  content.js
  idb.js
  channels/
    common/
      capture_envelope.js
      storage.js
      export.js
    maimai/
      inject.js
      parser.js
      pager.js
      detail_batch.js
    boss/
      inject.js
      parser.js
      search_capture.js
      passive_detail_capture.js
```

公共层职责：

- 识别当前 tab 所属渠道。
- 展示统一状态：请求数、候选人数、详情数、运行日志、导出状态。
- 管理统一 IndexedDB 和 `chrome.storage.local` 兼容字段。
- 导出统一 capture JSON。
- 提供 reset、export、summary、log、run token 等跨渠道能力。

渠道层职责：

- 定义 URL 匹配规则。
- 识别本渠道 API。
- 从原始响应提取列表、详情和分页元信息。
- 将原始记录归一到统一 capture item。
- 定义本渠道允许的页面动作。

脉脉渠道保留现有能力：

- 被动捕获列表请求。
- 基于捕获模板主动分页。
- 批量详情接口重放。
- 详情 job、限流、熔断、run token 和完整导出。

Boss 渠道第一版能力：

- 被动捕获 `geeks.json`。
- 从 `zpData.geeks[].geekCard` 提取候选人。
- 按 `encryptGeekId` 去重。
- 可选安全页面辅助：定位 `/web/frame/search/` iframe、清空职位筛选、输入关键词、点击搜索、低速滚动加载有限页数。
- 被动详情实验区：用户手动点击候选人或打开侧边详情时，如果页面自然产生详情相关请求，则保存到 `details[]` 和 `requests[]`。

## 统一数据契约

所有渠道导出同一个 capture envelope。

```json
{
  "exportTime": "2026-05-12T00:00:00.000Z",
  "metadata": {
    "schema_version": 1,
    "channel": "boss",
    "export_type": "full",
    "capture_level": "list",
    "run_token": 1,
    "total_contacts": 0,
    "total_details": 0,
    "total_requests": 0
  },
  "contacts": [],
  "details": [],
  "detailJobs": [],
  "requests": [],
  "logs": []
}
```

`contacts[]` 使用统一字段：

```json
{
  "channel": "boss",
  "platform_id": "encryptGeekId",
  "profile_url": "https://www.zhipin.com/web/geek/encryptGeekId",
  "name": "候选人",
  "city": "北京",
  "current_company": "公司",
  "current_title": "职位",
  "education": "本科",
  "work_years": 5,
  "expected_salary": "30-50K",
  "skill_tags": [],
  "data_level": "partial",
  "raw_profile": {}
}
```

Boss 原始字段保留策略：

- `raw_profile` 保存完整 `geekCard`。
- `raw_profile._capture` 保存请求 URL、页码、关键词、捕获时间、响应摘要。
- `securityId` 不提升为候选人身份主键，只作为 Boss 请求上下文字段保留在 `raw_profile`。

`details[]` 对 Boss 仅表示被动捕获到的详情相关响应：

```json
{
  "channel": "boss",
  "platform_id": "encryptGeekId",
  "mode": "passive_detail_capture",
  "url": "自然请求 URL",
  "ts": "2026-05-12T00:00:00.000Z",
  "endpoint_type": "unknown_detail",
  "data": {},
  "raw_entry": {}
}
```

Boss 第一版 `detailJobs[]` 保持为空或仅记录手动详情捕获观察任务，不复用脉脉批量详情 job 语义，避免用户误以为 Boss 已支持批量详情。

## 入库链路

新增统一导入脚本，优先命名为 `scripts/channel_capture_import.py`。它替代继续新增单渠道导入脚本，但内部仍按 channel 路由到对应 adapter。

流程：

1. 读取 capture JSON。
2. 校验 `metadata.schema_version`、`metadata.channel`、`contacts[]`。
3. 根据 channel 选择 adapter：
   - `maimai` 使用 `MaimaiAdapter.map_to_schema()`。
   - `boss` 使用 `BossAdapter.map_to_schema()` 或等价的 capture item 映射。
4. dry-run 写报告，不修改数据库。
5. apply 必须带明确确认文本，例如 `确认写入boss列表`。
6. 写入 `TalentDB.ingest(mapped, platform=channel)`。
7. 写入后抽样或逐条验证：
   - `source_profiles.platform = channel`
   - `source_profiles.platform_id` 存在
   - `source_profiles.raw_profile` 保留原始响应
   - Boss 列表导入后的 `data_level = partial`

Boss 详情被动捕获的入库策略：

- 如果 `details[]` 只包含未结构化或无法稳定映射的响应，只保留在报告中，不写入 `candidate_details`。
- 如果后续确认某个 Boss 详情响应结构稳定，再新增显式映射规则和测试，允许将该响应升级写入 `candidate_details`。
- 任意详情升级都必须先 dry-run 展示旧值和新值数量，再确认写入。

## 数据一致性规则

来源一致性：

- `source_profiles.platform` 是渠道边界，取值为 `maimai` 或 `boss`。
- `source_profiles.platform_id` 只在同一平台内唯一。
- 脉脉 `platform_id` 是 `uid`。
- Boss `platform_id` 是 `encryptGeekId`。

候选人一致性：

- 同平台同 `platform_id` 必须合并到同一候选人。
- 跨渠道不使用平台 ID 互认。
- 跨渠道只使用姓名、公司、职位、城市、学历等现有身份字段做保守匹配。
- 公司别名命中时进入 pending merge，避免 Boss 与脉脉字段粒度不同导致误合并。

字段覆盖规则：

- 保持现有 `TalentDB` fill-only 语义，列表级数据不覆盖已有更完整字段。
- `skill_tags` 可合并去重。
- `data_level` 只允许升级，不允许从 `detailed` 降级到 `partial`。
- Boss 列表数据不能覆盖脉脉详情数据中的结构化经历，除非后续通过详情映射 dry-run 明确确认。

业务一致性：

- 脉脉和 Boss 都提供“捕获、导出、dry-run、确认写入、报告”的同一业务路径。
- 两个渠道在 UI 上都显示候选人数、详情数、请求数和日志。
- 两个渠道导出的 JSON 都可被本地导入脚本识别。
- 对用户的能力描述必须明确区分 `partial` 和 `detailed`，避免把 Boss 列表卡片误称为完整详情。

## Boss 渠道机制设计

Boss 搜索捕获：

- content script 只在 `*://*.zhipin.com/*` 激活。
- MAIN world 拦截 `fetch` 和 XHR 的响应读取结果，但不主动发起请求。
- 识别 URL 中包含 `geeks.json` 且不属于埋点域的响应。
- 解析 `zpData.geeks[].geekCard`。
- 用 `encryptGeekId` 去重。
- 保存请求 URL、关键词、页码、捕获时间和响应摘要。

Boss 安全搜索辅助：

- 要求用户先打开 Boss `/web/chat/search` 并登录。
- 插件检查是否存在 `/web/frame/search/` iframe。
- 每次搜索前尝试将职位筛选恢复为“不限职位”。
- 只操作 `.search-input`，不用 `.input-text`。
- 清空输入使用 `Control+a` 和 `Backspace`，再模拟输入关键词并点击 `.icon-search`。
- 滚动加载默认最多 3 页，页间等待 5 到 10 秒。
- 城市、学历、经验、薪资等筛选由用户手动设置，插件第一版不自动操作。

Boss 被动详情实验区：

- 监听 Boss 页面自然产生的详情相关响应。
- 不访问 `/web/geek/{id}`。
- 不从扩展侧主动调用详情 API。
- 不承诺详情结构化入库。
- 导出中用 `metadata.capture_level = "partial_detail"` 标识已经捕获到部分详情响应。
- 报告中列出捕获到的 endpoint、HTTP 状态、能否关联到 `platform_id`、是否具备可映射字段。

风控和失败处理：

- 401、403、429、验证码页面、非 JSON 登录页都记录为 risk event。
- 连续 3 次 risk event 后停止辅助动作。
- 任意疑似强制登出或验证码出现时提示用户手动处理。
- 导出保留失败请求和日志，不静默丢弃。

## 插件命名和迁移

第一阶段新建多渠道插件目录，不删除 `extensions/maimai-scraper`。

迁移步骤：

1. 复制现有 `maimai-scraper` 到 `talent-channel-scraper`。
2. 先保持脉脉行为完全等价，测试通过。
3. 抽出公共 envelope、storage、export、summary。
4. 把脉脉逻辑迁入 `channels/maimai`。
5. 增加 `channels/boss`。
6. 新插件验证稳定后，再决定是否废弃旧 `maimai-scraper`。

这样做的原因是降低回归风险。现有脉脉插件已经承载真实数据抓取和详情补全，不能为了 Boss 渠道一次性破坏现有可用路径。

## 测试策略

静态契约测试：

- manifest 包含 maimai 和 zhipin host permissions。
- 公共导出包含 `metadata.channel`、`schema_version`、`contacts`、`details`、`requests`。
- Boss parser 能从样例 `geeks.json` 提取候选人。
- Boss parser 按 `encryptGeekId` 去重。
- Boss 导出中列表记录 `data_level = partial`。
- Boss `detailJobs` 不出现脉脉批量详情语义字段，除非后续明确实现。

Python 导入测试：

- Boss capture dry-run 不修改数据库。
- Boss capture apply 需要确认文本。
- Boss 导入后 `source_profiles.platform = "boss"`。
- Boss 导入后 `platform_id = encryptGeekId`。
- Boss 导入后 raw_profile 保留完整原始记录。
- 同平台同 platform_id 合并。
- 跨平台疑似同人不因 platform_id 合并。

回归测试：

- 现有 `tests/test_maimai_scraper_extension.py` 继续通过。
- 现有 `tests/test_maimai_detail_import.py` 继续通过。
- 现有 `scripts/test_boss.py` 继续通过。
- 全量运行 `python -m pytest tests scripts -q`。
- 对插件 JS 运行 `node --check`。

人工验收：

1. 在脉脉页面执行一次列表导出，确认旧能力仍可用。
2. 在脉脉页面执行一次小批量详情，确认详情 job 和导出仍可用。
3. 在 Boss 搜索页手动搜索，确认插件捕获 `geeks.json`。
4. 在 Boss 搜索页用安全搜索辅助输入关键词，确认能捕获列表。
5. 导出 Boss JSON，dry-run 报告显示 created、merged、pending、errors。
6. apply 后数据库中可按 `platforms=["boss"]` 过滤到新增来源。
7. 用户手动点击 Boss 候选人详情时，如有自然请求，导出中能看到 `details[]` 或报告中的实验记录。

## 分阶段实施

Phase 1：设计和契约

- 写入本设计文档。
- 增加多渠道 capture envelope 的测试计划。
- 明确 Boss 第一版验收只到 partial。

Phase 2：多渠道插件骨架

- 新建 `extensions/talent-channel-scraper`。
- 迁移脉脉能力，保持行为等价。
- 抽出公共导出和存储。

Phase 3：Boss 列表捕获

- 增加 Boss URL 权限和渠道识别。
- 实现 `geeks.json` 被动捕获。
- 实现 Boss parser 和导出。
- 增加静态测试和样例响应测试。

Phase 4：Boss 导入闭环

- 新增统一导入脚本或 Boss capture 导入脚本。
- dry-run、apply、报告、写后验证。
- 覆盖同平台合并和跨渠道保守合并测试。

Phase 5：Boss 页面辅助和被动详情实验区

- 增加安全搜索辅助。
- 增加有限滚动。
- 增加详情自然请求捕获和报告展示。
- 不做结构化详情入库，除非后续响应结构已验证稳定。

## 验收标准

第一版完成时必须满足：

- Boss 搜索结果可以被插件捕获并导出。
- Boss 导出 JSON 符合统一 envelope。
- Boss 候选人能 dry-run 并确认入库。
- 入库后来源、平台 ID、raw_profile 和 `partial` 数据等级正确。
- 脉脉现有列表和详情能力没有回归。
- 插件不会主动请求 Boss API、不会自动打开 Boss 详情页、不会新开页面探测登录态。
- 所有失败、跳过、风控事件都有日志和导出记录。

## 风险

Boss 页面结构可能变化，`.search-input`、`.icon-search` 或 iframe 路径可能失效。缓解方式是把选择器集中在 Boss channel 模块，并用静态测试覆盖关键字符串。

Boss `encryptGeekId` 是否跨 session 稳定仍需观察。第一版只把它作为 Boss 平台内 ID，不把它用于跨渠道身份合并。

Boss 详情接口结构和风险未知。第一版只被动捕获，不主动抓取，不作为入库核心能力。

多渠道重构可能影响脉脉已有能力。缓解方式是新建目录迁移、保持旧插件目录不动，并先用测试证明脉脉行为等价。

## 后续决策点

如果被动详情实验区连续多批捕获到稳定 Boss 详情响应，并且不会触发风控，再单独设计 Boss 详情结构化入库方案。届时需要新增详情字段映射、dry-run 差异报告、写后验证和小批量人工验收。
