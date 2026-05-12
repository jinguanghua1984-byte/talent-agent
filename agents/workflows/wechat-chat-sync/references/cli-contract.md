# wechat-cli 契约

## 导出命令

```bash
wechat-cli export "<联系人或群名>" --format markdown --output <path> --start-time "YYYY-MM-DD [HH:MM[:SS]]" --end-time "YYYY-MM-DD [HH:MM[:SS]]" --limit <N>
```

## 必填参数

- `CHAT_NAME`：微信联系人名或群名。
- `--format markdown`：第一版固定使用 markdown。
- `--output`：导出到临时文件，再由业务入口写入正式归档文件。
- `--start-time` 和 `--end-time`：必须由用户提供。

## 可选参数

- `--limit`：限制导出消息数。
- `--config`：如用户提供特定配置路径，由运行时透传给 `wechat-cli`。

## 失败处理

- 命令不可用：报告依赖缺失，不写库。
- 返回非零：报告 stderr 摘要，不写索引。
- 输出为空：报告 0 条消息，由用户决定是否重试。
