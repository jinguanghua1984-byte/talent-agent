# Task Archive

这里保存已经完成的任务记录。`tasks/todo.md` 只作为当前工作台，不长期保存完整历史。

## 归档规则

- 完成任务后，把完整计划和 Review 移到 `tasks/archive/YYYY-MM.md`。
- `tasks/todo.md` 只保留最近 1-3 个完成摘要，以及归档索引。
- 归档内容保持 append-only；合并冲突时保留双方记录。
- 查历史优先用 `rg "<关键词>" tasks/archive tasks/lessons.md memory/error-log.md`。

## 写入格式

每个归档块保留原任务标题、目标、计划、Review、关键产物路径、验证命令和结果。
