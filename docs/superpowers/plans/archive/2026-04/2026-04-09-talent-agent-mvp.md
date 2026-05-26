# Talent-agent MVP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重建 Talent-agent 为轻量 CC 插件，实现 Sourcing + 筛选评估 4 个核心 Skill。

**Architecture:** CC 插件（Markdown Skill 定义）+ 轻量数据层（Python 脚本管理 JSON 文件）。两条流在 screen 阶段汇合：候选人建设流（公域搜索→平台匹配）与 JD 驱动流（筛选→报告）。

**Tech Stack:** Claude Code Plugin（SKILL.md）、Python 3（data-manager.py）、JSON 文件存储、TypeScript（maimai-scraper 复用）

**Spec:** `docs/superpowers/specs/2026-04-09-talent-agent-roadmap-design.md`

---

## 文件结构总览

```
talent-agent/
├── .claude/skills/
│   ├── public-search/
│   │   ├── SKILL.md                    # Skill 1 定义
│   │   └── references/
│   │       └── search-sources.md       # 搜索渠道配置
│   ├── platform-match/
│   │   ├── SKILL.md                    # Skill 2 定义
│   │   ├── modules/                    # 从现有代码迁移
│   │   │   ├── form-filler/            # 表单填充模块
│   │   │   ├── loop-orchestrator/      # 循环编排
│   │   │   └── result-merger/          # 结果合并
│   │   └── references/
│   │       ├── platform-config.md      # 平台配置
│   │       ├── maimai-fields.md        # 脉脉字段映射
│   │       ├── form-controls-map.md    # 表单控件映射
│   │       └── anti-scraping.md        # 反爬策略
│   ├── screen/
│   │   ├── SKILL.md                    # Skill 3 定义
│   │   └── references/
│   │       └── eval-criteria.md        # 评估维度与红旗规则
│   └── report/
│       ├── SKILL.md                    # Skill 4 定义
│       └── references/
│           └── report-template.md      # 报告模板
├── data/
│   ├── jds/                            # JD 存档（每条一个 JSON）
│   ├── candidates/                     # 候选人数据（每条一个 JSON）
│   ├── screens/                        # 筛选结果（jd_id__candidate_id.json）
│   ├── reports/                        # 推荐报告（按JD版本化）
│   ├── rules/
│   │   └── preferences.json            # 匹配规则进化数据
│   └── output/                         # 阶段性 md（人机协同）
├── scripts/
│   └── data-manager.py                 # 数据 CRUD + 去重 + 查询
├── schemas/
│   ├── jd.schema.json                  # JD 数据校验
│   ├── candidate.schema.json           # 候选人数据校验
│   └── screen.schema.json              # 筛选结果数据校验
├── .claude/
│   └── settings.local.json             # CC 插件配置
└── README.md                           # 项目说明
```

---

## Phase 1: 架构重建

### Task 1: 清理旧架构

**Files:**
- Delete: `core/` (整个目录)
- Delete: `adapters/claude-code/src/` (TypeScript 源码，保留 modules/ 和 references/)
- Delete: `adapters/claude-code/dist/` (编译产物)
- Delete: `adapters/claude-code/node_modules/` (依赖)
- Delete: `adapters/claude-code/package.json`
- Delete: `adapters/claude-code/tsconfig.json`
- Delete: `adapters/claude-code/README.md`
- Delete: `biome.json`
- Delete: `pnpm-workspace.yaml`
- Delete: `tsconfig.base.json`
- Delete: `package.json` (根目录)
- Delete: `pnpm-lock.yaml`
- Delete: `test-result.png`
- Delete: `docs/plans/` (旧计划文档)
- Delete: `docs/download/`
- Keep: `adapters/claude-code/skills/maimai-scraper/modules/`
- Keep: `adapters/claude-code/skills/maimai-scraper/references/`
- Keep: `adapters/claude-code/skills/maimai-scraper/SKILL.md`
- Keep: `adapters/claude-code/data/search-template.xlsx`
- Keep: `.claude/settings.local.json`
- Keep: `.gitignore`
- Keep: `docs/superpowers/`

- [ ] **Step 1: 删除旧架构文件**

