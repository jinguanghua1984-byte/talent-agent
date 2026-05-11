# 脉脉批量详情抓取方案设计

日期：2026-05-10

## 背景

当前 `talent-library detail` 已验证一条可行路径：

1. 在真实 Chrome 登录态中打开脉脉候选人列表页。
2. 用户在列表页内点击候选人卡片，打开详情弹窗。
3. `maimai-scraper` 被动捕获详情接口。
4. 导出完整 JSON。
5. 本地按 `source_profiles.platform_id` 精确匹配，dry-run 后写入 `TalentDB.enrich()`。

这个路径已成功补全 Top10 候选人详情，但如果需要处理几十到几百人，逐个手动点击详情弹窗不可接受。

已确认的限制：

- CDP 抓取不可行，不作为方案基础。
- 外部 `profile/detail` 链接新开页无法稳定捕获详情。
- 列表页内详情弹窗可以捕获。
- 详情核心接口不是旧的 `/api/pc/u/`，而是 `/api/ent/talent/basic`。
- 当前扩展必须使用完整导出，不能只导出 IndexedDB 中的分页联系人列表。

## 已验证接口

成功捕获的详情核心接口形态：

```text
/api/ent/talent/basic?channel=www&data_version=3.1&need_ai_info=0&resume_project_id=&show_tip=0&to_uid=<uid>&trackable_token=<trackable_token>&version=1.0.0
```

配套详情接口：

```text
/api/ent/candidate/associated/project/list?channel=www&data_version=4.1&fr=profile&to_uid=<uid>&version=1.0.0
/api/ent/talent/job_preference?channel=www&page=0&size=20&to_uid=<uid>&version=1.0.0
/api/ent/v3/search/contact_btn?channel=www&to_uids=<uid>&version=1.0.0
```

其中 `to_uid` 来自列表页联系人 `id`，`trackable_token` 通常来自列表页联系人 `trackable_token`。在已验证 Top10 中，9/10 的联系人 token 与详情接口 token 完全一致；仍需保留失败兜底。

## 目标

新增一个可暂停、可恢复、有限流熔断的批量详情抓取能力：

- 输入：`maimai-scraper` 已抓到的联系人列表，或用户上传的候选人 ID/token 列表。
- 输出：包含 `contacts`、`details`、`detailJobs`、`requests` 的完整 JSON。
- 运行环境：真实 Chrome 登录态中的脉脉列表页上下文。
- 入库：仍由本地 `talent-library detail` 执行 dry-run、确认、写入和验证。

## 推荐方案：扩展内接口重放

在 `extensions/maimai-scraper` 中新增“批量详情”能力，优先通过页面 MAIN world 的 `fetch` 重放详情接口。

### 数据来源

按优先级读取：

1. `PagerDB.contacts`
2. `chrome.storage.local.contacts`
3. 用户导入的 JSON 联系人列表

每个联系人至少需要：

- `id`：作为 `to_uid`
- `trackable_token`：用于 `/api/ent/talent/basic`
- `name`：用于日志和人工复核
- `company` / `position`：用于复核

缺少 `id` 的记录跳过。缺少 `trackable_token` 的记录进入兜底队列。

### 执行链路

```text
popup.js
  -> background.js 创建 detail job
  -> content.js 转发批量详情命令
  -> inject.js 在 MAIN world 中按限流策略 fetch
  -> content.js 接收结果
  -> background.js 写入 DetailDB / chrome.storage.local.details
  -> popup.js 展示进度
```

### 数据存储

建议新增 `DetailDB`，类似当前 `PagerDB`：

- DB：`maimai_detail`
- store：`details`
- keyPath：`id`

详情任务状态建议保存为：

```json
{
  "id": "166812124",
  "name": "范青",
  "trackable_token": "...",
  "status": "done",
  "attempts": 1,
  "started_at": "2026-05-10T...",
  "finished_at": "2026-05-10T...",
  "detail": {
    "basic": {},
    "projects": {},
    "job_preference": {}
  },
  "errors": []
}
```

导出 JSON 顶层结构：

```json
{
  "exportTime": "...",
  "metadata": {
    "export_type": "full",
    "detail_mode": "batch_replay",
    "total_jobs": 100,
    "done": 92,
    "failed": 8
  },
  "contacts": [],
  "details": [],
  "detailJobs": [],
  "requests": []
}
```

## 限流与熔断

第一版不并发。

