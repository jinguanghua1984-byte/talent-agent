# Main DB Sync Gates Policy

## 适用范围

适用于 Campaign DB、同步 bundle 或本地候选结果准备写入主库 `data/talent.db` 的 workflow。

## 基本边界

- `data/talent.db` 是主人才库，未通过本 policy 前不得创建、覆盖或写入。
- Campaign DB apply 不等于主库 apply；Campaign DB clean 后仍必须单独执行主库 dry-run。
- 无人值守授权不覆盖主库写入。

## 必需步骤

1. 先执行 `talent_sync.py export` 导出源 bundle。
2. 执行 `verify-bundle` 校验 bundle。
3. 对目标 `data/talent.db` 执行 `talent_sync.py import` dry-run，生成 dry-run/apply 计划。
4. dry-run 必须覆盖新增、更新、冲突、跳过、身份绑定、字段来源和交付影响。
5. 只有 Campaign DB clean、dry-run 无阻塞冲突、bundle 校验通过、用户对本次 dry-run 给出一次总授权，并提供 `CONFIRM_SYNC_TEXT` / `确认同步人才库`，才能执行 `talent_sync.py import --apply`。

## 授权约束

一次总授权只覆盖本 campaign、本 bundle 和本 dry-run。源数据、bundle、目标 DB 或 dry-run 结果变化后，必须重新 dry-run 并重新授权。不得自动执行主库同步，不得复用旧授权。
