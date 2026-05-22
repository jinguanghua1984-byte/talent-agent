---
name: maimai-talent-search-campaign
description: Use when the user asks to search Maimai from a JD or talent-search requirement, such as 根据xxJD搜索脉脉, 按需求搜索脉脉, 脉脉寻访实施计划, or wants a Maimai campaign from business requirements.
---

# maimai-talent-search-campaign

## 目标

把一次脉脉人才搜索 campaign 从模糊业务输入整理成可执行、可恢复、可审计的无人值守合同。此 Skill 负责需求抽取、搜索计划生成、计划确认点和 workflow 交接；搜索计划生成完毕后与用户确认，确认后自动进入 `agents/workflows/maimai-unattended-campaign/AGENT.md`，不用提示让用户手动启动浏览器。

## 场景语义调用

用户没有显式写出 skill 名称时，只要语义是在“根据需求/JD 去脉脉找人”，也应使用本 Skill。典型触发包括：

- `根据 AI Infra JD 搜索脉脉`
- `根据下面 JD 做脉脉寻访`
- `按需求搜索脉脉，需求如下：...`
- `按需求搜素脉脉，需求如下：...`
- `帮我制定脉脉寻访实施计划`
- `启动一个脉脉无人值守寻访 campaign`
- `基于这个岗位需求生成脉脉人才搜索计划`

如果用户要求“继续执行已有 campaign”“恢复中断任务”“启动浏览器执行搜索”，不要只停留在本 Skill；应读取 `agents/workflows/maimai-unattended-campaign/AGENT.md` 并按 workflow 阶段继续。

## 调用方式

1. 先读取用户本轮提供的提示词、JD、职位描述、粘贴材料或文件路径。
2. 优先自动抽取岗位目标、候选人画像、行业范围、地点、资历、关键词、排除项、交付格式和时间约束。
3. 只对缺失或冲突的信息提问；能稳定推断的字段直接写入合同，并在 `requirements.json` 中标记来源。
4. 如果输入不足以直接执行，进入冷启动：用最小必要问题补齐岗位目标、地域、资历和公司/行业范围，再生成第一版关键词包。
5. 问题中出现业务术语时，必须在问题里解释清楚含义，尤其是“冷启动”“关键词包”“停止阈值”。
6. 生成合同文件后，进入“自动交接”规则。

## 业务合同

面向业务方交付的是一套无人值守人才搜索 campaign 合同：业务方提供 JD、职位描述或粘贴材料，Skill 先自动抽取目标人群、筛选口径、外联交付物和执行边界，再把可执行策略落到 campaign 目录。默认输出根目录为 `data/campaigns/<campaign_id>/`，所有需求、策略、运行策略、执行计划、报告和恢复状态都必须在该目录下可追溯。

## 需求抽取规则

- 优先从调用提示词、JD、职位描述或粘贴内容中自动抽取岗位目标、候选人画像、行业范围、地点、资历、关键词、排除项、交付格式和时间约束。
- 只对缺失或冲突的信息提问；能从输入中稳定推断的字段直接写入合同，并在 `requirements.json` 中标记来源。
- 如果输入不足以直接执行，进入冷启动：用最小必要问题补齐岗位目标、地域、资历和公司/行业范围，再生成第一版关键词包。

## 术语

- 冷启动：输入信息不足或没有明确历史 campaign 可接续时的启动模式，目标是在不追问完整长表单的前提下补齐最小可执行需求。
- 关键词包：围绕岗位、技术栈、行业、公司类型和排除项组织的一组搜索词组合，用于分批构造 search wave。
- 停止阈值：提前停止或转入复核的条件，例如命中质量低、重复率过高、验证码/登录/非 JSON 响应、模板漂移或请求预算耗尽。

## 已确认默认值

- 每日搜索请求预算：500，不包括详情请求。
- 搜索 wave 每组不超过 50 页。
- 详情 pack 每组上限 100 人。
- 默认只抓取 A+B 档；如果 A+B+C 总数不超过 100，则抓取 A+B+C 全部人选。
- 交付格式为本地 Markdown 报告、CSV、飞书云文档、飞书多维表格。
- 计划确认后自动启动 CDP 浏览器、加载临时 profile 和扩展，并进入 canonical workflow 的预检与执行阶段。
- 详情抓取、详评精排、交付包生成和飞书推送在无人值守模式下自动推进；Campaign DB 之后由人工手动整合进主 DB。

