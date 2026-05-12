# 微信聊天时间线格式

聊天正文归档到：

```text
data/wechat-timelines/<candidate_id>-<safe-name>-<YYYYMMDDHHMMSS>.md
```

文件由 front matter 和 `wechat-cli export --format markdown` 原始正文组成。

## Front Matter 字段

- `candidate_id`
- `candidate_name`
- `chat_name`
- `chat_identifier`
- `start_time`
- `end_time`
- `source_tool`
- `synced_at`
- `export_command`

## 隐私规则

- 报告默认只展示路径和消息数量。
- 不把正文复制到 `candidate_details.raw_data`。
- 不把手机号、微信号加入全文索引。
