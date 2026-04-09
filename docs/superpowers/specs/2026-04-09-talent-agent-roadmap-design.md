# Talent-agent 产品路线设计

> 日期：2026-04-09
> 状态：已确认
> 仓库：D:\workspace\talent-agent

## 产品定位

猎头顾问的综合 AI 助理，面向独立猎头顾问和小型猎头公司。Sourcing 是一个场景而非全部。

## MVP 范围

**Sourcing + 筛选评估**，触达沟通后续补。

## 交付形态

MVP 阶段：Claude Code 插件。后续必须做可视化界面（推广必备）。

## 策略

做深不做广。1-2 个场景做到极致。

## 架构

CC 插件 + 轻量数据层（Markdown Skill 定义 + Python 脚本管理 JSON 数据）。

保留现有 maimai-scraper 代码（已验证可用），其余架构推倒重建。

## 核心认知：两条流在 screen 阶段汇合

```
流 A（候选人建设，与JD无关）：  公域搜索 → 平台匹配 → 候选人池（信息不断丰富）
流 B（JD驱动）：               JD → 从池中筛选 → 报告
                                    ↑
                              两条流在这里汇合
```

候选人池是独立资产，不属于任何 JD。候选人与 JD 的关系只在 screen 阶段建立。

## 目录结构

```
talent-agent/
├── skills/
│   ├── public-search/              # Skill 1: 公域搜索
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── search-sources.md
│   ├── platform-match/             # Skill 2: 招聘平台匹配
│   │   ├── SKILL.md
│   │   ├── modules/                # 复用 maimai-scraper
│   │   │   ├── form-filler/
│   │   │   └── loop-orchestrator/
│   │   └── references/
│   │       └── platform-config.md
│   ├── screen/                     # Skill 3: 筛选评估
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── eval-criteria.md
│   └── report/                     # Skill 4: 推荐报告
│       ├── SKILL.md
│       └── references/
│           └── report-template.md
├── data/
│   ├── jds/                        # JD 存档
│   ├── candidates/                 # 候选人数据
│   ├── screens/                    # 筛选结果（候选人-JD关系）
│   ├── reports/                    # 推荐报告（按JD版本化）
│   ├── rules/                      # 匹配规则进化
│   └── output/                     # 阶段性md（人机协同）
└── scripts/
    └── data-manager.py             # 轻量数据管理
```

## 数据模型

### JD

```json
{
  "id": "jd-001",
  "company": "某科技公司",
  "title": "CTO",
  "department": "技术部",
  "description": "岗位职责：...\n任职要求：...\n加分项：...\n福利：...",
  "job_type": "全职",
  "experience": "10年以上",
  "min_education": "本科",
  "salary_range": "80-120万/年",
  "location": "北京",
  "created_at": "2026-04-09"
}
```

description 初期存原始文本，不做深度结构化拆分。

### Candidate（候选人）

```json
{
  "id": "cand-001",
  "name": "张三",
  "gender": "男",
  "age": 38,
  "work_years": 15,
  "education": "硕士",
  "city": "北京",
  "current_company": "某大厂",
  "current_title": "技术VP",
  "status": "在职-看机会",
  "skill_tags": ["Go", "K8s", "团队管理"],
  "expected_city": "北京/上海",
  "expected_title": "CTO/VP",
  "expected_salary": "100万+",
  "work_experience": [
    {
      "period": "2018-至今",
      "company": "某大厂",
      "title": "技术VP",
      "description": "..."
    }
  ],
  "education_experience": [
    {
      "period": "2004-2008",
      "school": "某大学",
      "major": "计算机",
      "description": "..."
    }
  ],
  "enrichment_level": "partial",
  "sources": [
    {"channel": "github", "url": "https://...", "found_at": "2026-04-09"},
    {"channel": "maimai", "url": "https://...", "found_at": "2026-04-09"}
  ],
  "created_at": "2026-04-09",
  "updated_at": "2026-04-09"
}
```

- 候选人独立于 JD，是候选人池的一部分
- enrichment_level：raw（公域基本信息）→ partial（部分补充）→ enriched（信息完整）
- sources 记录从哪些渠道发现，一个候选人可以有多个来源

### Screen（筛选结果）

```json
{
  "jd_id": "jd-001",
  "candidate_id": "cand-001",
  "score": 85,
  "gaps": ["无AI/ML背景"],
  "flags": [],
  "user_adjustments": [],
  "status": "screened"
}
```

- 只在 screen 阶段创建，是候选人与 JD 的关系记录
- status：screened / reported / passed / rejected
- user_adjustments：用户修正记录，用于规则进化

### 匹配规则进化

