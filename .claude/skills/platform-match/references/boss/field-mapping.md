# Boss 直聘 → candidate.schema 字段映射

> 状态: 待调研校准

| Boss API 字段（预估） | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| name | name | 直接映射 |
| cityName | city | 直接映射 |
| brandName | current_company | 直接映射 |
| jobName | current_title | 直接映射 |
| degree | education | 枚举映射 |
| workYear | work_years | 数字解析 |
| goldHunter | status | 布尔映射 |
| skills[] | skill_tags | 直接映射 |
| experienceList[] | work_experience[] | 结构转换 |
| educationList[] | education_experience[] | 结构转换 |
| encryptUserName | _source.platform_id | 直接映射 |

> **注意**: 所有字段名和转换逻辑需在阶段 1 调研后校准。
