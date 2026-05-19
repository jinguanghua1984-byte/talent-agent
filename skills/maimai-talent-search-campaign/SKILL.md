---
name: maimai-talent-search-campaign
description: 脉脉人才搜索 campaign 的需求抽取、策略固化和静态执行合同生成。
---

# maimai-talent-search-campaign

## 目标

把一次脉脉人才搜索 campaign 从模糊输入整理成可执行、可恢复、可审计的静态合同。此 Skill 只负责需求抽取和计划产物，不运行真实脉脉请求，不启动浏览器，不发布飞书消息或文档。

## 业务合同

面向业务方交付的是一套无人值守人才搜索 campaign 合同：业务方提供 JD、职位描述或粘贴材料，Skill 先自动抽取目标人群、筛选口径、外联交付物和执行边界，再把可执行策略落到 campaign 目录。默认输出根目录为 `data/campaigns/<campaign_id>/`，所有需求、策略、运行策略、执行计划、报告和恢复状态都必须在该目录下可追溯。

## 需求抽取规则

- 优先从调用提示词、JD、职位描述或粘贴内容中自动抽取岗位目标、候选人画像、行业范围、地点、资历、关键词、排除项、交付格式和时间约束。
- 只对缺失或冲突的信息提问；能从输入中稳定推断的字段直接写入合同，并在 `requirements.json` 中标记来源。
- 如果输入不足以直接执行，进入冷启动：用最小必要问题补齐岗位目标、地域、资历和公司/行业范围，再生成第一版关键词包。

## 术语

- 冷启动：输入信息不足时的启动模式，目标是在不追问完整长表单的前提下补齐最小可执行需求。
- 关键词包：围绕岗位、技术栈、行业、公司类型和排除项组织的一组搜索词组合，用于分批构造 search wave。
- 停止阈值：提前停止或转入复核的条件，例如命中质量低、重复率过高、验证码/登录/非 JSON 响应、模板漂移或请求预算耗尽。

## 已确认默认值

- 每日搜索请求预算：500，不包括详情请求。
- 搜索 wave 每组不超过 50 页。
- 详情 pack 每组上限 100 人。
- 只对 A/B 档人选抓详情。
- 交付格式为本地 Markdown 报告、CSV、飞书云文档、飞书多维表格。

## run-policy.json 合同

`run-policy.json` 必须显式写入以下键和值，作为 workflow 执行、恢复和人工确认的 source of truth：

- `daily_search_request_budget=500`
- `search_wave_max_pages=50`
- `detail_pack_max_contacts=100`
- `detail_target_grades=["A","B"]`
- `notify_channel="feishu_im"`
- `allow_main_db_write=false`

## 输出产物

生成并保持以下静态合同文件，供 canonical workflow 和实现脚本读取：

- `requirements.json`：结构化需求、抽取来源、缺失字段和冲突说明。
- `strategy.json`：关键词包、搜索维度、分组策略、筛选规则和停止阈值。
- `run-policy.json`：每日搜索预算、详情抓取范围、人工确认点和安全边界。
- `search-implementation-plan.md`：按 wave/pack 展开的执行计划、恢复方式和验收清单。
- `campaign-manifest.json`：campaign 根目录、输入输出产物、状态文件、报告路径和版本信息。

## 安全边界

- 本 Skill 不执行真实搜索、详情抓取、数据库写入或云端发布。
- 涉及真实脉脉页面时，必须交由 `maimai-unattended-campaign` canonical workflow 按阶段执行。
- 合同中必须明确人工确认点，尤其是从 dry-run 转 apply、从本地报告转飞书发布的步骤。
