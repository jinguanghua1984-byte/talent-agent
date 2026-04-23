# Boss 直聘 Skill 主流程集成 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Boss 直聘接入 platform-match skill 的全部三种模式，使 SKILL.md 成为多平台流程说明书。

**Architecture:** 纯文档改造，底层 Python 脚本零改动。SKILL.md 中将硬编码 `maimai` 替换为动态 `<platform>` 变量，新增 `--platform` 参数路由和平台选择步骤。新建 2 个 Boss reference 文档（字段映射、搜索机制）。

**Tech Stack:** Markdown 文档

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `.claude/skills/platform-match/references/boss/field-mapping.md` | 新建 | Boss API → candidate.schema 字段映射表 |
| `.claude/skills/platform-match/references/boss/search-mechanism.md` | 新建 | Boss 被动拦截搜索机制 + 与脉脉的差异 |
| `.claude/skills/platform-match/SKILL.md` | 修改 | 参数路由、前置检查、资源索引、三种模式泛化 |

---

### Task 1: 创建 Boss 字段映射文档

**Files:**
- Create: `.claude/skills/platform-match/references/boss/field-mapping.md`

- [ ] **Step 1: 创建 field-mapping.md**

参照 `.claude/skills/platform-match/references/maimai/field-mapping.md` 的格式，从 `.claude/skills/platform-match/scripts/adapters/boss.py` 的 `map_to_schema()` 方法（第 180-273 行）提取映射关系。

文档结构：

```markdown
# Boss 直聘 API 字段 → candidate.schema 映射表

> 来源: `scripts/adapters/boss.py` `map_to_schema()` (2026-04-20 校准)

## 基本信息映射

| Boss API 字段 (geekCard) | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| name | name | 直接映射 |
| gender | gender | 1→"男", 2→"女", 其他→跳过 |
| city | city | 直接映射 |
| geekWork.name | current_title | "公司·部门·职位" → 取最后一段为职位，无分隔符时整体作为职位 |
| highestDegreeName | education | 通过 EDUCATION_MAP 映射（"MBA"/"EMBA"→"硕士"） |
| workYear | work_years | "4年" → 提取数字 |
| ageDesc | age | "27岁" → 提取数字 |
| activeDesc | active_state | 直接映射 |
| salary | expected_salary | 直接映射 |

## 经历映射

| Boss API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| workList[].name | work_experience[].company + title | "公司·职位" → 按·分割，首段为公司，末段为职位 |
| workList[].dateRange | work_experience[].period | "2024-2026" → "2024-06 - 2026-06"；含"至今" → "start - 至今" |
| geekEdu.name | education_experience[].school + major | "国家·学校·专业" → 按·分割，第二段为学校，第三段为专业 |

## 标签映射

| Boss API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| labelMatchList[].markWord | skill_tags | 提取所有 markWord 为列表 |

## 来源映射

| Boss API 字段 | sources[] 字段 | 转换逻辑 |
|---|---|---|
| encryptGeekId | platform_id | 直接映射 |
| securityId | security_id | 直接映射 |
| — | url | 构造 `https://www.zhipin.com/web/geek/{encryptGeekId}` |
| — | channel | 固定 "boss" |

## 学历枚举映射

| Boss 原始值 | candidate education |
|---|---|
| 大专 | 大专 |
| 本科 | 本科 |
| 硕士 | 硕士 |
| 博士 | 博士 |
| MBA | 硕士 |
| EMBA | 硕士 |
```

- [ ] **Step 2: 验证内容准确性**

对照 `boss.py` 第 45-54 行的 `EDUCATION_MAP`、第 57-64 行的 `_parse_work_years`、第 90-119 行的 `_parse_geek_work` 和 `_parse_geek_edu`，确认映射表与代码一致。

- [ ] **Step 3: 提交**

```bash
git add .claude/skills/platform-match/references/boss/field-mapping.md
git commit -m "docs(FEAT-017): 添加 Boss 直聘字段映射文档"
```

---

### Task 2: 创建 Boss 搜索机制文档

**Files:**
- Create: `.claude/skills/platform-match/references/boss/search-mechanism.md`

- [ ] **Step 1: 创建 search-mechanism.md**

内容覆盖：

```markdown
# Boss 直聘搜索机制

