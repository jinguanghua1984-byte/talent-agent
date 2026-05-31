# Script Inventory

本清单记录 `scripts/` 的当前职责边界，用于脚本清理、代码审查和新增入口准入。

## Runtime CLI

- `scripts/talent_library.py`：人才库导入、查询和报告入口。
- `scripts/talent_sync.py`：人才库 bundle 导入导出入口。
- `scripts/talent_cloud_sync.py`：人才库云同步入口。
- `scripts/jd_talent_delivery.py`：JD 推荐交付 workflow 入口。
- `scripts/maimai_campaign_orchestrator.py`：脉脉 campaign 阶段编排入口。
- `scripts/score_pipeline.py`：JD 驱动评分 pipeline 入口。
- `scripts/boss_app_sourcing.py`：BOSS App 推荐列表寻访合同和状态初始化入口。

## Library Modules

- `scripts/talent_db.py`、`scripts/talent_models.py`、`scripts/talent_sync_models.py`：人才库核心模型和持久化。
- `scripts/talent_cloud_sync_common.py`、`scripts/talent_cloud_sync_providers.py`：云同步 provider 和通用能力。
- `scripts/maimai_campaign_*.py`：通用脉脉 campaign 计划、评分、报告和反馈模块。
- `scripts/jd_talent_delivery_*.py`：JD 推荐画像、评分卡、匹配和飞书发布模块。

## Legacy Compatibility

- `scripts/data_manager.py`：JSON 数据管理 CLI 的 importable module。
- `scripts/data-manager.py`：旧命令兼容 shim；只转发到 `scripts.data_manager.main()`。
- `scripts/maimai_ai_infra_*`：legacy AI Infra strategy 兼容模块组，仍由 `scripts/maimai_campaign_orchestrator.py`、脉脉 campaign pipeline 和回归测试在旧策略路径下使用；当前整组受兼容层保护。现有模块包括：
  - `scripts/maimai_ai_infra_campaign.py`
  - `scripts/maimai_ai_infra_delivery_report.py`
  - `scripts/maimai_ai_infra_detail_live_gate.py`
  - `scripts/maimai_ai_infra_detail_plan.py`
  - `scripts/maimai_ai_infra_detail_report.py`
  - `scripts/maimai_ai_infra_outreach_export.py`
  - `scripts/maimai_ai_infra_pipeline.py`
  - `scripts/maimai_ai_infra_rank.py`
  - `scripts/maimai_ai_infra_review.py`
  - `scripts/maimai_ai_infra_search_live_gate.py`
  - `scripts/maimai_ai_infra_search_plan.py`
  - `scripts/maimai_ai_infra_search_runner.py`

清理原则：`maimai_ai_infra_*` 当前不是一次性脚本；它们是旧策略兼容层。只有在 `maimai_campaign_*` 完成等价迁移、orchestrator 不再路由到旧模块、并且对应回归测试移除旧路径后，才能另起计划删除。

## Removed Or Approval-Gated Scripts

- `scripts/score_candidates.py`：已移出运行时目录；历史评分入口由 `scripts/score_pipeline.py` 取代。
- `scripts/hunyuan_abc_detail_tasks.py`：已移出运行时目录；历史执行记录保留在 `tasks/archive/2026-05.md`。
- `scripts/hunyuan_abc_parallel_supervisor.ps1`：已移出运行时目录；历史执行记录保留在 `tasks/archive/2026-05.md`。

## Admission Rules

- 新增生产入口必须有稳定 CLI help、聚焦测试和文档入口。
- 新增库模块必须被生产入口或测试引用。
- 测试文件必须放在 `tests/`，不得新增 `scripts/test_*.py`。
- 带固定日期、固定 campaign root 或固定 data/output 路径的一次性任务脚本不得进入 `scripts/`。
