# Pipeline 与现有 Skill 协同分析

调研日期: 2026-05-01
触发场景: Pipeline 首次运行成功后，评估与现有 skill 体系的集成方式

## 现有 Skill 架构

### 数据流全景

```
/platform-match 搜索
    ↓
data/boss-search/search-{keyword}.json  ← pipeline 直接消费
    ↓
    ├──→ [旧路径] score_candidates.py 硬编码评分 → scored-企业级agent.json (legacy)
    ├──→ [新路径] score_pipeline.py JD驱动评分 → data/output/score-report-*.md
    ↓
/screen --jd <id>  ← 单候选人深度评估 (交互式, Claude 对话)
    ↓                    读取 data/candidates/
    ↓
/report <jd-id>   ← 面向客户的推荐文档
                    读取 data/screens/
    ↓
/public-search       ← 公域搜索补充候选池
    ↓
data/candidates/     ← 所有候选人归档 (data-manager.py CRUD)
```

### 各 Skill 定位

| Skill | 定位 | 输入 | 输出 | 依赖 |
|-------|------|------|------|------|
| `/platform-match` | 候选人发现 | JD/关键词/候选人列表 | `data/{platform}-search/`, `data/candidates/` | data-manager |
| `score_pipeline` | **批量离线筛选** | JD + 搜索结果文件 | `data/cache/pipeline/`, `data/output/` | platform-match 搜索结果 |
| `/screen` | 单人深度评估 | JD ID + 候选人 | `data/screens/`, `data/output/screen-*.md` | data-manager |
| `/report` | 客户交付文档 | JD ID | `data/reports/<jd-id>/v<N>.md` | screen 结果 |
| `/public-search` | 公域搜索补充 | JD 文本 | `data/candidates/`, `data/batches/` | data-manager |

### 评分维度对比

#### score_pipeline (统一维度定义)

| 维度 | 权重 | 来源 |
|------|------|------|
| 岗位匹配度 | 30 | rules/scoring-config.json |
| 技能覆盖率 | 25 | rules/scoring-config.json |
| 经验深度 | 20 | rules/scoring-config.json |
| 行业背景 | 15 | rules/scoring-config.json |
| 稳定性 | 10 | rules/scoring-config.json |

#### /screen skill (eval-criteria.md)

| 维度 | 权重 | 说明 |
|------|------|------|
| 岗位匹配度 | 30% | 职责对口、管理层级、行业对口 |
| 技能覆盖率 | 25% | 必备/优先技能满足比例 |
| 经验深度 | 20% | 工作年限、领域经验、管理经验 |
| 行业背景 | 15% | 同行业、竞争对手、行业认知 |
| 稳定性 | 10% | 平均在职时长、空窗期、跳槽频率 |

#### /platform-match (score_candidates.py, legacy)

| 维度 | 权重 | 说明 |
|------|------|------|
| 职位匹配度 | 30 | lidTag + 描述关键词 |
| 技能重叠度 | 25 | 技能标签命中 |
| 行业经验 | 20 | 名企/AI 公司 |
| 学历背景 | 15 | 学位 + 名校 |
| 意向匹配 | 10 | 年限 + 薪资 + 活跃度 |

**一致性结论:**
- 三套维度基本对齐 (5 维度, 权重接近)
- pipeline 的维度定义最规范 (集中管理在 scoring-config.json)
- `/screen` 和 pipeline 维度已一致, 但命名略有差异 (技能覆盖率 vs 技能重叠度)
- `/platform-match` 的 "学历背景" 和 "意向匹配" 与另外两套不同 (这是 legacy 脚本, 已标记废弃)

## 协同方案

### 方案 A: 最小改动 (文档对齐)

只更新 `/screen` SKILL.md, 提到 pipeline 存在, 文档说明工作流顺序。两边独立运行, 人工衔接。

**改动:**
- `/screen/SKILL.md` 增加 "前置步骤: 可先用 score_pipeline 批量筛选" 章节
- 评分维度引用统一到 `rules/scoring-config.json`

**优点:** 零代码风险, 立即生效
**缺点:** 人工衔接, 数据不互通

### 方案 B: 数据互通

pipeline 评分结果自动写入 `data/screens/` 格式 (通过 data-manager.py), 让 `/screen` 和 `/report` 能直接消费 pipeline 输出。

**改动:**
- `score_pipeline.py` 增加 `--save-to-screens` 选项, 评分结果通过 data-manager 写入
- `/screen` 增加 `--use-pipeline-cache` 选项, 读取 pipeline 缓存作为预评分
- `/report` 支持从 pipeline 报告生成客户文档

**优点:** 数据贯通, 减少重复工作
**缺点:** 需要修改 data-manager.py 的 screen schema, 兼容性风险

### 方案 C: 统一入口

在 `/platform-match` 完成搜索后自动触发 pipeline 评分, 一键从搜索到 Top 10。

**改动:**
- `/platform-match` SKILL.md 搜索完成后增加 "是否运行 score_pipeline?" 的交互提示
- pipeline 支持 `--auto-trigger` 模式, 被 platform-match 调用

**优点:** 用户体验最好, 一键完成
**缺点:** 改动最大, 需要 skill 间调用机制

## 未打通的数据缺口

| 缺口 | 说明 | 影响 |
|------|------|------|
| pipeline 结果未写入 data/screens/ | `/screen` 和 `/report` 无法消费 pipeline 评分 | 两套系统数据孤立 |
| pipeline 报告格式与 /report 格式不同 | pipeline 输出评分明细, /report 输出客户推荐文档 | 格式不统一 |
| 校准轮结果未持久化 | calibration.json 未写入 | 无法追溯校准前后对比 |
| /screen 评估无法引用 pipeline 排名 | 人工评估不知道 pipeline 的排名 | 信息丢失 |

## 建议

1. **短期 (方案 A)**: 先文档对齐, 确保用户知道正确的工作流顺序
2. **中期 (方案 B)**: pipeline 评分结果写入 data/screens/, 实现数据贯通
3. **长期 (方案 C)**: 统一入口, 一键从搜索到 Top 10

优先级判断依据:
- 核心指标是 **Top 10 命中率** (70-80%)
- 当前 pipeline 已能独立完成 "搜索→Top 10" 全流程
- `/screen` 的价值在于对 Top 10 中特定候选人做深度追问 (pipeline 做不到)
- 因此方案 A 已足够支撑核心业务, B/C 属于体验优化