## 输出产物

生成并保持以下静态合同文件，供 canonical workflow 和实现脚本读取：

- `requirements.json`：结构化需求、抽取来源、缺失字段和冲突说明。
- `strategy.json`：关键词包、搜索维度、分组策略、筛选规则和停止阈值。
- `run-policy.json`：每日搜索预算、详情抓取范围、自动推进策略、通知/飞书发布策略和安全边界。
- `search-implementation-plan.md`：按 wave/pack 展开的执行计划、恢复方式和验收清单。
- `campaign-manifest.json`：campaign 根目录、输入输出产物、状态文件、报告路径和版本信息。

### 最小合同骨架

`requirements.json` 至少包含：

- `campaign_id`
- `source_input`
- `target_role`
- `candidate_profile`
- `location_constraints`
- `seniority_constraints`
- `company_or_industry_scope`
- `must_have`
- `nice_to_have`
- `exclusions`
- `missing_fields`
- `confirmed_defaults`

`strategy.json` 至少包含：

- `keyword_packages`
- `search_dimensions`
- `company_pools`
- `company_product_mappings`：JD 中公司+部门/产品线缩写的结构化映射，例如 `字节 DMC -> 字节跳动 + DMC/Data Management Center/数据管理中心`。
- `position_aliases`
- `screening_rules`
- `stop_thresholds`
- `delivery_targets`
- `delivery_feedback_contract`：交付后用户评价字段、原因码和下一轮策略调整入口。

`run-policy.json` 必须显式写入以下键和值，作为 workflow 执行、恢复和无人值守推进的 source of truth：

- `daily_search_request_budget=500`
- `search_wave_max_pages=50`
- `detail_pack_max_contacts=100`
- `detail_target_grades=["A","B"]`
- `detail_include_c_when_abc_total_lte=100`
- `auto_continue_after_search_plan_confirmation=true`
- `auto_bootstrap_browser_after_plan_confirmation=true`
- `auto_run_detail_after_list_funnel=true`
- `auto_rank_after_detail_apply=true`
- `auto_publish_feishu_delivery_after_detail_rank=true`
- `allow_campaign_db_auto_apply_after_clean_dry_run=true`
- `allow_detail_campaign_db_auto_apply_after_clean_dry_run=true`
- `allow_feishu_delivery_publish=true`
- `notify_channel="feishu_im"`
- `delivery_language="zh-CN"`
- `main_db_sync_mode="manual_only"`
- `allow_main_db_write=false`

## 自动交接

合同文件全部写入后，自动交接到 `agents/workflows/maimai-unattended-campaign/AGENT.md`。不要停在只生成文件的状态。搜索计划生成完毕后与用户确认；一旦确认，后续执行进入无人值守模式，除平台阻断和主库整合外不再要求人工确认。

交接动作：

1. 下一步读取 canonical workflow：`agents/workflows/maimai-unattended-campaign/AGENT.md`。
2. 用 `campaign-manifest.json` 和 `run-policy.json` 确认 campaign root、预算、通知目标、自动推进策略和安全边界。
3. 先执行状态检查命令，确认 workflow 入口可读：

```powershell
python -m scripts.maimai_campaign_orchestrator status --campaign-root data/campaigns/<campaign_id>
```

4. 用户确认搜索计划后，自动启动 CDP 浏览器、加载临时 profile 和扩展，并交由 workflow 处理登录/验证码/人才银行页健康检查；不要再提示负责人手动启动浏览器。
5. 后续真实执行必须由 `maimai-unattended-campaign` workflow 按阶段处理。

## 安全边界

- 本 Skill 不自行执行真实搜索、详情抓取、数据库写入或云端发布；计划确认后的真实执行必须交给 canonical workflow。
- 涉及真实脉脉页面时，必须交由 `maimai-unattended-campaign` canonical workflow 按阶段执行。
- 无人值守确认点只有搜索计划确认、平台阻断恢复和主 DB 手动整合；campaign DB clean dry-run 后自动 apply，详情 clean dry-run 后自动 apply，交付包生成后自动推送飞书。
- 合同必须明确 `allow_main_db_write=false` 和 `main_db_sync_mode="manual_only"`，禁止无人值守流程把 Campaign DB 自动整合进主库。
