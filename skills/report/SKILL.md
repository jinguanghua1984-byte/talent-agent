---
name: report
description: 生成推荐报告——将筛选后的候选人整理为面向客户的推荐文档，支持版本迭代
---

# 推荐报告

## 触发
/report <jd-id>

## 参数
- jd-id: 目标 JD

## 工具依赖
- Bash — 调用 data-manager.py
- Read / Write — 读写数据和文件

## 流程

### Step 1: 加载数据
1. 读取 JD：`python scripts/data-manager.py jd get <jd-id>`
2. 读取筛选结果：`python scripts/data-manager.py screen list <jd-id>`
3. 对每个 screened/reported 的候选人，读取详细信息：
   `python scripts/data-manager.py candidate get <candidate-id>`
4. 检查已有报告版本：`ls data/reports/<jd-id>/`

### Step 2: 确定候选人范围
拉取该 JD 下所有 status 为 screened 或 reported 的候选人。
按 score 降序排列，默认取 top 5（用户可调整）。

询问用户：确认要包含哪些候选人。

### Step 3: 生成报告
按 references/report-template.md 模板生成推荐报告：
1. JD 概要（从 JD 数据提取）
2. 每个候选人：
   - 画像摘要
   - 匹配亮点（从 screen 结果读取）
   - 差距分析（从 screen gaps 读取）
   - 风险评估（从 screen flags 读取）
   - 职业轨迹表（从 candidate work_experience 读取）
3. 横向对比表
4. 备注区（留空供用户填写）

### Step 4: 保存版本
1. 确定版本号：已有版本中取最大 N，新版本 = N+1（无已有版本则 v1）
2. 保存到 data/reports/<jd-id>/v<N>.md
3. 更新所有包含候选人的 screen status 为 "reported"：
   对每个候选人执行 `python scripts/data-manager.py screen update <jd-id> <candidate-id> <tmpfile>`
   其中 tmpfile 内容为 `{"status": "reported", "updated_at": "<YYYY-MM-DD>"}`

### Step 5: 用户编辑
报告生成后，用户可编辑：
- 调整内容、措辞
- 修改推荐排序
- 添加备注说明
- 删除不需要的候选人

编辑完成后，更新版本的 updated_at。

## 版本管理规则
- 每次生成新版本，包含所有 screened + reported 的候选人
- 即使只新增了 1 个候选人，也重新生成完整报告
- 历史版本保留，不覆盖
- 版本号自动递增

## 使用场景
1. 首次推荐：screen 完成后生成 v1
2. 补充推荐：新候选人 screen 后生成 v2（v2 包含 v1 的 reported + 新 screened）
3. 客户反馈后：调整评分后重新生成新版本

## 注意事项
- 报告面向客户，措辞要专业客观
- 评分只是参考，最终推荐顺序由猎头顾问决定
- 横向对比表帮助客户快速比较
- 每个版本独立完整，不需要参考历史版本