## 概述

Boss 直聘采用**被动网络拦截**方式获取搜索结果，与脉脉的主动 API 调用完全不同。

核心差异：不在代码中发起 fetch 请求，而是模拟用户在搜索框输入关键词，
通过 `page.on('response')` 拦截浏览器发出的 geeks.json 响应。

## 前提条件

1. Chrome 已通过 `--remote-debugging-port=9222` 启动
2. **已有一个 Boss 直聘页面打开且处于登录状态**（zhipin.com）
3. 页面需处于人才搜索页（/web/frame/search/ iframe 可用）

**不能 `context.new_page()`** — 会触发 browser-check.min.js 导致强制登出。
**不能 `page.evaluate(fetch)`** — 会触发反爬检测导致强制登出（code: 7）。

## 搜索流程

### 1. 定位搜索 iframe

搜索页在 iframe 中加载，路径包含 `/web/frame/search/`。

```python
for frame in page.frames:
    if "/web/frame/search/" in frame.url and "about:" not in frame.url:
        search_frame = frame
```

超时: 15 次轮询，每次 0.5s（共 7.5s）。

### 2. 填入关键词

定位 `.input-text` 输入框 → click → 清空 → type(query, delay=50)。

### 3. 触发搜索

优先点击 `.icon-search` 图标，找不到时回退到 Enter 键。

### 4. 拦截响应

在 **page 级别**（不是 frame 级别）注册 response listener：
- 过滤 URL 包含 `geeks.json` 且不含 `t.zhipin.com`
- 校验 `page` 和 `keywords` 参数匹配
- 超时: 20 次轮询，每次 0.5s（共 10s）

### 5. 解析结果

响应 body 结构: `{ zpData: { geeks: [{ geekCard: {...} }], totalCount, hasMore } }`

取 `geeks[].geekCard` 作为搜索结果项。

## 分页

与脉脉相同，通过 page 参数控制分页。
每次翻页重新触发搜索并拦截对应 page 的响应。

## 与脉脉的对比

| 维度 | 脉脉 | Boss 直聘 |
|------|------|----------|
| 搜索方式 | 主动 API 调用 (page.evaluate(fetch)) | 被动拦截 (page.on('response')) |
| 页面操作 | 创建新页面 → goto → fetch | 复用已有页面 → iframe 内输入 |
| 反爬风险 | 低（自有 API） | 高（不能 new_page / fetch） |
| 前提条件 | Chrome 打开任意页面 | Chrome 打开 zhipin.com 且已登录 |
| 结果位置 | API 响应直接返回 | geekCard 嵌套在 geeks 数组中 |
| 筛选参数 | 在 fetch URL 中拼接 | 在搜索页 UI 中设置（当前未实现） |

## 已知限制

1. **session.py verify 风险**: `session.py verify --mode cdp` 会 `new_page()` + `goto()`，
   可能触发 Boss 反检测。Boss 的前置检查应优先检查 Chrome 是否已有 zhipin.com 页面，
   而非主动访问。
2. **筛选参数未暴露**: search.py CLI 未暴露 city/education/work_years 参数，
   Boss 的 build_search_params() 虽然支持这些字段但当前未被使用。
