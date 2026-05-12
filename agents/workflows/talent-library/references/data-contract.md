# talent-library 数据契约

## 主库

主数据源是本地 SQLite：

```text
data/talent.db
```

所有新增、更新、评分、详情补全、删除默认写入主库。workflow 不直接拼接 SQL，必须通过 TalentDB API 完成。

核心表按人才库设计沿用：

- `candidates`
- `candidate_details`
- `candidate_wechat_timelines`
- `source_profiles`
- `score_events`
- `match_scores`
- `pending_merges`
- `merge_log`
- `candidate_fts`
- `candidate_vectors`

## 旧 JSON

旧 JSON 路径：

```text
data/candidates/*.json
```

使用规则：

旧 `data/candidates/*.json` 只作为迁移和兼容入口。

1. 旧 JSON 只作为迁移、兼容读取或用户明确指定的导入入口。
2. 新增候选人默认不写旧 JSON。
3. SQLite 删除不会隐式删除旧 JSON；如需删除旧 JSON，必须单独确认。
4. 不做 SQLite 与旧 JSON 双写一致性承诺。

## 输出目录

所有报告写入：

```text
data/output/
```

命名规则：

| 场景 | 文件名 |
| --- | --- |
| 导入 | `talent-import-{YYYY-MM-DD}-{slug}.md` |
| 查询 | `talent-search-{YYYY-MM-DD}-{slug}.md` |
| 匹配 | `talent-match-{YYYY-MM-DD}-{slug}.md` |
| 评分 | `talent-score-{YYYY-MM-DD}-{slug}.md` |
| 详情补全 | `talent-detail-{YYYY-MM-DD}-{slug}.md` |
| 更新 | `talent-update-{YYYY-MM-DD}-{slug}.md` |
| 删除 | `talent-delete-{YYYY-MM-DD}-{slug}.md` |

短查询可以只在对话中展示，不强制生成文件。

## 联系方式字段

`candidates` 第一版保留单值联系方式：

| 字段 | 含义 |
| --- | --- |
| `email` | 当前可用邮箱 |
| `phone` | 当前可用手机号 |
| `wechat` | 当前微信号或顾问可识别的微信名片标识 |
| `wechat_id` | 预留微信内部 id 或稳定 id |

联系方式可通过 `TalentDB.update_candidate(candidate_id, patch)` 更新。批量导入时只填补空值，不静默覆盖已有联系方式。

## 微信聊天时间线

微信聊天正文归档到 `data/wechat-timelines/*.md`。SQLite 只在 `candidate_wechat_timelines` 保存索引，包括候选人、微信联系人或群名、起止时间、消息数、归档路径和同步时间。

## 核心 TalentDB API

`talent-library` workflow 只通过以下 API 读写人才库：

| API | 用途 |
| --- | --- |
| `TalentDB.batch_ingest(candidates, platform)` | 批量导入候选人，返回新增、合并、待确认和失败明细 |
| `TalentDB.search(filter, sort, page, page_size)` | 结构化候选人查询 |
| `TalentDB.fulltext_search(query, filter, page, page_size)` | 全文候选人查询 |
| `TalentDB.enrich(candidate_id, details, source)` | 追加来源并补全详情 |
| `TalentDB.update_candidate(candidate_id, patch)` | 结构化字段局部更新 |
| `TalentDB.add_wechat_timeline(candidate_id, data)` | 写入微信聊天 markdown 归档索引 |
| `TalentDB.update_overall_score(candidate_id, score, event_detail)` | 更新综合分并记录评分事件 |
| `TalentDB.save_match_score(candidate_id, jd_id, score, detail)` | 保存候选人与 JD 的匹配评分 |
| `TalentDB.delete_candidate(candidate_id)` | 事务化硬删除候选人及关联记录 |
| `TalentDB.resolve_merge(candidate_id, merge_decision)` | 处理待确认合并 |

如果某个 API 尚未实现，workflow 应报告能力缺口，不得绕过 TalentDB 直接操作数据库。
