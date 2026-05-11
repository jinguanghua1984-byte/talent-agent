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

### 脉脉详情补全：批量详情接口重放

脉脉批量详情补全优先使用 `extensions/maimai-scraper` 的“批量详情”Tab，在真实 Chrome 登录态和脉脉列表页上下文中低速顺序重放详情接口。该路径不使用 CDP，不打开外部 `profile/detail` 新页，也不自动绕过验证或权限异常。

#### 推荐列表驱动的批量详情

当用户先通过 `talent-library search` 或 `talent-library match` 得到推荐人选列表时，不要把全量脉脉联系人列表直接交给批量详情。应先把推荐结果转换为详情目标 JSON，再导入扩展。

推荐流程：

1. 运行 `talent-library search` 或 `talent-library match`，得到推荐报告。优先使用结构化 JSON 报告，例如 `data/output/talent-match-...json`。
2. 通过 `talent-library detail` 扩展参数生成 `maimai-scraper` 可导入的联系人清单。用户只需要表达业务入口：

```text
talent-library detail --top10-file data/output/<recommendation>.json --out data/output/maimai-detail-targets.json
```

3. 如果已经人工确定候选人 ID，也可以直接按候选人 ID 生成：

```text
talent-library detail --ids 440,747,727 --out data/output/maimai-detail-targets.json
```

4. 当前运行时将上述业务入口映射为 `scripts/talent_library.py detail`，生成目标 JSON；不要让用户直接记忆或调用底层转换脚本。
5. 在 Chrome 的 `maimai-scraper` 中切到“批量详情”，导入 `data/output/maimai-detail-targets.json`。
6. 执行批量详情抓取，完成或暂停后导出完整 JSON。
7. 本地执行 `maimai_detail_import.py dry-run`，确认匹配和字段差异。
8. 用户明确确认后执行 `maimai_detail_import.py apply`。

扩展也兼容直接导入包含 `top10`、`candidates`、`matches`、`results` 或 `items` 的推荐 JSON；但正式流程优先使用 `talent-library detail --top10-file/--ids`，因为它会通过 `data/talent.db` 补齐 `source_profiles.platform_id` 和 `profile_url`。

执行方法：

1. 先用分页抓取或导入 JSON 准备联系人；联系人至少应包含 `id`，最好包含 `trackable_token`、姓名、公司和职位。
2. 打开真实 Chrome 的脉脉列表页，确认 `maimai-scraper` 已重新加载并启用。
3. 在扩展中切到“批量详情”Tab，选择 `safe` 模式；只做小样本验证时才使用 `test` 模式。
4. 点击“开始详情”，扩展会按低速顺序执行 `/api/ent/talent/basic` 及配套项目、求职意向、联系按钮接口。
5. 如果出现连续权限异常、验证码、非 JSON 响应或熔断提示，立即停止盲目重试，先导出完整 JSON 并复盘失败原因。
6. 任务完成或暂停后，使用扩展“导出 JSON”。导出文件必须包含顶层 `contacts`、`details`、`detailJobs`、`requests`。
7. 本地先执行 dry-run：

```bash
python scripts/maimai_detail_import.py dry-run --capture-file <export.json> --db data/talent.db
```

8. dry-run 报告必须展示匹配人数、未匹配人数、失败 jobs，以及每位候选人的工作、教育、项目经历旧值与新值数量。
9. 用户确认后再执行写入：

```bash
python scripts/maimai_detail_import.py apply --capture-file <export.json> --db data/talent.db --confirm "确认写入脉脉详情"
```

10. apply 只写入 `source_profiles.platform='maimai'` 且 `platform_id` 精确匹配的人选；未匹配和失败 job 不写入。
11. 写入后逐人验证 `data_level='detailed'`、`candidate_details` 存在、`raw_data.maimai_detail_capture` 存在，再生成最终报告。

### 脉脉详情补全：列表页弹窗捕获

小批量补全或批量详情失败记录兜底时，使用 `extensions/maimai-scraper` 的真实 Chrome 被动捕获路径，不使用 CDP 抓取，也不依赖外部 profile 链接直接打开的新详情页。

执行方法：

1. 从 `source_profiles` 读取目标候选人的 `platform_id`、`profile_url`、姓名、公司和职位，生成列表页点击勾选清单。
2. 让用户在真实 Chrome 中打开脉脉候选人列表页，例如 `/ent/v41/recruit/talents`，确认 `maimai-scraper` 已重新加载并启用。
3. 在扩展中点击“清除”，清空旧 `contacts`、`details`、`requests` 和分页 IndexedDB 缓存。
4. 用户按清单在列表页内定位候选人，点击候选人卡片或详情入口，等待弹出的详情面板加载完成；不要打开外部 `profile/detail` 链接。
5. 每个候选人完成后检查扩展计数：`请求` 应增长，`详情` 最好增长。若无增长，刷新列表页后重新点击详情弹窗。
6. 10 人或目标批次完成后，使用扩展“导出 JSON”。导出文件必须包含顶层 `details`、`totalDetails`、`requests`；若只有 `contacts`，说明导出路径错误，不能入库。
7. 解析导出 JSON 后，用详情 payload 的 `id` 与本地 `source_profiles.platform_id` 精确匹配；匹配不到的候选人不写入。
8. 使用 `scripts.platform_match.adapters.maimai.MaimaiAdapter.map_to_schema()` 做字段映射；详情接口项目字段可能是 `project_name`、`project_role`、`v`，必须映射到 `project_experience`。
9. 写库前生成 dry-run 报告，展示每位候选人的工作经历、教育经历、项目经历旧值与新值数量，并等待用户明确确认。
10. 用户确认后调用 `TalentDB.enrich()` 写入 `candidate_details`；保留原始详情响应到 `raw_data.maimai_detail_capture`，包含 `capture_file`、`platform_id`、`profile_url`、`record_url`、`record_id` 和原始 payload。
11. 写入后逐人验证 `data_level='detailed'`、详情条数和 `raw_data.maimai_detail_capture` 存在，再生成最终报告。

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