Run: 在 D:\workspace\talent-agent 下执行删除操作。保留 maimai-scraper 的 modules/、references/、SKILL.md、evals/，以及 .claude/、.gitignore、docs/superpowers/。

- [ ] **Step 2: 验证保留文件完整**

Run: `ls -R adapters/claude-code/skills/maimai-scraper/`
Expected: modules/、references/、SKILL.md、evals/、scripts/ 目录和文件存在

- [ ] **Step 3: Commit**

```
chore: remove old architecture, keep maimai-scraper
```

---

### Task 2: 创建新目录结构

**Files:**
- Create: `.claude/skills/public-search/SKILL.md` (空占位)
- Create: `.claude/skills/public-search/references/.gitkeep`
- Create: `.claude/skills/platform-match/SKILL.md` (空占位)
- Create: `.claude/skills/screen/SKILL.md` (空占位)
- Create: `.claude/skills/screen/references/.gitkeep`
- Create: `.claude/skills/report/SKILL.md` (空占位)
- Create: `.claude/skills/report/references/.gitkeep`
- Create: `data/jds/.gitkeep`
- Create: `data/candidates/.gitkeep`
- Create: `data/screens/.gitkeep`
- Create: `data/reports/.gitkeep`
- Create: `data/rules/.gitkeep`
- Create: `data/output/.gitkeep`
- Create: `schemas/.gitkeep`
- Create: `scripts/.gitkeep`

- [ ] **Step 1: 创建目录结构**

Run: `mkdir -p .claude/skills/public-search/references .claude/skills/platform-match .claude/skills/screen/references .claude/skills/report/references data/{jds,candidates,screens,reports,rules,output} schemas scripts`

- [ ] **Step 2: 迁移 maimai-scraper 到新位置**

Run:
```bash
cp -r adapters/claude-code/skills/maimai-scraper/* .claude/skills/platform-match/modules/ 2>/dev/null || true
# 如果 modules/ 已有内容，合并 references
cp -r adapters/claude-code/skills/maimai-scraper/references/* .claude/skills/platform-match/references/ 2>/dev/null || true
```

- [ ] **Step 3: 创建占位文件**

每个 SKILL.md 写入最小占位内容：
```markdown
---
name: skill-name
description: TODO
---
# Skill Name
TODO
```

- [ ] **Step 4: 清理残留的 adapters/ 目录**

Run: `rm -rf adapters/`

- [ ] **Step 5: 更新 .gitignore**

追加：
```
data/output/*.md
data/rules/preferences.json
```

- [ ] **Step 6: Commit**

```
chore: create new directory structure
```

---

### Task 3: 实现 data-manager.py

**Files:**
- Create: `scripts/data-manager.py`
- Create: `scripts/test_data_manager.py`

data-manager.py 提供以下 CLI 命令：

| 命令 | 说明 |
|------|------|
| `python scripts/data-manager.py jd create <file>` | 创建 JD |
| `python scripts/data-manager.py jd list` | 列出所有 JD |
| `python scripts/data-manager.py jd get <id>` | 获取单个 JD |
| `python scripts/data-manager.py candidate create <file>` | 创建候选人 |
| `python scripts/data-manager.py candidate list [--enrichment raw\|partial\|enriched]` | 列出候选人 |
| `python scripts/data-manager.py candidate get <id>` | 获取单个候选人 |
| `python scripts/data-manager.py candidate update <id> <file>` | 更新候选人 |
| `python scripts/data-manager.py candidate merge <id>` | 合并同人多来源信息 |
| `python scripts/data-manager.py candidate dedup` | 按姓名+公司去重 |
| `python scripts/data-manager.py screen create <jd-id> <candidate-id> <score>` | 创建筛选结果 |
| `python scripts/data-manager.py screen list <jd-id>` | 列出某 JD 的筛选结果 |
| `python scripts/data-manager.py screen update <jd-id> <candidate-id> <file>` | 更新筛选结果 |
| `python scripts/data-manager.py rules get <client>` | 获取客户偏好 |
| `python scripts/data-manager.py rules add-correction <client> <data>` | 添加修正记录 |
| `python scripts/data-manager.py validate` | 校验所有数据文件 |

