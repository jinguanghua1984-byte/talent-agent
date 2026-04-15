# 脉脉 API 字段 → candidate.schema 映射表

## 基本信息映射

| 脉脉 API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| name | name | 直接映射 |
| gender_str | gender | 1→"男", 2→"女", 其他→"未提及" |
| age | age | 直接映射 |
| city | city | 直接映射 |
| company | current_company | 直接映射 |
| position | current_title | 直接映射 |
| sdegree | education | 1→"本科", 2→"硕士", 3→"博士", 4→"大专" |
| worktime | work_years | "4年7个月" → 提取数字取整 |
| hunting_status | status | 见下方完整映射表 |
| active_state | active_state | 直接映射 |

## 经历映射

| 脉脉 API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| exp[].company | work_experience[].company | 直接映射 |
| exp[].position | work_experience[].title | 直接映射 |
| exp[].v | work_experience[].period | "2021-09-01至今" → "2021-09 - 至今" |
| exp[].description | work_experience[].description | 直接映射 |
| edu[].school | education_experience[].school | 直接映射 |
| edu[].major | education_experience[].major | 直接映射 |
| edu[].v | education_experience[].period | 同上格式转换 |
| edu[].sdegree | education_experience[].description | 附加学历信息 |
| user_project[] | project_experience | 直接映射（name, period, role, description） |

## 意向映射

| 脉脉 API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| job_preferences.regions[] | expected_city | 数组直接映射 |
| job_preferences.positions[] | expected_title | 取第一个 |
| job_preferences.salary | expected_salary | 直接映射 |

## 标签映射

| 脉脉 API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| exp_tags[] + tag_list[] | skill_tags | 合并去重 |

## 来源映射

| 脉脉 API 字段 | sources[] 字段 | 转换逻辑 |
|---|---|---|
| id | platform_id | 直接映射 |
| detail_url | url | 直接映射，无则构造 `https://maimai.cn/u/{id}` |
| — | channel | 固定 "maimai" |
| — | found_at | 搜索时间（ISO 8601） |
| — | enrichment_level | 固定 "enriched" |

## hunting_status 完整映射

| 脉脉值 | candidate status | 说明 |
|---|---|---|
| 5 | "在职-看机会" | 主动求职 |
| 0, 1, 2, 3, 4 | "在职-不看" | 未主动求职 |
| 待确认 | "离职-求职中" | 已离职 |
| 无此字段 | 不更新 | API 未返回时不覆盖 |

> 注：完整枚举值需在登录后实测确认。
