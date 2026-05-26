# BossAdapter Bugfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 BossAdapter 测试报告中的 3 个失败用例 + PR Review 中的 Critical/Important 问题，使测试通过率从 94.4% 提升到 100%。

**Architecture:** 纯 bugfix，不改变架构。修复 `map_to_schema()` 遗漏的 `current_company` 字段、workList 单段名称解析逻辑、`get_detail()` 反爬违规代码、`DETAIL_API_URL` 重复值、retryable 状态码遗漏、search.py 代码质量问题，以及 git 数据清理和文档同步。

**Tech Stack:** Python 3.13, pytest

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `.claude/skills/platform-match/scripts/adapters/boss.py` | 修改 | 修复 5 个 bug（current_company、单段名称、get_detail、DETAIL_API_URL、504） |
| `.claude/skills/platform-match/scripts/search.py` | 修改 | 修复 2 个代码质量问题（变量名、异常捕获） |
| `scripts/test_boss.py` | 修改 | 补充 2 个边界测试用例 |
| `.gitignore` | 修改 | 添加 `data/*.json` 排除规则 |
| `.claude/skills/platform-match/references/boss/field-mapping.md` | 修改 | 补充 `current_company` 映射 |
| `.claude/skills/platform-match/references/boss/search-mechanism.md` | 修改 | 补充 `get_detail()` 暂不可用 |
| `.claude/skills/platform-match/references/boss/api-reference.md` | 修改 | 标注详情端点待调研 |

---

### Task 1: 修复 `map_to_schema()` 遗漏 `current_company` 字段

**Files:**
- Modify: `.claude/skills/platform-match/scripts/adapters/boss.py:196-202`
- Test: `scripts/test_boss.py`（已有 test_full_geek_card、test_geek_work_two_parts 两个失败用例）

- [ ] **Step 1: 确认当前失败**

Run: `python -m pytest scripts/test_boss.py::TestBossMapToSchema::test_full_geek_card scripts/test_boss.py::TestBossMapToSchema::test_geek_work_two_parts -v`
Expected: 2 个 FAILED，KeyError: 'current_company'

- [ ] **Step 2: 修复 boss.py — 在 `map_to_schema()` 中补充 `current_company` 赋值**

将 boss.py 第 198-202 行:

```python
            company, title = _parse_geek_work(api_data.get("geekWork"))
            if title:
                result["current_title"] = title
            else:
                result["current_title"] = geek_work_name
```

改为:

```python
            company, title = _parse_geek_work(api_data.get("geekWork"))
            if company:
                result["current_company"] = company
            if title:
                result["current_title"] = title
            elif not company:
                result["current_title"] = geek_work_name
```

关键变更:
- 新增 `if company: result["current_company"] = company`
- `else` 分支改为 `elif not company` — 只在 company 和 title 都为空时才回退到原始字符串

- [ ] **Step 3: 运行测试验证修复**

Run: `python -m pytest scripts/test_boss.py::TestBossMapToSchema -v`
Expected: 全部 11 个用例 PASS（含之前失败的 2 个）

- [ ] **Step 4: 提交**

```bash
git add .claude/skills/platform-match/scripts/adapters/boss.py
git commit -m "fix(FEAT-017): map_to_schema 补充 current_company 字段输出"
```

---

### Task 2: 修复 workList 单段名称解析逻辑

**Files:**
- Modify: `.claude/skills/platform-match/scripts/adapters/boss.py:237-240`
- Test: `scripts/test_boss.py`（已有 test_work_experience_single_part_name 失败用例）

- [ ] **Step 1: 确认当前失败**

Run: `python -m pytest scripts/test_boss.py::TestBossMapToSchema::test_work_experience_single_part_name -v`
Expected: FAILED，`AssertionError: '' != '某公司'`

- [ ] **Step 2: 修复 boss.py — 单段名称放入 company 而非 title**

将 boss.py 第 239-240 行:

```python
                else:
                    w_company, w_title = "", w_name
```

改为:

```python
                else:
                    w_company, w_title = w_name, ""
```

单段名称（无 `·` 分隔符）大概率是公司名，应放入 company 字段。

- [ ] **Step 3: 运行测试验证修复**

Run: `python -m pytest scripts/test_boss.py::TestBossMapToSchema -v`
Expected: 全部 11 个用例 PASS

- [ ] **Step 4: 提交**