```json
{
  "client_profiles": {
    "某科技公司": {
      "jd_id": "jd-001",
      "learned_rules": [
        {"pattern": "大厂背景权重调低", "reason": "用户调整", "learned_at": "..."},
        {"pattern": "创业经验加分", "reason": "用户手动调整", "learned_at": "..."}
      ],
      "example_corrections": [
        {"candidate_id": "cand-005", "original_score": 60, "adjusted_score": 85, "reason": "用户调整"}
      ]
    }
  }
}
```

MVP 进化机制：
1. 每次 screen 后用户可调整评分
2. 调整记录存入 preferences.json
3. 下次为同一客户 screen 时，AI 读取历史修正作为 few-shot 上下文
4. MVP 不做模型训练，靠 prompt 中的 few-shot examples 实现"越用越准"

### 推荐报告

按 JD 版本化存储：`reports/<jd-id>/v1.md`、`reports/<jd-id>/v2.md`

每次生成报告时，拉取该 JD 下所有 screened + reported 的候选人合并对比。

## Skill 设计

### Skill 1: public-search（公域搜索）

**触发**：`/public-search <搜索画像或JD>`

**输入**：JD（从 data/jds/ 选择或直接粘贴）、团队画像、或自由关键词

**输出**：阶段性 md + candidates/*.json

**流程**：
1. 理解搜索意图（JD分析 / 团队画像 / 自由关键词）
2. AI 生成搜索策略（关键词组合 × 目标渠道）→ 输出策略 md 供用户确认
3. 用户确认后执行搜索
4. AI 从搜索结果提取候选人信息 → 输出结果 md 供用户确认
5. 用户确认后写入候选人池

**搜索技术路线**：混合模式（AI 分析 JD/画像生成搜索策略 → 按策略调用 WebSearch 等工具执行 → AI 过滤提炼结果）

**公域搜索渠道**：Google、GitHub、论文网站、个人主页等公开渠道

### Skill 2: platform-match（招聘平台匹配）

**触发**：`/platform-match --platform maimai --rules "姓名+公司" [候选人范围]`

**输入**：候选人范围 + 平台 + 匹配规则

**输出**：阶段性 md + candidates/ 更新（enrichment_level 提升）

**流程**：
1. 用户指定平台、匹配规则、候选人范围
2. 逐个执行匹配 → 输出进度 md
3. 匹配结果丰富候选人信息 → 输出结果 md 供确认
4. 用户确认后更新候选人池

**关键**：
- 匹配不基于 JD，只是丰富候选人信息
- 复用现有 maimai-scraper 的 form-filler 能力
- 后续扩展 BOSS、猎聘等平台

### Skill 3: screen（筛选评估）

**触发**：`/screen <jd-id> [--jd jd-002 ...] [--all-candidates]`

**输入**：JD(s) + 候选人池

**输出**：阶段性 md + screens/*.json + rules 更新

**流程**：
1. 读取 JD(s) + 候选人池
2. 加载历史偏好（同一客户的 learned_rules + example_corrections）
3. AI 逐个评估 → 输出评估表 md（评分 + 差距 + 红旗）
4. 用户调整评分/标记 → 记录为 learned_rules
5. 确认后写入 screens/ + 更新 preferences

**关键**：
- 支持单 JD 和批量多 JD 匹配
- 匹配规则通过用户反馈自动进化（few-shot learning）
- 批量处理是核心价值

### Skill 4: report（推荐报告）

**触发**：`/report <jd-id>`

**输入**：该 JD 下所有 screened + reported 的候选人

**输出**：reports/<jd-id>/vN.md

**流程**：
1. 拉取该 JD 下所有 screened + reported 的候选人
2. 生成推荐报告（JD 概要 + 候选人画像 + 匹配亮点 + 差距 + 横向对比表）
3. 用户编辑后保存为版本 N

**关键**：
- 支持多次生成（新候选人加入后重新生成）
- 每次生成包含历史 reported + 新 screened 候选人的完整对比

## 人机协同

每个 Skill 执行后输出阶段性 md，用户确认后才进入下一步：

```
data/output/
├── public-search-20260409-cto-team.md    # 搜索策略 + 结果摘要
├── platform-match-20260409-maimai.md     # 匹配结果 + 新增信息
├── screen-20260409-cto-v1.md             # 筛选结果 + 评分表
└── report-20260409-cto-v1.md             # 推荐报告
```

用户可在任意 md 上修改，下一步 Skill 读取修改后的版本继续。

## 代码迁移策略

保留：maimai-scraper（form-filler、loop-orchestrator、result-merger 等模块）

丢弃：core/adapters 分层、类型注册系统、Skill builder/Registry 等"架构架子"