建议默认策略：

- 单人详情请求间隔：5-12 秒随机。
- 每 30 人暂停：5-10 分钟随机。
- 每日上限：100-150 人。
- 单人最多重试：2 次。
- 连续 3 次 401 / 403 / 验证码 / 非 JSON 响应：立即熔断。
- 页面切到后台时可以继续，但如果 Chrome 休眠导致失败，需要暂停并提示用户。

熔断状态要写入导出 JSON，不要静默失败。

## 兜底方案：自动点击详情弹窗

当接口重放失败，尤其是 `trackable_token` 缺失或失效时，进入自动点击兜底。

兜底不使用 CDP，而是在页面脚本上下文中做 DOM 自动化：

1. 在列表页按候选人姓名、公司、职位或 `data-*` 属性定位候选人卡片。
2. 滚动到卡片。
3. 点击卡片或详情入口。
4. 等待 `/api/ent/talent/basic` 被捕获。
5. 关闭详情弹窗。
6. 进入下一个候选人。

兜底模式风险更高，必须更保守：

- 每人间隔 8-20 秒。
- 每 10 人暂停 3-5 分钟。
- 任何验证码、权限异常或页面结构变化立即暂停，等待用户处理。

## 入库流程

本地入库不应直接写扩展导出的全部数据。

标准流程：

1. 读取导出 JSON。
2. 校验顶层必须包含 `details` 或 `detailJobs`。
3. 用详情 payload 的 `id` 精确匹配本地 `source_profiles.platform_id`。
4. 调用 `MaimaiAdapter.map_to_schema()` 做字段映射。
5. 生成 dry-run 报告：
   - 匹配人数
   - 未匹配人数
   - 工作经历旧值与新值数量
   - 教育经历旧值与新值数量
   - 项目经历旧值与新值数量
   - 原始响应保留状态
6. 用户明确确认后调用 `TalentDB.enrich()`。
7. 保留原始响应到 `raw_data.maimai_detail_capture`。
8. 写入后逐人验证：
   - `data_level='detailed'`
   - `candidate_details` 条数符合预期
   - `raw_data.maimai_detail_capture` 存在

## 字段映射注意事项

详情接口项目字段可能使用：

- `project_name`
- `project_role`
- `v`

需要映射到：

- `project_experience[].name`
- `project_experience[].role`
- `project_experience[].period`

该映射已在 `scripts/platform_match/adapters/maimai.py` 中补充，并由 `scripts/test_maimai.py` 覆盖。

## 分阶段实施

### Phase 1：接口重放最小闭环

- 新增批量详情 Tab。
- 从现有 contacts 生成 detail jobs。
- 对 `/api/ent/talent/basic` 做顺序 fetch。
- 写入 `details` 和 `detailJobs`。
- 完整导出 JSON。
- 用 30 人以内批次验证。

### Phase 2：多接口补全

- 增加项目列表接口。
- 增加求职意向接口。
- 合并到单个 detail job。
- 生成更完整的 details payload。

### Phase 3：断点恢复和熔断

- 保存 job 状态。
- 支持暂停、继续、跳过失败。
- 实现 batch pause、daily limit、circuit break。
- 导出失败原因。

### Phase 4：自动点击兜底

- 为 token 缺失或接口失败的人选启用 DOM 点击。
- 捕获弹窗请求。
- 自动关闭弹窗。
- 失败时暂停给用户处理。

### Phase 5：talent-library 集成

- 新增本地解析脚本或 workflow 小工具。
- 标准化 dry-run 报告。
- 标准化最终详情补全报告。
- 把批量详情抓取流程写入 `talent-library detail` 的正式操作手册。

## 风险

- 脉脉接口参数可能变化，尤其是 `data_version`、`trackable_token` 规则。
- 批量访问可能触发风控，必须保持低速和熔断。
- 某些详情接口可能需要列表页上下文中额外状态。
- 自动点击兜底依赖 DOM 结构，维护成本高。
- 捕获数据涉及个人信息，导出文件和数据库必须妥善保存，不应提交到远端仓库。

## 推荐下一步

先实现 Phase 1 和 Phase 2，不做自动点击兜底。

原因：

- 当前成功样本证明 `trackable_token` 大多可从列表数据直接复用。
- 接口重放对页面扰动最小。
- 实现成本低，容易限流和断点恢复。
- 自动点击方案可以作为少数失败记录的后续增强。