3. **分页翻页**: 当前每次翻页需要重新填入关键词并点击搜索，效率较低。
```

- [ ] **Step 2: 验证与 api-reference.md 的一致性**

对照 `references/boss/api-reference.md` 第 72-96 行的"搜索触发方式"和"反爬检测"章节，确保内容一致且不重复。

- [ ] **Step 3: 提交**

```bash
git add .claude/skills/platform-match/references/boss/search-mechanism.md
git commit -m "docs(FEAT-017): 添加 Boss 直聘搜索机制文档"
```

---

### Task 3: 更新 SKILL.md — 描述、参数路由、前置检查、资源索引

**Files:**
- Modify: `.claude/skills/platform-match/SKILL.md` (第 1-43 行)

- [ ] **Step 1: 更新 SKILL.md frontmatter 描述**

将第 3 行的 description 从:
```
description: "招聘平台候选人搜索与信息丰富。在脉脉等招聘平台上搜索候选人，丰富候选人库信息，或根据 JD/条件搜索目标人选。触发词: 匹配候选人、搜索脉脉、平台找人、丰富候选人、/platform-match"
```
改为:
```
description: "招聘平台候选人搜索与信息丰富。在脉脉、Boss直聘等招聘平台上搜索候选人，丰富候选人库信息，或根据 JD/条件搜索目标人选。触发词: 匹配候选人、搜索脉脉、搜索Boss、平台找人、丰富候选人、/platform-match"
```

- [ ] **Step 2: 更新参数路由**

在第 16 行后新增 `--platform` 参数说明:

```
/platform-match                              → 对话式（模式 3）
/platform-match --candidates <filter>        → 候选丰富（模式 1）
/platform-match --candidates batch:<batch-id> → 候选丰富（模式 1，从批次读取）
/platform-match --jd <id|file>               → JD 驱动（模式 2）
/platform-match --headless                   → 降级模式（附加在任意模式上）
/platform-match --platform <name>            → 平台选择（附加在任意模式上）
```

新增说明段:

```
平台选择: `--platform` 参数。支持: maimai（脉脉）、boss（Boss直聘）。
- 传入 --platform → 直接使用，不询问
- 不传 → 交互式询问用户选择平台
- 模式 3（对话式）始终在搜索前确认平台
```

- [ ] **Step 3: 更新前置检查**

将第 26 行的:
```
   - 默认模式: `python scripts/session.py status`
   - 降级模式: `python scripts/session.py verify --platform maimai --mode standalone`
```
改为:
```
   - 默认模式: `python scripts/session.py status`
   - 降级模式: `python scripts/session.py verify --platform <platform> --mode standalone`
```

将第 28-29 行的提示文案改为平台分支:
```
   - 如果 session 不可用:
     - maimai → 提示用户: "请先启动 Chrome: `chrome --remote-debugging-port=9222`"
     - boss → 提示用户: "请确保 Chrome 已打开 Boss 直聘页面（需已有登录态）"
```

新增 boss 前置检查注意事项:
```
   - boss 特殊: session.py verify --mode cdp 会 new_page() 触发反检测。
     应优先检查 Chrome 是否已有 zhipin.com 页面，而非主动 verify。
     参考 `references/boss/search-mechanism.md` 已知限制。
```

- [ ] **Step 4: 更新资源索引表**

在第 35 行资源索引表中，脉脉文档后新增 Boss 文档:

```
| 脉脉 API 规格 | `references/maimai/api-reference.md` |
| 脉脉字段映射 | `references/maimai/field-mapping.md` |
| 脉脉反检测策略 | `references/maimai/anti-detect.md` |
| Boss API 规格 | `references/boss/api-reference.md` |
| Boss 字段映射 | `references/boss/field-mapping.md` |
| Boss 搜索机制 | `references/boss/search-mechanism.md` |
| 匹配策略 | `references/matching-strategy.md` |
```

- [ ] **Step 5: 提交**

```bash
git add .claude/skills/platform-match/SKILL.md
git commit -m "docs(FEAT-017): SKILL.md 参数路由、前置检查、资源索引支持多平台"
```

---

### Task 4: 更新 SKILL.md — 模式 1（候选丰富）

**Files:**
- Modify: `.claude/skills/platform-match/SKILL.md` (第 45-129 行，模式 1)

- [ ] **Step 1: 步骤 2.2 — 平台关联检查**

将第 77-79 行:
```
    - 在 candidates sources[] 中查找 channel="maimai" 的记录
    - 已关联（同记录）→ 跳过搜索，提示"已有脉脉数据"
    - 已关联（其他记录）→ 提示可能重复，建议去重
