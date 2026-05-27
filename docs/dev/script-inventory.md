# Script Inventory

本清单记录 `scripts/` 的当前职责边界，用于脚本清理、代码审查和新增入口准入。

## Runtime CLI

- `scripts/talent_library.py`：人才库导入、查询和报告入口。
- `scripts/talent_sync.py`：人才库 bundle 导入导出入口。
- `scripts/talent_cloud_sync.py`：人才库云同步入口。
- `scripts/jd_talent_delivery.py`：JD 推荐交付 workflow 入口。
- `scripts/maimai_campaign_orchestrator.py`：脉脉 campaign 阶段编排入口。
- `scripts/score_pipeline.py`：JD 驱动评分 pipeline 入口。

## Library Modules

- `scripts/talent_db.py`、`scripts/talent_models.py`、`scripts/talent_sync_models.py`：人才库核心模型和持久化。
- `scripts/talent_cloud_sync_common.py`、`scripts/talent_cloud_sync_providers.py`：云同步 provider 和通用能力。
- `scripts/maimai_campaign_*.py`：通用脉脉 campaign 计划、评分、报告和反馈模块。
- `scripts/jd_talent_delivery_*.py`：JD 推荐画像、评分卡、匹配和飞书发布模块。

## Legacy Compatibility

- `scripts/data_manager.py`：JSON 数据管理 CLI 的 importable module。
- `scripts/data-manager.py`：旧命令兼容 shim；只转发到 `scripts.data_manager.main()`。
- `scripts/maimai_ai_infra_search_plan.py`、`scripts/maimai_ai_infra_rank.py`、`scripts/maimai_ai_infra_delivery_report.py`：legacy AI Infra strategy 兼容层，仍由 `scripts/maimai_campaign_orchestrator.py` 在旧策略下路由使用。

## Removed Or Approval-Gated Scripts

- `scripts/score_candidates.py`：已移出运行时目录；历史评分入口由 `scripts/score_pipeline.py` 取代。
- `scripts/hunyuan_abc_detail_tasks.py`：已移出运行时目录；历史执行记录保留在 `tasks/archive/2026-05.md`。
- `scripts/hunyuan_abc_parallel_supervisor.ps1`：已移出运行时目录；历史执行记录保留在 `tasks/archive/2026-05.md`。

## Admission Rules

- 新增生产入口必须有稳定 CLI help、聚焦测试和文档入口。
- 新增库模块必须被生产入口或测试引用。
- 测试文件必须放在 `tests/`，不得新增 `scripts/test_*.py`。
- 带固定日期、固定 campaign root 或固定 data/output 路径的一次性任务脚本不得进入 `scripts/`。
