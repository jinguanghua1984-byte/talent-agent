# Boss 直聘 API 字段 → candidate.schema 映射表

> 来源: `scripts/adapters/boss.py` `map_to_schema()` (2026-04-20 校准)

## 基本信息映射

| Boss API 字段 (geekCard) | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| name | name | 直接映射 |
| gender | gender | 1→"男", 2→"女", 其他→跳过 |
| city | city | 直接映射 |
| geekWork.name | current_company + current_title | "公司·部门·职位" → 取第一段为公司、最后一段为职位；无分隔符时整体作为公司名 |
| highestDegreeName | education | 通过 EDUCATION_MAP 映射（"MBA"/"EMBA"→"硕士"） |
| workYear | work_years | "4年" → 提取数字 |
| ageDesc | age | "27岁" → 提取数字 |
| activeDesc | active_state | 直接映射 |
| salary | expected_salary | 直接映射 |

## 经历映射

| Boss API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| workList[].name | work_experience[].company + title | "公司·职位" → 按·分割，首段为公司，末段为职位 |
| workList[].dateRange | work_experience[].period | "2024-2026" → "2024-06 - 2026-06"；含"至今" → "start - 至今" |
| geekEdu.name | education_experience[].school + major | "国家·学校·专业" → 按·分割，第二段为学校，第三段为专业 |

## 标签映射

| Boss API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| labelMatchList[].markWord | skill_tags | 提取所有 markWord 为列表 |

## 来源映射

| Boss API 字段 | sources[] 字段 | 转换逻辑 |
|---|---|---|
| encryptGeekId | platform_id | 直接映射 |
| securityId | security_id | 直接映射 |
| — | url | 构造 `https://www.zhipin.com/web/geek/{encryptGeekId}` |
| — | channel | 固定 "boss" |

## 学历枚举映射

| Boss 原始值 | candidate education |
|---|---|
| 大专 | 大专 |
| 本科 | 本科 |
| 硕士 | 硕士 |
| 博士 | 博士 |
| MBA | 硕士 |
| EMBA | 硕士 |
