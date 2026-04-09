---
name: screen
description: 候选人筛选评估——将候选人池与JD匹配，打分排序，支持规则进化
---

# 筛选评估

## 触发

```
/screen <jd-id> [--jd <jd-id-2> ...] [--all]
```

## 参数

| 参数 | 必需 | 说明 |
|------|------|------|
| jd-id | 是 | 目标 JD ID（从 `data/jds/` 读取） |
| --jd | 否 | 额外 JD ID（批量多 JD 匹配） |
| --all | 否 | 对候选人池全部评估（不限 JD，仅按岗位匹配度排序） |

## 工具依赖

- **Bash** — 调用 `data-manager.py` 读写数据
- **Read** — 读取参考文件和候选人 JSON
- **Write** — 写入评估报告 md

## 参考

- 评估标准：`skills/screen/references/eval-criteria.md`

---

## 流程

### Step 1: 加载数据

```bash
# 1. 读取 JD
python scripts/data-manager.py jd get <id>

# 2. 读取候选人池（优先 enriched，其次 partial，最后 raw）
python scripts/data-manager.py candidate list

# 3. 加载客户偏好（按 JD 中的 company 字段查找）
python scripts/data-manager.py rules get <company>
```

读取 `skills/screen/references/eval-criteria.md` 获取评估标准。

如果 `rules get` 返回空，说明该客户没有历史修正记录，使用默认评分逻辑。

### Step 2: 逐个评估

对候选人池中的每个候选人执行以下步骤：

#### 2.1 基础评估

按 `eval-criteria.md` 中的 5 个维度逐项评分：

1. **岗位匹配度（30%）** — 对比候选人当前/过往职责与 JD 核心职责
2. **技能覆盖率（25%）** — 计算 JD 要求技能的满足比例
3. **经验深度（20%）** — 对比工作年限和管理经验
4. **行业背景（15%）** — 评估行业相关度
5. **稳定性（10%）** — 分析职业轨迹

每个维度给出 0-100 的分数和简要理由。

#### 2.2 规则调整

如果客户有 `learned_rules`（从 corrections 中提炼的规则），应用调整：

- 例：`"大厂背景权重调低"` → 行业背景维度降 10 分
- 例：`"有创业经验加分"` → 经验深度维度加 10 分

规则调整在基础评分之后、红旗检测之前执行。每个调整需注明规则来源。

#### 2.3 红旗检测

逐条检查 5 项红旗规则：

| 红旗 | 触发条件 | 影响 |
|------|---------|------|
| 高流动性 | 3年内跳槽3次+ | 总分-10 |
| 长空窗期 | 空窗期超过6个月 | 总分-5 |
| 时间重叠 | 工作经历时间有重叠 | 总分-10 |
| 学历疑点 | 学历与工作年限不匹配 | 标记（不扣分） |
| 方向不符 | 最近职业方向与JD完全不符 | 总分-15 |

#### 2.4 差距分析

逐条对标 JD 要求，标注每个要求的状态：

- :white_check_mark: 匹配 — 候选人满足该要求
- :warning: 部分匹配 — 候选人部分满足，有差距
- :x: 缺失 — 候选人不满足该要求

#### 2.5 计算总分

```
总分 = round(岗位匹配度 * 0.30 + 技能覆盖率 * 0.25 + 经验深度 * 0.20 + 行业背景 * 0.15 + 稳定性 * 0.10)
总分 = max(0, 总分 - 红旗扣分)
```

### Step 3: 输出评估表

写入 `data/output/screen-<date>-<jd-slug>-v<N>.md`。

文件名规则：
- `<date>` = 当天日期（YYYY-MM-DD）
- `<jd-slug>` = JD 的 company-title 简写
- `<N>` = 当天同一 JD 的版本号（从 1 开始，如果已存在则递增）

报告格式：

