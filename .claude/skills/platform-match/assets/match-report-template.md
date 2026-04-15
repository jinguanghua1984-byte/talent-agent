# 平台匹配报告

**执行时间**: {{report_time}}
**执行模式**: {{mode}}
**平台**: {{platform}}

## 摘要

| 指标 | 数值 |
|------|------|
| 待处理 | {{total_candidates}} 人 |
| 已丰富 | {{enriched_count}} 人 |
| 未找到 | {{not_found_count}} 人 |
| 待确认 | {{pending_count}} 人 |

## 详细结果

### 已丰富

{{#each enriched}}
#### {{name}} — {{company}}
- **置信度**: {{confidence}}%
- **匹配路径**: {{match_path}}
- **更新字段**: {{updated_fields}}
- **来源**: [脉脉]({{source_url}})

{{/each}}

### 未找到

{{#each not_found}}
- {{name}} — {{company}}（平台未收录）

{{/each}}

### 待确认

{{#each pending}}
- {{name}} — {{company}}（{{reason}}）

{{/each}}