```bash
git add .claude/skills/platform-match/scripts/adapters/boss.py
git commit -m "fix(FEAT-017): workList 单段名称解析为 company 而非 title"
```

---

### Task 3: 禁用 `get_detail()` 并标记 `DETAIL_API_URL` 为 TODO

**Files:**
- Modify: `.claude/skills/platform-match/scripts/adapters/boss.py:32-38, 425-463`

- [ ] **Step 1: 修复 `DETAIL_API_URL`**

将 boss.py 第 35-38 行:

```python
# 候选人详情端点（需 securityId）
DETAIL_API_URL = (
    "https://www.zhipin.com/wapi/zpitem/web/boss/search/geeks.json"
)
```

改为:

```python
# 候选人详情端点（待调研，get_detail 暂不可用）
DETAIL_API_URL = ""
```

- [ ] **Step 2: 修复 `get_detail()` — 标记为未实现**

将 boss.py 第 425-463 行整个方法替换为:

```python
    async def get_detail(
        self,
        page: Any,
        platform_id: str,
    ) -> CandidateData | None:
        """获取候选人详情。

        当前不可用: Boss 直聘详情端点未调研，且 page.evaluate(fetch)
        会触发反爬检测导致强制登出。待改为被动拦截方式实现。
        """
        logger.warning(
            "Boss get_detail 暂不可用: platform_id=%s（需改为被动拦截）",
            platform_id,
        )
        return None
```

- [ ] **Step 3: 运行全部测试确保无回归**

Run: `python -m pytest scripts/test_boss.py -v`
Expected: 54 passed, 0 failed

- [ ] **Step 4: 提交**

```bash
git add .claude/skills/platform-match/scripts/adapters/boss.py
git commit -m "fix(FEAT-017): 禁用 get_detail 并标记 DETAIL_API_URL 为 TODO"
```

---

### Task 4: 补充 retryable 状态码 504

**Files:**
- Modify: `.claude/skills/platform-match/scripts/adapters/boss.py:380`

- [ ] **Step 1: 修复 retryable 状态码列表**

将 boss.py 第 380 行:

```python
                        retryable=intercepted_response.status in (429, 502, 503),
```

改为:

```python
                        retryable=intercepted_response.status in (429, 502, 503, 504),
```

- [ ] **Step 2: 提交**

```bash
git add .claude/skills/platform-match/scripts/adapters/boss.py
git commit -m "fix(FEAT-017): search retryable 状态码补充 504"
```

---

### Task 5: 修复 search.py 代码质量问题

**Files:**
- Modify: `.claude/skills/platform-match/scripts/search.py:84, 149-152`

- [ ] **Step 1: 修复变量名 `p` 遮蔽**

将 search.py 第 83-86 行:

```python
                boss_page = next(
                    (p for p in existing_pages if "zhipin.com" in p.url),
                    None,
                )
```

改为:

```python
                boss_page = next(
                    (pg for pg in existing_pages if "zhipin.com" in pg.url),
                    None,
                )
```

- [ ] **Step 2: 收窄异常捕获范围**

将 search.py 第 149-152 行:

```python
            try:
                record_search(platform, headless)
            except Exception:
                pass  # 状态持久化失败不应丢弃搜索结果
```

改为:

```python
            try:
                record_search(platform, headless)
            except (OSError, json.JSONDecodeError):
                pass  # 状态持久化失败不应丢弃搜索结果
```

- [ ] **Step 3: 提交**

```bash
git add .claude/skills/platform-match/scripts/search.py
git commit -m "refactor(FEAT-017): search.py 变量名去遮蔽 + 异常捕获收窄"
```

---

### Task 6: 清理 git 跟踪的捕获数据

**Files:**
- Modify: `.gitignore`
- Delete (from git): `data/boss-search-response.json`, `data/boss-api-capture.json`, `data/boss-captured-requests.json`

- [ ] **Step 1: 在 .gitignore 中添加捕获数据排除规则**

在 `.gitignore` 文件末尾追加:

```
# API capture data (debug only, not for version control)
data/boss-api-capture.json
data/boss-captured-requests.json
data/boss-search-response.json
```

- [ ] **Step 2: 从 git 移除已跟踪的捕获数据文件**

Run: `git rm --cached data/boss-search-response.json data/boss-api-capture.json data/boss-captured-requests.json`
Expected: 3 个文件从 git index 移除（本地文件保留）

- [ ] **Step 3: 提交**

```bash
git add .gitignore
git commit -m "chore(FEAT-017): 从 git 移除 API 捕获数据 + .gitignore 排除"
```

