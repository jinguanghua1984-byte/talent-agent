---
name: report
description: 生成推荐报告——将筛选后的候选人整理为面向客户的推荐文档，支持版本迭代
---

# 推荐报告

## 触发
/report <jd-id>

## 流程

### Step 1: 读取数据
1. 读取JD：`python scripts/data-manager.py jd get <jd-id>`
2. 读取筛选结果：`python scripts/data-manager.py screen list <jd-id>`
3. 对每个 screened/reported 的候选人，读取详细信息：
   `python scripts/data-manager.py candidate get <candidate-id>`
4. 检查已有报告版本：`ls data/reports/<jd-id>/`

### Step 2: 确认包含哪些候选人
拉取该 JD 下所有 status 为 screened 或 reported 的候选人。
按 score 降序排列，默认取 top 5（用户可调整）。

询问用户：确认要包含哪些候选人。

### Step 3: 按模板生成报告
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

## 版本管理
- 每次生成包含所有screened+reported候选人，历史版本保留不覆盖
- 版本号自动递增

## 使用场景
- 首次推荐v1，补充推荐v2，反馈调整后新版本