```markdown
# 筛选评估报告

## JD 信息
- **职位**：<title>
- **公司**：<company>
- **类型**：<job_type>
- **核心要求**：<从 description 中提取的 2-3 条关键要求>

## 评估标准
参考：eval-criteria.md
客户偏好：<如果有 learned_rules，列出关键规则>

## 评估结果

| 排名 | 姓名 | 当前职位 | 加权总分 | 岗位 | 技能 | 经验 | 行业 | 稳定 | 关键差距 | 红旗 |
|------|------|---------|---------|------|------|------|------|------|---------|------|
| 1 | 张三 | 技术VP | 85 | 90 | 80 | 85 | 75 | 80 | 无AI/ML背景 | 无 |
| 2 | 李四 | CTO | 78 | 85 | 75 | 80 | 70 | 65 | 创业经验不足 | 高流动性 |

## 详细分析

### #1 张三 — 技术VP @ 某大厂（85分）

**各维度评分：**
| 维度 | 分数 | 理由 |
|------|------|------|
| 岗位匹配度 | 90 | 15年技术管理经验，当前VP职位与JD高度匹配 |
| 技能覆盖率 | 80 | 必备技能全部满足，优先技能中缺AI/ML |
| 经验深度 | 85 | 管理过百人团队，有从0到1搭建经验 |
| 行业背景 | 75 | 互联网行业，但非目标细分领域 |
| 稳定性 | 80 | 平均4年/段，轨迹上升 |

**匹配亮点：**
- 15年技术管理经验，远超10年要求
- 有从0到1搭建百人团队经验

**差距分析：**
- :x: 无 AI/ML 背景（JD 优先要求）
- :warning: 创业公司经验有限（一直在大厂）

**红旗：** 无

---

### #2 李四 — CTO @ 创业公司（78分）
...
```

### Step 4: 用户调整

评估报告输出后，等待用户反馈。用户可以：

1. **调整评分** — 如"张三应该90分，他的AI经验在之前的创业公司有"
2. **标记/取消红旗** — 如"李四的高流动性是因为公司倒闭，不算红旗"
3. **添加评语** — 补充评估中遗漏的信息

每次调整需要记录：
- 调整字段（哪个维度/总分/红旗）
- 原始值和调整后值
- 调整原因

### Step 5: 记录修正，写入结果

用户确认调整后：

```bash
# 1. 记录修正到客户偏好
python scripts/data-manager.py rules add-correction <company> '<json>'

# json 示例:
# {
#   "candidate_id": "cand-1",
#   "jd_id": "jd-xxx",
#   "field": "score",
#   "original": 78,
#   "adjusted": 85,
#   "reason": "AI经验在之前的创业公司有，简历未体现"
# }

# 2. 写入 screening 结果
python scripts/data-manager.py screen create <jd-id> <cand-id> <adjusted-score>

# 3. 如果有红旗或差距，更新 screening
# 先写入临时 JSON 文件，再 update
python scripts/data-manager.py screen update <jd-id> <cand-id> <update-file.json>
```

修正数据格式（写入 `data/rules/preferences.json`）：
```json
{
  "candidate_id": "cand-1",
  "jd_id": "jd-xxx",
  "field": "score|dimension|flag",
  "original": "原始值",
  "adjusted": "调整后值",
  "reason": "用户给出的原因",
  "added_at": "YYYY-MM-DD"
}
```

---

## 规则进化机制

核心思路：**用户每次调整评分，都是一次"训练数据"。**

### 数据流

```
用户调整评分
    ↓
记录 correction 到 preferences.json
    ↓
下次为同一客户 screen 时
    ↓
读取 corrections 作为 few-shot 示例
    ↓
AI 根据历史修正模式调整评分逻辑
```

### 进化规则

1. **单客户内进化**：同一客户的 corrections 只影响该客户的评分
2. **规则提炼**：当同一客户的 corrections 积累到 5 条以上，提炼为 `learned_rules`
   - 格式：`{"rule": "描述", "effect": "维度/分数调整", "based_on": [correction_ids]}`
3. **全局趋势**（MVP 后考虑）：多个客户的共同 correction 模式可提升为全局默认规则

### MVP 实现

MVP 阶段不做自动规则提炼，靠 prompt 中的 few-shot 实现"越用越准"：

- 每次 screen 时，将客户的历史 corrections 作为上下文传入
- AI 根据 corrections 中的调整模式来校准当前评分
- corrections 格式本身就是 few-shot 示例

---

## 注意事项

- **screen 是候选人与 JD 建立关系的唯一入口** — 所有匹配关系都通过 screen 建立
- **支持多 JD 批量匹配** — 同一批候选人可以 vs 多个 JD，输出多份报告
- **评分是参考值** — 用户可以自由调整，AI 评分不等于最终结论
- **用户调整是核心数据** — 每次修正都是规则进化的燃料，务必完整记录
- **enrichment 级别影响准确性** — enriched 候选人数据最全，raw 数据可能信息不足，评分时需标注数据置信度
