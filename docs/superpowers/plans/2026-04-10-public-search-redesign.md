# public-search Skill 完全重写 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 public-search 从单次搜索工具重写为策略驱动的协作搜索系统（引导入口 → 协作策略 → 执行搜索 → 三层反馈 → 迭代循环 → 策略沉淀）。

**Architecture:** 完全重写 SKILL.md，新增搜索策略存储目录和岗位感知渠道推荐表。Token Tracker 作为独立模块预留接口，OTEL 部署为前置任务。

**Tech Stack:** Claude Code Skill（Markdown prompt）、Python（data-manager）、JSON（数据格式）、Git（版本控制）

**Spec:** `docs/superpowers/specs/2026-04-10-public-search-redesign-design.md`

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `skills/public-search/SKILL.md` | Skill 主文件（完整流程定义） | 完全重写 |
| `skills/public-search/references/search-sources.md` | 渠道参考 + 岗位类型渠道推荐表 | 更新 |
| `skills/public-search/references/strategy-template.md` | 策略文件模板（Instance/Template 格式定义） | 新建 |
| `data/search-strategies/instances/.gitkeep` | 单次策略目录 | 新建 |
| `data/search-strategies/templates/.gitkeep` | 策略模板目录 | 新建 |
| `data/search-strategies/universal-rules.json` | 通用规则 | 新建 |

---

## Task 1: 创建目录结构和初始文件

**Files:**
- Create: `data/search-strategies/instances/.gitkeep`
- Create: `data/search-strategies/templates/.gitkeep`
- Create: `data/search-strategies/universal-rules.json`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p data/search-strategies/instances
mkdir -p data/search-strategies/templates
touch data/search-strategies/instances/.gitkeep
touch data/search-strategies/templates/.gitkeep
```

- [ ] **Step 2: 创建 universal-rules.json 初始文件**

```json
{
  "rules": [],
  "metadata": {
    "created_at": "2026-04-10",
    "last_updated": "2026-04-10"
  }
}
```

写入 `data/search-strategies/universal-rules.json`。

- [ ] **Step 3: Commit**

```bash
git add data/search-strategies/
git commit -m "chore: 创建搜索策略存储目录结构"
```

---

## Task 2: 创建策略文件模板参考

**Files:**
- Create: `skills/public-search/references/strategy-template.md`

- [ ] **Step 1: 创建 Instance 策略模板**

写入 `skills/public-search/references/strategy-template.md`，包含：
- Instance 策略文件的完整格式定义（元信息、目标画像、关键词矩阵、渠道计划、执行记录、累计归因）
- Template 策略文件的完整格式定义（共同特征、推荐渠道、推荐关键词模式、排除渠道、统计数据）
- 放弃记录的格式定义
- 所有字段说明

参考 spec 第 3.4 节的格式定义和第 7.2 节的模板格式。

- [ ] **Step 2: Commit**

```bash
git add skills/public-search/references/strategy-template.md
git commit -m "docs: 添加搜索策略文件格式模板参考"
```

---

## Task 3: 更新渠道参考文档

**Files:**
- Modify: `skills/public-search/references/search-sources.md`

- [ ] **Step 1: 在 search-sources.md 末尾追加岗位感知渠道推荐表**

追加内容参考 spec 第 8.1 节：

```markdown
## 岗位类型渠道推荐

| 岗位类型 | 首选渠道 | 辅助渠道 | 排除渠道 |
|---------|---------|---------|---------|
| 技术开发 | GitHub, Google | 技术社区, LinkedIn | Scholar |
| 产品经理 | LinkedIn, Google | 行业媒体, 即刻 | GitHub, Scholar |
| 设计师 | Dribbble, Behance | 小红书, LinkedIn | GitHub, Scholar |
| 管理/高管 | LinkedIn, 行业媒体 | Google | GitHub |
| 学术/研究 | Scholar, 知网 | Google, GitHub | — |

### 使用说明

