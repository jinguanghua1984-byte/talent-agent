# talent-library 场景流程

## import：人才导入

适用于平台搜索结果、插件导出 JSON、旧 `data/candidates/*.json`、单个候选人 JSON 或用户提供的结构化候选人列表。

流程：

1. 识别输入类型、平台来源和候选人数量。
2. 校验候选人必要字段，无法解析的记录进入失败明细。
3. 平台原始数据先执行字段映射；旧 JSON 只走迁移或兼容读取路径。
4. 批量写入前展示 dry-run：预计新增、合并、待人工确认、失败数量。
5. 用户确认后调用 `TalentDB.batch_ingest(candidates, platform)`。
6. 对返回的 `pending_merges` 展示人工确认队列，不自动合并置信度不足的候选人。
7. 使用 `assets/import-report-template.md` 生成 `data/output/talent-import-{YYYY-MM-DD}-{slug}.md`。

## search：人才查询

适用于按公司、职位、城市、学历、年限、技能、来源、数据级别、综合分或关键词查找候选人。

流程：

1. 将自然语言查询转换为结构化过滤条件、关键词和排序规则。
2. 结构化条件优先调用 `TalentDB.search(filter, sort, page, page_size)`。
3. 用户明确要求关键词、履历文本或模糊检索时调用 `TalentDB.fulltext_search(query, filter, page, page_size)`。
4. 默认分页展示，每页 20 条；默认字段使用 `assets/candidate-table-template.md`。
5. 用户要求导出时生成 `data/output/talent-search-{YYYY-MM-DD}-{slug}.md`。
6. 查询不得修改 `data/talent.db`。

## match：人才匹配

适用于基于 JD、JD ID、本地 JD 文件或自然语言人才画像，从人才库中筛选候选人。

流程：

1. 读取 JD、JD ID、本地文件或用户给出的画像。
2. 先通过 `TalentDB.search()` 或 `TalentDB.fulltext_search()` 粗筛候选池。
3. 候选池较大时按结构化条件、数据级别和 `overall_score` 先做缩小。
4. 需要完整 JD 匹配评分时，复用 `agents/workflows/screen/AGENT.md` 或调用 `scripts/score_pipeline.py`。
5. 对每个候选人与 JD 的匹配结果调用 `TalentDB.save_match_score(candidate_id, jd_id, score, detail)`。
6. 输出 Top N、匹配理由、关键差距、风险点和数据置信度。
7. 生成 `data/output/talent-match-{YYYY-MM-DD}-{slug}.md`。

## score：人才评分

适用于综合评分和 JD 匹配评分。

流程：

1. 判断评分类型：提到 JD、岗位匹配或职位要求时执行 JD 匹配评分；提到综合分、人才质量或候选人质量时执行综合评分。
2. 综合评分基于候选人完整度、职业轨迹、公司背景、职级、技能稀缺性、求职状态等维度。
3. 综合评分结果调用 `TalentDB.update_overall_score(candidate_id, score, event_detail)`，必须写入评分事件或记录。
4. JD 匹配评分复用 `agents/workflows/screen/AGENT.md` 或 `scripts/score_pipeline.py`。
5. JD 匹配评分结果调用 `TalentDB.save_match_score(candidate_id, jd_id, score, detail)`。
6. 覆盖既有评分前展示旧分数、新分数、评分依据和影响范围，并等待用户确认。
7. 生成 `data/output/talent-score-{YYYY-MM-DD}-{slug}.md`。

## detail：详情抓取

适用于补全候选人的平台详情、履历、教育、项目经历、联系方式线索或来源档案。

流程：

1. 用 `TalentDB.search()` 定位候选人；命中多条时让用户选择。
2. 读取候选人的 `source_profiles`、平台 ID、profile URL 和已有数据级别。
3. 已有平台线索时，按 `agents/workflows/platform-match/AGENT.md` 执行详情抓取。
4. 没有平台线索时，先复用 `agents/workflows/platform-match/AGENT.md` 搜索并做身份确认。
5. 置信度不足、多结果冲突或用户未确认时，不自动写入详情。
6. 详情数据完成字段映射后调用 `TalentDB.enrich(candidate_id, details, source)`。
7. 更新数据级别，记录来源、抓取时间和置信度，生成 `data/output/talent-detail-{YYYY-MM-DD}-{slug}.md`。

## update：人才更新

适用于更新结构化字段、补充履历、合并来源、修正综合分、修正 JD 匹配分或处理待确认合并。

流程：

1. 通过 `TalentDB.search()` 或候选人 ID 定位记录；命中多条时先让用户选择。
2. 展示当前候选人摘要和即将修改的字段。
3. 对用户输入做字段校验；来源类数据只能追加。
4. 批量更新或高风险字段更新必须先 dry-run。
5. 结构化字段更新调用 `TalentDB.update_candidate(candidate_id, patch)`；处理待确认合并时调用 `TalentDB.resolve_merge(candidate_id, merge_decision)`。
6. 详情或来源补全调用 `TalentDB.enrich(candidate_id, details, source)`。
7. 综合分修正调用 `TalentDB.update_overall_score(candidate_id, score, event_detail)`。
8. JD 匹配分修正调用 `TalentDB.save_match_score(candidate_id, jd_id, score, detail)`。
9. 写入后展示变更摘要，生成 `data/output/talent-update-{YYYY-MM-DD}-{slug}.md`。

## delete：人才删除

适用于删除明确错误、重复或用户确认不再保留的候选人。

流程：

1. 根据候选人 ID 或查询条件定位记录；命中多条时展示列表并让用户选择。
2. 展示删除影响范围：候选人主记录、详情、来源、综合评分事件、JD 匹配评分、向量记录和待合并记录。
3. 使用 `assets/delete-confirmation-template.md` 展示候选人摘要和关联数据计数。
4. 要求用户输入明确确认语句：`确认删除候选人 <candidate_id>`。
5. 用户确认后调用 `TalentDB.delete_candidate(candidate_id)`。
6. 删除旧 JSON 必须另行确认；SQLite 删除不隐式删除旧 JSON。
7. 输出删除摘要，生成 `data/output/talent-delete-{YYYY-MM-DD}-{slug}.md`。
