# 人才库联系方式与微信聊天时间线设计

> **日期**: 2026-05-12
> **状态**: Draft
> **背景**: 顾问在触达和跟进人选后，需要把邮箱、手机号、微信号和微信聊天记录补充回本地人才库，便于后续检索、匹配和跟进复盘。

---

## 1. 目标

第一版补齐两个能力：

1. 在候选人主记录中保留当前联系方式：邮箱、手机号、微信号，以及预留微信 id。
2. 新增手动触发的微信聊天同步 skill，通过本机已安装的 `wechat-cli` 导出指定联系人、指定时间范围的聊天记录，并按候选人归档为 markdown 时间线。

设计原则：

1. 联系方式第一版每类只保留一个当前值，不引入多值联系方式表。
2. 微信聊天正文以 markdown 文件归档，不把完整聊天塞进 SQLite。
3. 写库和同步都必须通过明确候选人身份和人工触发完成，不做后台自动监听。
4. 继续遵守 `talent-library` 的安全边界：批量写入先 dry-run，高风险覆盖先展示旧值和新值。

## 2. 非目标

- 不做微信实时监听或后台自动同步。
- 不直接读取、破解或解析微信本地数据库；底层导出只调用 `wechat-cli`。
- 不在第一版支持同一类型多个邮箱、手机号或微信号。
- 不做聊天内容向量化、摘要模型、自动意向判断或自动跟进建议。
- 不把微信聊天记录同步扩展到 Boss、脉脉站内 IM 或邮件线程。

## 3. 当前上下文

现有人才库主数据源是 `data/talent.db`，由 `scripts/talent_db.py` 初始化和读写。核心表包括：

- `candidates`
- `candidate_details`
- `source_profiles`
- `score_events`
- `match_scores`
- `pending_merges`
- `merge_log`

候选人结构化更新通过 `TalentDB.update_candidate(candidate_id, patch)` 完成，目前允许更新姓名、公司、职位、城市、薪资期望、求职状态、技能标签和数据级别等字段。

本机已安装 `wechat-cli.exe`，其导出命令支持：

```bash
wechat-cli export "<联系人或群名>" --format markdown --output <path> --start-time "YYYY-MM-DD [HH:MM[:SS]]" --end-time "YYYY-MM-DD [HH:MM[:SS]]" --limit <N>
```

## 4. 数据模型

### 4.1 候选人联系方式字段

在 `candidates` 表增加四个可空字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `email` | TEXT | 当前可用邮箱 |
| `phone` | TEXT | 当前可用手机号 |
| `wechat` | TEXT | 当前微信号或顾问可识别的微信名片标识 |
| `wechat_id` | TEXT | 预留微信内部 id 或稳定 id，第一版允许为空 |

同步更新：

- `Candidate` dataclass 增加同名字段。
- `_CANDIDATE_UPDATE_FIELDS` 允许这四个字段。
- `TalentDB._insert_candidate()` 和 `_merge_candidate()` 支持导入时填空，但不静默覆盖已有联系方式。
- FTS 第一版不纳入联系方式字段，避免手机号和微信号被全文检索结果意外暴露。

### 4.2 微信聊天归档索引

新增轻量索引表 `candidate_wechat_timelines`：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | 同步记录 id |
| `candidate_id` | INTEGER | 候选人 id，外键级联删除 |
| `chat_name` | TEXT | `wechat-cli` 使用的联系人或群名 |
| `chat_identifier` | TEXT | 可选稳定标识，第一版可为空 |
| `start_time` | TEXT | 导出起始时间 |
| `end_time` | TEXT | 导出结束时间 |
| `message_count` | INTEGER | 导出消息数量；无法解析时为空 |
| `markdown_path` | TEXT | 归档 markdown 相对路径 |
| `source_tool` | TEXT | 固定为 `wechat-cli` |
| `synced_at` | TEXT | 同步时间 |

聊天正文文件写入：

```text
data/wechat-timelines/<candidate_id>-<safe-name>-<YYYYMMDDHHMMSS>.md
```

文件头使用 YAML-like front matter，记录候选人、联系人、时间范围、导出命令和同步时间；正文保留 `wechat-cli export --format markdown` 的原始 markdown 输出。

## 5. Skill 设计

新增运行时中立 workflow：

```text
agents/workflows/wechat-chat-sync/
├── AGENT.md
├── references/
│   ├── cli-contract.md
│   └── timeline-format.md
└── assets/
    └── timeline-template.md
```

新增运行时适配 skill：

```text
.claude/skills/wechat-chat-sync/SKILL.md
```

如果后续需要安装到 Codex skill 目录，再按 `skill-creator` 生成标准结构。仓库内第一版仍延续现有架构：业务规则放 `agents/workflows/*`，运行时目录只做薄适配。

### 5.1 触发方式

典型请求：

```text
同步候选人 440 和微信联系人 张三 2026-05-01 到 2026-05-12 的聊天记录
```

必要输入：

- 候选人 id，或足够唯一的候选人查询条件。
- 微信联系人名或群名，即传给 `wechat-cli export` 的 `CHAT_NAME`。
- 时间范围。若用户未给时间范围，先问一个最小澄清问题，不默认导出全量聊天。