1. **岗位类型判断**：从 JD 职位名称中提取关键词，匹配上表
2. **模糊情况**：默认匹配最接近的类型，用户可手动覆盖
3. **覆盖记录**：记录在策略文件的元信息中
4. **仅作推荐**：用户可随时忽略推荐，使用自定义渠道组合
```

- [ ] **Step 2: Commit**

```bash
git add skills/public-search/references/search-sources.md
git commit -m "docs: 增加岗位类型渠道推荐表"
```

---

## Task 4: 重写 SKILL.md — 触发入口与引导模式

**Files:**
- Modify: `skills/public-search/SKILL.md`

- [ ] **Step 1: 重写 SKILL.md 的 frontmatter 和触发部分**

完全替换文件内容，写入新的 frontmatter、触发方式、入口判断逻辑、引导模式（含退出机制）。参考 spec 第 2 节。

关键点：
- 触发方式保持 `/public-search [输入]` 格式
- 三种入口路径清晰定义
- 引导模式的退出机制（「取消」「算了」或空消息）

- [ ] **Step 2: Commit**

```bash
git add skills/public-search/SKILL.md
git commit -m "feat(public-search): 重写触发入口与引导模式"
```

---

## Task 5: 重写 SKILL.md — 协作策略生成

**Files:**
- Modify: `skills/public-search/SKILL.md`

- [ ] **Step 1: 追加协作策略生成流程**

在 SKILL.md 中追加 JD 驱动路径和策略驱动路径的完整流程定义。参考 spec 第 3 节。

关键点：
- JD 驱动：读取 JD → 匹配策略模板 → 应用 Universal 规则 → 生成策略 → 用户审查 → 确认
- 策略驱动：解析策略 → AI 审查 → 优化建议 → 定稿 → 确认
- 策略文件格式引用 `references/strategy-template.md`
- 跨会话恢复逻辑（最后活跃时间 + 轮次号 + 并发控制）

- [ ] **Step 2: Commit**

```bash
git add skills/public-search/SKILL.md
git commit -m "feat(public-search): 重写协作策略生成流程"
```

---

## Task 6: 重写 SKILL.md — 执行搜索

**Files:**
- Modify: `skills/public-search/SKILL.md`

- [ ] **Step 1: 追加执行搜索流程**

追加执行逻辑。参考 spec 第 4 节。

关键点：
- 按关键词矩阵逐条执行
- 每条独立记录（搜索量、候选人数、噪音数）
- Token Tracker 集成：定义读取接口，降级方案（显示「未配置」）
- 候选人去重复用 `data-manager.py candidate dedup`
- 候选人写入流程（临时 JSON → data-manager create → 清理）

- [ ] **Step 2: Commit**

```bash
git add skills/public-search/SKILL.md
git commit -m "feat(public-search): 重写执行搜索流程（含 Token Tracker 接口）"
```

---

## Task 7: 重写 SKILL.md — 搜索反馈与迭代循环

**Files:**
- Modify: `skills/public-search/SKILL.md`

- [ ] **Step 1: 追加三层反馈结构**

追加归因表、覆盖缺口、AI 反思 + 成本分析的完整输出格式。参考 spec 第 5 节。

关键点：
- 归因表包含 Token 消耗和成本/候选人列
- Token 为 0 时显示「未配置」
- AI 反思不给结论，给选项让用户选择

- [ ] **Step 2: 追加迭代循环**

追加迭代循环的用户选择和每轮操作。参考 spec 第 6 节。

关键点：
- 四种用户选择（采纳/自提优化/满意/放弃）
- 每轮更新：执行记录追加、关键词状态更新、累计归因重算、最后活跃时间更新
- 放弃记录格式

- [ ] **Step 3: Commit**

```bash
git add skills/public-search/SKILL.md
git commit -m "feat(public-search): 重写搜索反馈与迭代循环"
```

---

## Task 8: 重写 SKILL.md — 策略沉淀

**Files:**
- Modify: `skills/public-search/SKILL.md`

- [ ] **Step 1: 追加策略沉淀流程**

追加 Instance → 策略模板 → Universal 规则的完整流程。参考 spec 第 7 节。

关键点：
- 「同类搜索」定义：JD 全文相似度 > 0.6（阈值可调）
- 策略模板创建触发（N=3 次）和更新触发
- 策略模板匹配逻辑（与「同类判定」同一套）
- Universal 规则提炼触发和生命周期管理
- 用户可控原则
- 模板格式引用 `references/strategy-template.md`

- [ ] **Step 2: 追加岗位感知和 Token Tracker 部分**

追加岗位类型判断逻辑（引用 `references/search-sources.md` 中的渠道推荐表）。追加 Token Tracker 前置任务说明。

- [ ] **Step 3: Commit**

```bash
git add skills/public-search/SKILL.md
git commit -m "feat(public-search): 重写策略沉淀与岗位感知"
```

---

## Task 9: 端到端验证

**Files:**
- No new files — 验证现有实现

- [ ] **Step 1: 验证引导模式**

触发 `/public-search`（无参数），确认输出引导菜单。输入「取消」，确认正常退出。

- [ ] **Step 2: 验证 JD 驱动路径**

用之前创建的测试 JD（`jd-20260410-alibaba-cloud-ai-agent-pm`）触发 `/public-search jd-20260410-alibaba-cloud-ai-agent-pm`，确认：
- 读取 JD 成功
- 生成策略文件到 `data/search-strategies/instances/`
- 策略包含关键词矩阵、渠道计划、目标画像
- 等待用户确认（不自动执行搜索）

- [ ] **Step 3: 验证策略文件格式**

检查生成的策略文件是否符合 `references/strategy-template.md` 中定义的格式。

- [ ] **Step 4: 验证跨会话恢复**

在同一策略文件基础上，新会话触发 `/public-search` 并给出策略文件路径，确认能正确读取并提示继续。

- [ ] **Step 5: 验证数据目录结构**

确认 `data/search-strategies/` 目录结构完整：
```
data/search-strategies/
├── instances/          # 至少 1 个策略文件
├── templates/          # 空目录（首次使用后才有）
└── universal-rules.json  # 初始空规则
```

- [ ] **Step 6: Commit 验证结果**

```bash
git add -A
git commit -m "test: public-search 重写端到端验证通过"
```
