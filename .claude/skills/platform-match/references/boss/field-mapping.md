# Boss 直聘 → candidate.schema 字段映射

> 状态: 已校准（2026-04-20）

| Boss API 字段（geekCard） | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| name | name | 直接映射 |
| gender (int: 1/2) | gender | 枚举映射: 1→男, 2→女 |
| city | city | 直接映射 |
| geekWork.name | current_company + current_title | 解析 "公司·部门·职位"，取首段为公司，末段为职位 |
| highestDegreeName | education | 枚举映射 (大专/本科/硕士/博士/MBA→硕士) |
| workYear ("4年") | work_years | 数字提取 |
| ageDesc ("27岁") | age | 数字提取 |
| activeDesc | active_state | 直接映射 |
| salary ("15-25K") | expected_salary | 直接映射 |
| labelMatchList[].markWord | skill_tags | 提取 markWord 数组 |
| workList[].name + dateRange | work_experience[] | 解析 "公司·职位" + 日期格式化 |
| geekEdu.name | education_experience[] | 解析 "国家·学校·专业" |
| encryptGeekId | _source.platform_id | 直接映射 |
| securityId | _source.security_id | 直接映射 |
| encryptGeekId | _source.url | 拼接: `https://www.zhipin.com/web/geek/{encryptGeekId}` |