可选输入：

- `limit`：最大消息数。
- `wechat` / `wechat_id`：同步前或同步后写入候选人联系方式。
- 输出路径：默认使用 `data/wechat-timelines/`。

### 5.2 执行流程

1. 用 `TalentDB.get()` 或 `TalentDB.search()` 定位候选人；命中多条时让用户选择。
2. 展示候选人当前联系方式、目标微信联系人名、时间范围和输出路径。
3. 如果需要更新联系方式，先展示旧值和新值；用户确认后调用 `TalentDB.update_candidate()`。
4. 调用 `wechat-cli export` 导出 markdown 到临时文件。
5. 读取导出结果，补充 front matter，写入正式时间线文件。
6. 解析可识别的消息条数；无法可靠解析时保留为空，不中断归档。
7. 调用新增 `TalentDB.add_wechat_timeline()` 写入索引记录。
8. 输出同步报告，包含候选人、聊天名、时间范围、消息数、归档路径和索引 id。

## 6. CLI 入口

在 `scripts/talent_library.py` 增加子命令：

```bash
python scripts/talent_library.py wechat-sync \
  --candidate-id 440 \
  --chat-name "张三" \
  --start-time "2026-05-01" \
  --end-time "2026-05-12" \
  --limit 1000 \
  --db data/talent.db
```

联系方式单独更新继续走 `update` 场景，实施时可选择先补一个轻量 CLI：

```bash
python scripts/talent_library.py update-contact \
  --candidate-id 440 \
  --email alice@example.com \
  --phone 13800138000 \
  --wechat alice-wx
```

如果实现成本需要收敛，优先实现 `wechat-sync`，并让它支持可选联系方式 patch。

## 7. 错误处理

| 场景 | 处理 |
| --- | --- |
| 找不到候选人 | 不调用 `wechat-cli`，提示先确认 candidate id |
| 候选人查询命中多条 | 展示候选人列表，等待用户选择 |
| 未提供时间范围 | 只问一个澄清问题，不默认全量导出 |
| `wechat-cli` 不存在 | 报告依赖缺失，不写库 |
| `wechat-cli` 返回非零 | 保留 stderr 摘要，不写索引记录 |
| 导出文件为空 | 报告 0 条消息，可选择不写索引 |
| 归档写入失败 | 不写索引记录，报告临时文件位置 |
| 索引写库失败 | 保留 markdown 文件，报告可重试命令 |

## 8. 隐私与安全

聊天记录可能包含高度敏感信息，第一版约束如下：

1. 不把聊天正文写进 `candidates.raw_data` 或 `candidate_details.raw_data`。
2. 不把手机号、微信号加入 FTS。
3. 报告中只展示归档路径和消息数量，不默认贴出聊天全文。
4. 批量同步多个候选人时必须 dry-run，展示候选人、联系人和时间范围。
5. 删除候选人时，`candidate_wechat_timelines` 索引随外键级联删除；markdown 文件是否删除需要单独确认。

## 9. 测试策略

单元测试：

- `Candidate` 支持 `email/phone/wechat/wechat_id` 的构造、序列化和反序列化。
- `TalentDB` 新库创建包含联系方式字段和 `candidate_wechat_timelines`。
- `TalentDB.update_candidate()` 可更新联系方式，并拒绝未知字段。
- `TalentDB.batch_ingest()` 对联系方式执行填空合并，不覆盖已有值。
- `TalentDB.add_wechat_timeline()` 写入索引；候选人删除后索引级联删除。

CLI 测试：

- mock `wechat-cli export` 成功，验证 markdown 归档、front matter 和索引写入。
- mock `wechat-cli export` 失败，验证不写索引。
- 未提供时间范围时拒绝执行并提示澄清。

Workflow 测试：

- `agents/workflows/talent-library/references/data-contract.md` 增加联系方式和微信时间线 API。
- `agents/workflows/talent-library/references/scenarios.md` 的 `update` 场景覆盖联系方式。
- 新增 `wechat-chat-sync` workflow 架构测试，确保 canonical workflow 不引用运行时私有工具名。

回归验证：

```bash
python -m pytest tests scripts -q
```

## 10. 推荐实施顺序

1. 扩展 `Candidate`、`candidates` 表和 `TalentDB.update_candidate()`。
2. 扩展导入/合并逻辑，让联系方式只填空不覆盖。
3. 新增 `candidate_wechat_timelines` 表和 `TalentDB.add_wechat_timeline()`。
4. 增加 `scripts/talent_library.py wechat-sync`，封装 `wechat-cli export`。
5. 新增 `agents/workflows/wechat-chat-sync` 和薄适配 skill。
6. 更新 `talent-library` data contract、scenarios 和安全规则。
7. 补测试并运行全量验证。

## 11. 自检

- 无占位符、未完成标记或悬空待办。
- 联系方式第一版明确为单值字段，未引入多值联系方式表。
- 微信聊天同步明确为手动触发，且必须带时间范围。
- 聊天正文只写 markdown 文件，SQLite 只保存索引。
- 设计范围可拆成一个实施计划，不包含自动摘要、实时监听或多渠道 IM。