- [ ] **Step 1: 写测试**

`scripts/test_data_manager.py`:
- 测试 jd create / list / get
- 测试 candidate create / list / get / update / merge / dedup
- 测试 screen create / list / update
- 测试 rules get / add-correction
- 测试 validate

- [ ] **Step 2: 运行测试确认失败**

Run: `cd D:/workspace/talent-agent && python scripts/test_data_manager.py`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 data-manager.py**

关键实现要点：
- 使用 `argparse` 解析 CLI 参数
- JSON 文件读写用 `encoding='utf-8'`
- 原子写入：先写 .tmp 再 rename
- 去重逻辑：按 `name` + `current_company` 判断同一人
- merge 逻辑：合并 sources 列表，提升 enrichment_level
- validate 逻辑：检查必需字段、枚举值、日期格式
- 所有路径相对于项目根目录

- [ ] **Step 4: 运行测试确认通过**

Run: `cd D:/workspace/talent-agent && python scripts/test_data_manager.py`
Expected: PASS

- [ ] **Step 5: Commit**

```
feat: add data-manager.py for JSON data CRUD
```

---

### Task 4: 创建数据 Schema

**Files:**
- Create: `schemas/jd.schema.json`
- Create: `schemas/candidate.schema.json`
- Create: `schemas/screen.schema.json`

- [ ] **Step 1: 创建 jd.schema.json**

必需字段：id, company, title, created_at
可选字段：department, description, job_type, experience, min_education, salary_range, location
枚举约束：job_type ∈ [全职, 兼职, 兼顾, 顾问]

- [ ] **Step 2: 创建 candidate.schema.json**

必需字段：id, name, created_at, updated_at
可选字段：gender, age, work_years, education, city, current_company, current_title, status, skill_tags[], expected_city, expected_title, expected_salary, work_experience[], education_experience[]
枚举约束：status ∈ [在职-看机会, 在职-不看, 离职-求职中, 离职-不求职], enrichment_level ∈ [raw, partial, enriched]

- [ ] **Step 3: 创建 screen.schema.json**

必需字段：jd_id, candidate_id, score, status, created_at
可选字段：gaps[], flags[], user_adjustments[]
枚举约束：status ∈ [screened, reported, passed, rejected]

- [ ] **Step 4: 在 data-manager.py validate 命令中集成 schema 校验**

使用 `jsonschema` 库校验（如果可用），否则手动校验关键字段。

- [ ] **Step 5: Commit**

```
feat: add JSON schemas for data validation
```

---

## Phase 2: Skill 实现

### Task 5: 实现 public-search Skill

**Files:**
- Modify: `.claude/skills/public-search/SKILL.md`
- Create: `.claude/skills/public-search/references/search-sources.md`

- [ ] **Step 1: 编写 search-sources.md**

定义搜索渠道列表及使用说明：
- Google（通用搜索）
- GitHub（技术人员）
- Google Scholar / 知网（学术论文）
- 个人主页 / 博客
- LinkedIn（公开资料）
- 技术社区（StackOverflow, 掘金, CSDN）

每个渠道：适用场景、搜索语法示例、信息提取要点。

- [ ] **Step 2: 编写 SKILL.md**

SKILL.md 定义完整的 Skill 行为：
```markdown
---
name: public-search
description: 公域搜索候选人——根据JD、团队画像或关键词，在公开渠道搜索候选人信息
---

# 公域搜索

## 触发
/public-search <搜索意图描述>

## 流程
1. 理解搜索意图 → 判断是 JD驱动 / 团队画像 / 自由关键词
2. 分析搜索意图 → 提取关键信息（职位、技能、行业、公司类型等）
3. 生成搜索策略 → 输出策略 md 到 data/output/
4. 等待用户确认策略
5. 按策略执行搜索（WebSearch / Jina Reader 等工具）
6. 从搜索结果提取候选人信息
7. 输出结果 md 到 data/output/（候选人列表 + 基本信息）
8. 等待用户确认
9. 调用 data-manager.py 写入候选人池

## 输出格式
阶段性 md 包含：
- 搜索策略（关键词 × 渠道矩阵）
- 搜索结果摘要（每个候选人一行：姓名、公司、职位、来源）

## 数据写入
确认后通过 data-manager.py candidate create 写入
```