---

### Task 7: 补充边界测试用例

**Files:**
- Modify: `scripts/test_boss.py`

- [ ] **Step 1: 添加 `get_detail` 返回 None 测试**

在 `TestBossMapToSchema` 类之后新增:

```python
class TestBossGetDetailUnavailable(unittest.TestCase):
    """get_detail 暂不可用测试。"""

    def test_get_detail_returns_none(self):
        import asyncio
        from adapters.boss import BossAdapter

        adapter = BossAdapter()
        result = asyncio.get_event_loop().run_until_complete(
            adapter.get_detail(None, "test_id")
        )
        self.assertIsNone(result)
```

- [ ] **Step 2: 添加 MBA/EMBA 学历映射测试**

在 `TestBossMapToSchema` 类中新增:

```python
    def test_education_mba_maps_to_master(self):
        """MBA 应映射为硕士。"""
        result = self._call({"name": "测试", "highestDegreeName": "MBA"})
        self.assertEqual(result["education"], "硕士")

    def test_education_emba_maps_to_master(self):
        """EMBA 应映射为硕士。"""
        result = self._call({"name": "测试", "highestDegreeName": "EMBA"})
        self.assertEqual(result["education"], "硕士")

    def test_education_unknown_passthrough(self):
        """未知学历应原样保留。"""
        result = self._call({"name": "测试", "highestDegreeName": "高中"})
        self.assertEqual(result["education"], "高中")
```

- [ ] **Step 3: 运行全部测试**

Run: `python -m pytest scripts/test_boss.py -v`
Expected: 58 passed, 0 failed（新增 4 个用例 + 原有 54 个）

- [ ] **Step 4: 提交**

```bash
git add scripts/test_boss.py
git commit -m "test(FEAT-017): 补充 get_detail 不可用 + MBA/EMBA 学历映射测试"
```

---

### Task 8: 文档同步更新

**Files:**
- Modify: `.claude/skills/platform-match/references/boss/field-mapping.md`
- Modify: `.claude/skills/platform-match/references/boss/search-mechanism.md`
- Modify: `.claude/skills/platform-match/references/boss/api-reference.md`

- [ ] **Step 1: field-mapping.md — 补充 `current_company` 映射**

将第 12 行:

```
| geekWork.name | current_title | "公司·部门·职位" → 取最后一段为职位，无分隔符时整体作为职位 |
```

改为:

```
| geekWork.name | current_company + current_title | "公司·部门·职位" → 取第一段为公司、最后一段为职位；无分隔符时整体作为公司名 |
```

- [ ] **Step 2: search-mechanism.md — 补充 `get_detail()` 暂不可用**

在"已知限制"章节末尾追加第 4 条:

```
4. **get_detail 暂不可用**: 候选人详情端点未调研，且 `page.evaluate(fetch)` 会触发反爬检测。
   需改为被动拦截方式实现（导航到候选人页面 → 拦截详情 API 响应）。
```

- [ ] **Step 3: api-reference.md — 确认详情端点已标注待调研**

第 98-100 行已有 `## 详情 API` 和 `待调研（需 securityId 访问候选人详情页）。`，无需修改。

- [ ] **Step 4: 提交**

```bash
git add .claude/skills/platform-match/references/boss/
git commit -m "docs(FEAT-017): field-mapping 补充 current_company + search-mechanism 补充 get_detail 限制"
```

---

### Task 9: 最终验证

- [ ] **Step 1: 运行全部测试**

Run: `python -m pytest scripts/test_boss.py -v`
Expected: 58 passed, 0 failed, 0 errors

- [ ] **Step 2: 检查 git 状态**

Run: `git status`
Expected: 无未提交的代码变更

- [ ] **Step 3: 检查 todo 清单完成情况**

对照 `docs/test/2026-04-23-boss-adapter-todo.md` 中的 Critical + Important 项:
- [x] C1: `map_to_schema` 补充 `current_company` → Task 1
- [x] C2: `get_detail()` 标记不可用 → Task 3
- [x] C3: `DETAIL_API_URL` 标记 TODO → Task 3
- [x] workList 单段名称解析 → Task 2
- [x] I1: 捕获数据从 git 移除 → Task 6
- [x] I4: retryable 补充 504 → Task 4
- [x] I2: search.py 变量名去遮蔽 → Task 5
- [x] search.py 异常捕获收窄 → Task 5
