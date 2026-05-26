# Maimai Search API Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用用户手动搜索产生的扩展被动 capture，生成可确认的脉脉搜索 API 说明书和请求头生成规则。

**Architecture:** 不自动导航、不刷新、不主动点击人才银行页。扩展继续只被动捕获请求；本地脚本读取导出的 JSON，抽取 `/api/ent/v3/search/basic` 请求样本，输出 JSON 规格与 Markdown 说明书，用户确认后才允许把字段写入自动搜索 runner。

**Tech Stack:** Python 3、Chrome MV3 extension `extensions/maimai-scraper`、pytest、现有 `data/output/raw/` 归档约定。

---

## File Structure

- Create: `scripts/maimai_search_api_spec.py` — 离线读取扩展导出 capture，生成搜索 API 规格。
- Create: `tests/test_maimai_search_api_spec.py` — 覆盖请求过滤、请求头策略、字段观测和 CLI 输出。
- Output: `data/output/raw/maimai-search-api-calibration-YYYY-MM-DD.json` — 用户手动搜索后的原始校准导出归档。
- Output: `data/output/maimai-search-api-spec-YYYY-MM-DD.json` — 机器可读规格。
- Output: `data/output/maimai-search-api-spec-YYYY-MM-DD.md` — 面向确认的说明书。
- Modify: `tasks/todo.md` — 跟踪执行和 Review。

## Manual Calibration Protocol

1. 用户在已登录人才银行页手动设置一个条件组合并点击搜索。
2. 扩展只被动捕获请求，不通过 CDP 或 automation 页面触发搜索。
3. 用户导出完整 JSON，或将下载路径发给我归档。
4. 本地脚本生成规格草案，标出 `generated_fields`、`preserve_only_fields` 和待确认字段。
5. 用户确认字段语义后，才允许更新 runner 的请求生成策略。

## Tasks

### Task 1: 离线规格生成器

- [x] 写红测：从扩展导出的 `requests` 中提取 `/api/ent/v3/search/basic`。
- [x] 实现 `build_search_api_spec()`：输出 endpoint、headers、body_policy、field_observations、samples。
- [x] 实现 CLI：`--input <capture.json> --out-json <spec.json> --out-md <spec.md>`。
- [x] 运行 `python -m pytest tests/test_maimai_search_api_spec.py -q`。

### Task 2: 人工校准执行

- [x] 等用户在人才银行页完成多组手动搜索并导出 JSON。
- [x] 归档 capture 到 `data/output/raw/`。
- [x] 运行规格生成 CLI。
- [x] 和用户逐项确认 `allcompanies`、`degrees`、`query_relation`、`positions`、`worktimes` 等字段语义。

### Task 3: Runner 策略更新

- [x] 只有字段确认后，更新 `scripts/maimai_ai_infra_search_runner.py` 或 live gate 的请求生成策略。
- [x] 保持默认只主动生成 `query/search_query` 与分页；新增字段必须来自确认后的规格。
- [x] 补请求体 patch 测试，确保 `sid/sessionid/data_version/highlight_exp` 等模板字段仍保留。

## Acceptance

```bash
python -m pytest tests/test_maimai_search_api_spec.py -q
python -m py_compile scripts/maimai_search_api_spec.py
git diff --check
```

真实搜索执行仍需单独授权，且不在本前置计划中自动触发。

## Review

- 离线规格生成器已生成 `data/output/maimai-search-api-spec-2026-05-14.json` 与 `data/output/maimai-search-api-spec-2026-05-14.md`。
- runner/live gate 已增加显式 `search_filters` 白名单：仅允许已确认字段；`age` 仍未确认，传入会失败。
- 默认自动策略仍只主动生成 `query/search_query` 与分页；确认筛选字段必须由 batch 显式提供，模板字段继续保留。
- 验证：`python -m pytest tests/test_maimai_search_api_spec.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_strategy.py -q` -> `27 passed`。
- 全量回归：`python -m pytest tests scripts -q` -> `509 passed, 1 warning`；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- 差异检查：`git diff --check` -> PASS。
- 用户校正：年龄范围参数确认为 `min_age/max_age`，示例 `min_age=16`、`max_age=40` 表示 16-40 岁；不引入 `age_min/age_max` 别名。
- 年龄范围已写入规格说明书、runner/live gate 白名单和搜索计划元数据；`age` 本身仍不是可写筛选字段。
- 重新生成：`data/output/maimai-search-api-spec-2026-05-14.json` 与 `data/output/maimai-search-api-spec-2026-05-14.md` 已包含年龄范围语义。
- 更新后验证：`python -m pytest tests/test_maimai_search_api_spec.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_strategy.py -q` -> `27 passed`；`python -m py_compile scripts/maimai_search_api_spec.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_plan.py` -> PASS；`python -m pytest tests scripts -q` -> `509 passed, 1 warning`；`git diff --check` -> PASS。
