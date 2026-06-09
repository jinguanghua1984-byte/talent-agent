# Campaign Recovery Policy

## 事实源

恢复时只信磁盘事实，不得盲信内存上下文。优先读取 campaign-local raw、`state/continuation-plan.json`、`state/events.jsonl`、`state/request-ledger.jsonl`、import ledger、reports 和 dry-run/apply 结果。

## 中断证据

停机后必须保留已成功 raw 和中断证据，写入 `reports/interruption-*.json`，追加 `state/events.jsonl` 或 `state/request-ledger.jsonl`，并更新 `state/continuation-plan.json`。已成功页、已成功 target 或 terminal job 不得重复请求。

## 恢复入口

长任务恢复优先运行 `campaign_status summarize` 获取一页摘要，再运行 `next-action` 获取合法下一步、阻塞原因、需要的确认文本、安全命令和禁止事项。

## 停机后行为

如果恢复摘要缺少必要 raw、manifest、continuation plan 或 dry-run 证据，必须停止并生成修复说明。不得用模型推断替代缺失的磁盘事实，不得在不确定阶段继续发起平台请求或写入数据库。