```
改为:
```
    - 在 candidates sources[] 中查找 channel="<platform>" 的记录
    - 已关联（同记录）→ 跳过搜索，提示"已有{平台中文名}数据"
    - 已关联（其他记录）→ 提示可能重复，建议去重
```

新增平台中文名映射说明（在步骤 2 之前或 2.2 注释中）:
```
平台中文名映射: maimai→脉脉, boss→Boss直聘
```

- [ ] **Step 2: 步骤 2.3 — 调用搜索**

将第 84 行:
```bash
    python scripts/search.py search --platform maimai --query "<query>" --pages 1
```
改为:
```bash
    python scripts/search.py search --platform <platform> --query "<query>" --pages 1
```

- [ ] **Step 3: 步骤 2.6 — 丰富写入**

将第 112 行:
```bash
    python scripts/enrich.py map --platform maimai --api-data '<json>'
```
改为:
```bash
    python scripts/enrich.py map --platform <platform> --api-data '<json>'
```

- [ ] **Step 4: 步骤 2.7 — 速率检查**

将第 121 行:
```bash
    python scripts/rate_limiter.py tick --platform maimai [--headless]
```
改为:
```bash
    python scripts/rate_limiter.py tick --platform <platform> [--headless]
```

- [ ] **Step 5: 提交**

```bash
git add .claude/skills/platform-match/SKILL.md
git commit -m "docs(FEAT-017): SKILL.md 模式 1 支持多平台"
```

---

### Task 5: 更新 SKILL.md — 模式 2（JD 驱动）和模式 3（对话式）

**Files:**
- Modify: `.claude/skills/platform-match/SKILL.md` (第 131-217 行，模式 2 + 模式 3)

- [ ] **Step 1: 模式 2 — 新增平台选择步骤**

在"步骤 1: 读取 JD 与搜索策略"之前，插入平台选择步骤:

```
### 步骤 0: 选择平台

如果 `--platform` 已传入 → 直接使用。
未传入 → 交互式询问用户选择平台（支持: maimai、boss）。
```

- [ ] **Step 2: 模式 2 — 步骤 2 搜索命令**

将第 156 行:
```bash
  python scripts/search.py search --platform maimai --query "<query>" --pages 3
```
改为:
```bash
  python scripts/search.py search --platform <platform> --query "<query>" --pages 3
```

- [ ] **Step 3: 模式 3 — 新增步骤 1 平台选择**

在当前"步骤 1: 理解搜索需求"之前插入新的步骤 1:

```
### 步骤 1: 选择平台

如果 `--platform` 已传入 → 直接使用。
未传入 → 交互式询问用户选择平台（支持: maimai、boss）。
```

原步骤 1-4 编号顺移为 2-5。

- [ ] **Step 4: 模式 3 — 步骤 3 搜索命令**

将第 203 行:
```bash
python scripts/search.py search --platform maimai --query "<query>" --pages 3
```
改为:
```bash
python scripts/search.py search --platform <platform> --query "<query>" --pages 3
```

- [ ] **Step 5: 提交**

```bash
git add .claude/skills/platform-match/SKILL.md
git commit -m "docs(FEAT-017): SKILL.md 模式 2/3 支持多平台"
```

---

### Task 6: 最终验证

- [ ] **Step 1: 全文搜索残留硬编码**

在 SKILL.md 中搜索 `maimai`，确认只出现在:
- 资源索引表（作为平台名称的合法出现）
- 平台选择说明（作为选项示例）
- 降级模式的示例命令中

不应出现在命令模板、流程描述中作为硬编码平台名。

- [ ] **Step 2: 检查新增文档引用路径**

确认 SKILL.md 资源索引表中的路径与实际文件路径一致:
- `references/boss/api-reference.md` ✓ 已存在
- `references/boss/field-mapping.md` ✓ Task 1 创建
- `references/boss/search-mechanism.md` ✓ Task 2 创建

- [ ] **Step 3: 整体提交（如有遗漏修复）**

```bash
git add -A
git commit -m "docs(FEAT-017): Boss 直聘 Skill 主流程集成完成"
```
