# BossAdapter 测试报告

> 日期: 2026-04-23
> 分支: feat/FEAT-017-boss-zhipin-channel
> 测试文件: `scripts/test_boss.py`
> 源文件: `.claude/skills/platform-match/scripts/adapters/boss.py`
> 运行环境: Python 3.13.0, pytest 9.0.2, Windows 11

## 测试结果总览

| 指标 | 值 |
|------|-----|
| 总用例数 | 54 |
| 通过 | 51 |
| 失败 | 3 |
| 跳过 | 0 |
| 通过率 | 94.4% |
| 运行时间 | 0.12s |

## 失败用例详情

### 1. `TestBossMapToSchema::test_full_geek_card`

- **错误**: `KeyError: 'current_company'`
- **位置**: `scripts/test_boss.py:216`
- **根因**: `map_to_schema()` 解析 `geekWork.name` 后只设置了 `current_title`，未设置 `current_company`。`_parse_geek_work()` 返回了 `(company, title)` 但 company 值被丢弃。
- **影响**: 下游依赖 `current_company` 字段的流程（候选丰富模式 1）将获取不到公司名。
- **修复方向**: 在 `map_to_schema()` 第 200 行附近增加 `result["current_company"] = company`。

### 2. `TestBossMapToSchema::test_geek_work_two_parts`

- **错误**: `KeyError: 'current_company'`
- **位置**: `scripts/test_boss.py:261`
- **根因**: 同上，`map_to_schema()` 未输出 `current_company` 字段。
- **修复方向**: 同上。

### 3. `TestBossMapToSchema::test_work_experience_single_part_name`

- **错误**: `AssertionError: '' != '某公司'`
- **位置**: `scripts/test_boss.py:306`
- **根因**: `map_to_schema()` 第 237-238 行对单段 workList name（无 `·` 分隔符）的处理逻辑为 `w_company, w_title = "", w_name`，将值放入 title 而非 company。测试期望值放入 company。
- **影响**: 单段工作经历名称（如 "某公司"）会被错误地放在职位字段。
- **修复方向**: 单段名称大概率是公司名，应 `w_company, w_title = w_name, ""`。

## 测试覆盖矩阵

### 按方法覆盖

| 方法 | 状态 | 用例数 | 备注 |
|------|------|--------|------|
| `_parse_work_years()` | ✅ 覆盖 | 5 | None, int, str, 带单位, 纯数字 |
| `_parse_age()` | ✅ 覆盖 | 4 | None, 空, 正常, 带单位 |
| `_normalize_period()` | ✅ 覆盖 | 6 | None, 空, 正常, 至今, 非标格式 |
| `_parse_geek_work()` | ✅ 覆盖 | 5 | None, 空, 两段, 三段, 单段 |
| `_parse_geek_edu()` | ✅ 覆盖 | 4 | None, 空, 两段, 三段 |
| `build_search_params()` | ✅ 覆盖 | 9 | candidate, jd, user_input, 空, 组合 |
| `map_to_schema()` | ⚠️ 部分 | 11 | happy path 好，缺边界（MBA/EMBA、fallback 学历） |
| `search()` | ❌ 零覆盖 | 0 | 最复杂方法（~140 行），需 async mock |
| `get_detail()` | ❌ 零覆盖 | 0 | 需 async mock |

### 按集成点覆盖

| 集成点 | 状态 | 备注 |
|--------|------|------|
| `ADAPTERS` 注册表 | ✅ | boss 正确注册 |
| `search.py` 路由 | ✅ | 引用同一注册表实例 |
| `enrich.py` 路由 | ✅ | `cmd_map` 动态查找适配器 |
| `rate_limiter.py` 配额 | ✅ | boss 默认限额已注册 |
| `session.py` 验证 URL | ✅ | boss 验证 URL 已注册 |

## 未覆盖但应测试的场景

### Critical

1. **`search()` 正常流程**: 成功拦截 geeks.json 响应，返回 SearchResult
2. **`search()` 错误路径**: NO_SEARCH_FRAME, NO_SEARCH_INPUT, INTERCEPT_TIMEOUT, API_ERROR, PARSE_ERROR, SEARCH_FAILED
3. **`search()` finally**: listener 被正确移除
4. **`get_detail()` 正常/异常**: 成功返回、非 200、空数据、异常

### Important

5. **`map_to_schema` MBA/EMBA 学历映射**: EDUCATION_MAP fallback 路径
6. **`build_search_params` user_input + candidate 组合**: 同时传入时的行为
7. **`build_search_params` 仅 name 无 company/title**: fallback 到 query=name
8. **`_normalize_period` 带横线的至今**: `"2020-03-至今"` 格式
9. **`_parse_geek_work` 单段名称通过 map_to_schema**: title 回退到原始字符串
10. **`workList` dateRange 为空/None**: 是否仍添加到 work_experience

## PR Review 关联问题

| PR Issue | 关联测试 | 严重度 |
|----------|---------|--------|
| C1: `current_company` 未设置 | test_full_geek_card, test_geek_work_two_parts | Critical |
| C2: `get_detail()` 使用 fetch | 无（方法零覆盖） | Critical |
| C3: `DETAIL_API_URL` 重复 | 无 | Critical |
| C4: 响应拦截竞态条件 | 无（search 零覆盖） | Critical |
| I4: 504 未纳入 retryable | 无 | Important |