- [ ] **Step 3: 手动验证**

在 CC 中执行 `/public-search 搜索字节跳动 Seedance 2.0 团队成员`，验证：
- 搜索策略 md 生成
- 搜索执行
- 结果 md 生成
- 候选人写入 data/candidates/

- [ ] **Step 4: Commit**

```
feat: implement public-search skill
```

---

### Task 6: 迁移并实现 platform-match Skill

**Files:**
- Modify: `.claude/skills/platform-match/SKILL.md`
- Create: `.claude/skills/platform-match/references/platform-config.md`
- Verify: `.claude/skills/platform-match/modules/` (maimai-scraper 代码)
- Verify: `.claude/skills/platform-match/references/maimai-fields.md`
- Verify: `.claude/skills/platform-match/references/form-controls-map.md`
- Verify: `.claude/skills/platform-match/references/anti-scraping.md`

- [ ] **Step 1: 验证 maimai-scraper 迁移完整**

Run: `ls -R .claude/skills/platform-match/modules/`
Expected: form-filler/、loop-orchestrator/、result-merger/、logger/ 等目录存在

- [ ] **Step 2: 编写 platform-config.md**

定义平台配置：
- 当前支持：maimai（脉脉）
- 后续扩展：boss（BOSS直聘）、liepin（猎聘）、linkedin
- 每个平台：搜索字段映射、匹配规则示例、反爬注意事项

- [ ] **Step 3: 编写 SKILL.md**

```markdown
---
name: platform-match
description: 招聘平台匹配——在脉脉等招聘平台上搜索候选人，丰富候选人信息
---

# 招聘平台匹配

## 触发
/platform-match --platform <平台> --rules <匹配规则> [--candidates <范围>]

## 参数
- --platform: maimai / boss / liepin（默认 maimai）
- --rules: 匹配规则，如 "姓名+公司"、"职位+城市"
- --candidates: 候选人范围（默认全部 raw/partial）

## 流程
1. 读取候选人列表（data-manager.py candidate list）
2. 用户确认匹配规则和平台
3. 逐个在平台搜索 → 输出进度 md
4. 找到匹配 → 补充候选人信息（联系方式、完整经历等）
5. 输出匹配结果 md（新增/更新的信息摘要）
6. 用户确认后更新候选人池（enrichment_level 提升）

## 脉脉搜索
使用 maimai-scraper modules 执行：
- form-filler：自动填写搜索表单
- loop-orchestrator：控制搜索循环
- result-merger：合并搜索结果
```

- [ ] **Step 4: 手动验证**

在 CC 中执行 `/platform-match --platform maimai --rules "姓名+公司"`，验证：
- 候选人列表读取
- 脉脉搜索执行
- 结果 md 生成
- 候选人信息更新

- [ ] **Step 5: Commit**

```
feat: implement platform-match skill with maimai-scraper
```

---

### Task 7: 实现 screen Skill

**Files:**
- Modify: `.claude/skills/screen/SKILL.md`
- Create: `.claude/skills/screen/references/eval-criteria.md`

- [ ] **Step 1: 编写 eval-criteria.md**

定义评估维度和红旗规则：

评估维度：
- 岗位匹配度（职责对口程度）
- 技能覆盖率（JD 要求技能的满足比例）
- 经验深度（工作年限、管理经验等）
- 行业背景（相关行业经验）
- 稳定性（跳槽频率、空窗期）

红旗规则：
- 3 年内跳槽 3+ 次 → 高流动性风险
- 空窗期超过 6 个月 → 需关注原因
- 工作经历时间重叠 → 可能虚报
- 学历与工作年限不匹配 → 需验证

- [ ] **Step 2: 编写 SKILL.md**

```markdown
---
name: screen
description: 候选人筛选评估——将候选人池与JD匹配，打分排序，支持规则进化
---

# 筛选评估

## 触发
/screen <jd-id> [--jd <jd-id-2> ...] [--all]

## 参数
- jd-id: 目标 JD（从 data/jds/ 读取）
- --jd: 额外 JD（批量匹配）
- --all: 对候选人池全部评估

## 流程
1. 读取 JD(s)
2. 加载客户偏好（data-manager.py rules get）
3. 读取候选人池（data-manager.py candidate list）
4. 逐个评估：
   - 对标 eval-criteria.md 中的维度
   - 参考 learned_rules 和 example_corrections
   - 输出：score、gaps、flags
5. 输出评估表 md（按分数排序，含差距和红旗）
6. 用户调整评分/标记
7. 记录调整 → data-manager.py rules add-correction
8. 确认后写入 screens/

## 评估输出格式
| 排名 | 姓名 | 当前职位 | 评分 | 关键差距 | 红旗 |
|------|------|---------|------|---------|------|
| 1 | 张三 | 技术VP | 85 | 无AI/ML背景 | 无 |
| 2 | 李四 | CTO | 78 | 创业经验不足 | 3年跳3次 |
```

- [ ] **Step 3: 手动验证**

准备测试数据（1个JD + 3-5个候选人），在 CC 中执行 `/screen jd-001`，验证：
- 评估表 md 生成
- 评分和差距合理
- 用户调整后 rules 更新
- screens/ 写入

- [ ] **Step 4: Commit**

```
feat: implement screen skill with rule evolution
```

---

### Task 8: 实现 report Skill

**Files:**
- Modify: `.claude/skills/report/SKILL.md`
- Create: `.claude/skills/report/references/report-template.md`

- [ ] **Step 1: 编写 report-template.md**

定义推荐报告模板结构：

```markdown
# <公司> - <职位> 推荐报告

> 报告日期：<日期>
> 候选人数量：<N> 人
> 报告版本：v<N>

## 职位概要
（从 JD 提取：公司、职位、核心要求、薪资范围）

## 推荐候选人

### 1. <姓名> — <当前职位> @ <当前公司>
- **匹配度：<N> 分**
- **核心优势**：...
- **与JD差距**：...
- **风险评估**：...
- **工作经历摘要**：...

### 2. ...

## 横向对比
| 维度 | 候选人1 | 候选人2 | 候选人3 |
|------|--------|--------|--------|
| 匹配度 | 85 | 78 | 72 |
| 经验年限 | 15年 | 12年 | 10年 |
| 核心技能 | Go, K8s | Java, Spring | Python, ML |
| 红旗 | 无 | 3年跳3次 | 空窗期8月 |

## 备注
（猎头顾问补充说明）
```

- [ ] **Step 2: 编写 SKILL.md**

```markdown
---
name: report
description: 生成推荐报告——将筛选后的候选人整理为面向客户的推荐文档
---

# 推荐报告

## 触发
/report <jd-id>

## 流程
1. 读取 JD
2. 拉取该 JD 下所有 screened + reported 的候选人
3. 生成推荐报告（按 report-template.md 模板）
4. 输出到 data/reports/<jd-id>/vN.md
5. 用户编辑确认

## 版本管理
- 自动检测已有版本号（v1, v2, ...），新版本 = max + 1
- 每次生成包含所有 screened + reported 候选人
- 历史版本保留，不覆盖
```

- [ ] **Step 3: 手动验证**

使用 Task 7 的测试数据，在 CC 中执行 `/report jd-001`，验证：
- 报告生成
- 横向对比表
- 版本号自动递增
- 再次执行生成 v2

- [ ] **Step 4: Commit**

```
feat: implement report skill
```

---

## Phase 3: 收尾

### Task 9: 更新 README 和项目配置

**Files:**
- Modify: `README.md`
- Create: `.claude/settings.local.json`（如需要更新）

- [ ] **Step 1: 重写 README.md**

包含：产品定位、4 个 Skill 说明、快速开始、目录结构、数据流图。

- [ ] **Step 2: 更新 .claude/settings.local.json**

确保 CC 插件配置正确，skills 目录指向新位置。

- [ ] **Step 3: 最终验证**

在 CC 中依次执行完整流程：
1. 创建一个测试 JD
2. `/public-search` 搜索几个测试候选人
3. `/platform-match` 匹配
4. `/screen` 筛选
5. `/report` 生成报告

- [ ] **Step 4: Commit**

```
docs: update README and project config for MVP
```
