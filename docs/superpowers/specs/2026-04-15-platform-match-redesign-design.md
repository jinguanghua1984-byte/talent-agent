# platform-match Skill 全量重设计

**日期**: 2026-04-15
**前置文档**: `docs/design-discussions/2026-04-13-platform-match-skill-redesign.md`
**状态**: 已确认，待实施

---

## 一、已确认的架构决策

| 决策项 | 结论 |
|--------|------|
| 范围 | 全量重设计，解决所有 6 个设计缺口 |
| API 调用方式 | Playwright 拦截式（连接已有 Chrome via CDP） |
| 脚本语言 | Python（与 data-manager.py 一致） |
| 浏览器启动 | 连接已有 Chrome（用户先手动登录） |
| 降级模式 | `--headless` 参数，Playwright 独立启动 + stealth + cookies 恢复 |
| 执行模式 | 三种同时设计（候选丰富 / JD 驱动 / 对话式） |
| 架构分层 | 混合分层——脚本负责 mechanics，SKILL.md 负责 decisions |

---

## 二、整体架构

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────┐
│  SKILL.md (编排层)                                       │
│  ├─ 解析用户意图 → 选择执行模式                            │
│  ├─ 生成搜索参数 → 展示计划 → 用户确认                     │
│  ├─ 调用 Python 脚本 → 解析返回                           │
│  ├─ 身份判定（置信度评分 + 业务规则 + 自学习）              │
│  ├─ JD 匹配排序（评分框架 + 自学习）                       │
│  ├─ 人工介入决策点                                        │
│  └─ 生成输出报告                                         │
├─────────────────────────────────────────────────────────┤
│  Python 脚本 (执行层)                                     │
│  ├─ session.py    — CDP 连接 + session 管理               │
│  ├─ search.py     — API 搜索 + 分页 + 结果解析             │
│  ├─ enrich.py     — 字段映射 + 逐字段冲突合并 + 写入        │
│  ├─ rate_limiter.py — 令牌桶限流（每平台独立配额）          │
│  └─ adapters/     — 平台适配器（当前仅 maimai）             │
│      ├─ base.py   — PlatformAdapter 协议                   │
│      └─ maimai.py — 脉脉搜索实现                          │
├─────────────────────────────────────────────────────────┤
│  基础设施                                                  │
│  ├─ Playwright (连接已有 Chrome / 独立启动)                │
│  ├─ data-manager.py (候选人 + 批次 CRUD)                  │
│  ├─ rules/identity-rules.md (身份判定规则)                 │
│  └─ rules/jd-match-rules.md (人岗匹配规则)                 │
└─────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
platform-match/
├── SKILL.md                              # 编排层 (<500行)
├── scripts/
│   ├── session.py                        # CDP 连接 + session 管理
│   ├── search.py                         # API 搜索 + 分页
│   ├── enrich.py                         # 字段映射 + 逐字段合并 + 写入
│   ├── rate_limiter.py                   # 令牌桶限流（每平台独立配额）
│   └── adapters/                         # 平台适配器
│       ├── __init__.py
│       ├── base.py                       # PlatformAdapter 协议
│       └── maimai.py                     # 脉脉搜索实现
├── references/
│   ├── maimai/
│   │   ├── api-reference.md              # 搜索 API 请求/响应规格
│   │   ├── field-mapping.md              # API 字段 → candidate.schema 映射表
│   │   └── anti-detect.md               # 反检测策略
│   ├── browser-tools.md                  # 浏览器工具选型（归档）
│   └── matching-strategy.md              # 多匹配判定策略
├── rules/
│   ├── identity-rules.md                 # 身份判定规则（场景1：人找人）
│   └── jd-match-rules.md                 # 人岗匹配规则（场景2：条件找人）
├── assets/
│   ├── candidate-list-template.md        # 候选人列表输出模板
│   └── match-report-template.md          # 匹配报告模板
└── evals/
    └── evals.json
```

### 2.3 清理旧代码

以下文件/目录完全删除（三月份设计已作废）：

- `modules/form-filler/` — 整个目录
- `modules/loop-orchestrator/` — 整个目录
- `modules/result-merger/` — 整个目录
- `modules/logger.ts` — 整个文件
- `references/form-controls-map.md` — DOM 控件映射
- `references/maimai-fields.md` — 旧字段映射
- `references/platform-config.md` — 旧配置

---

## 三、端到端数据流（解决 Gap 1）

### 3.1 三种模式的输入输出

| 维度 | 模式 1（候选丰富） | 模式 2（JD 驱动） | 模式 3（对话式） |
|------|-------------------|-------------------|-------------------|
| 输入 | `data/batches/<batch-id>.json` 或候选人属性过滤 | `data/jds/<id>.json` 或 JD 文本 + 搜索策略 | 用户自然语言 |
| 搜索参数来源 | name → query, current_company → query 附加 | Claude 从 JD 提取 + 用户策略补充 | Claude 直接生成 |
| 输出 | 更新 `data/candidates/*.json`（enrichment_level → enriched） | 新建 `data/candidates/*.json` + 搜索列表报告 | 新建或仅展示 |

### 3.2 API 字段 → candidate.schema.json 映射

| 脉脉 API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| `name` | `name` | 直接映射 |
| `gender_str` | `gender` | 1→"男", 2→"女", 其他→"未提及" |
| `age` | `age` | 直接映射 |
| `city` | `city` | 直接映射 |
| `company` | `current_company` | 直接映射 |
| `position` | `current_title` | 直接映射 |
| `sdegree` | `education` | 1→"本科", 2→"硕士", 3→"博士", 4→"大专" |
| `worktime` | `work_years` | "4年7个月" → 提取数字取整 |
| `hunting_status` | `status` | 见下方完整映射表 |
| `exp[].company` | `work_experience[].company` | 直接映射 |
| `exp[].position` | `work_experience[].title` | 直接映射 |
| `exp[].v` | `work_experience[].period` | "2021-09-01至今" → "2021-09 - 至今" |
| `exp[].description` | `work_experience[].description` | 直接映射 |
| `edu[].school` | `education_experience[].school` | 直接映射 |
| `edu[].major` | `education_experience[].major` | 直接映射 |
| `edu[].v` | `education_experience[].period` | 同上格式转换 |
| `edu[].sdegree` | `education_experience[].description` | 附加学历信息 |
| `job_preferences.regions[]` | `expected_city` | 数组直接映射 |
| `job_preferences.positions[]` | `expected_title` | 取第一个 |
| `job_preferences.salary` | `expected_salary` | 直接映射 |
| `exp_tags[]` / `tag_list[]` | `skill_tags` | 合并去重 |
| `detail_url` | `sources[].url` | 构造 source 对象 |
| `id`（脉脉 uid） | `sources[].platform_id` | channel="maimai" |
| `active_state` | `active_state`（新增字段） | 直接映射 |
| `user_project[]` | `project_experience`（新增字段） | 直接映射 |

### 3.3 candidate.schema.json 扩展

**新增字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `active_state` | string | 活跃状态（"今日活跃"/"在线"/"3天前活跃"） |
| `project_experience` | array | 项目经历（见下方 item 结构） |

**project_experience[] item 结构：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 项目名称 |
| `period` | string | 是 | 时间段（"2023-06 - 2024-12"） |
| `role` | string | 否 | 担任角色 |
| `description` | string | 否 | 项目描述 |

**sources[] 扩展 schema（新增字段）：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `channel` | string | 是 | 来源平台标识（"maimai"/"boss"/"public-search"） |
| `url` | string | 是 | 来源 URL |
| `found_at` | string | 是 | 发现时间（ISO 8601） |
| `platform_id` | string | 否 | 平台用户 ID（如脉脉 uid） |
| `enrichment_level` | string | 否 | 本次来源的丰富程度（"raw"/"partial"/"enriched"） |
| `match_confidence` | integer | 否 | 身份匹配置信度（0-100，仅候选丰富模式） |
| `match_path` | string | 否 | 匹配路径（"A"/"B"，仅候选丰富模式） |
| `snapshot` | object | 否 | 发现时的状态快照（见下方） |

**snapshot 结构：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `company_at_source` | string | 发现时的公司 |
| `position_at_source` | string | 发现时的职位 |

### 3.3.1 hunting_status 完整映射

| 脉脉 `hunting_status` | candidate `status` | 说明 |
|---|---|---|
| 5 | "在职-看机会" | 主动求职 |
| 1-4 | "在职-不看" | 未主动求职（细分值待实测补充） |
| 0 | "在职-不看" | 未设置求职状态 |
| 离职标识（待实测确认具体值） | "离职-求职中" | 已离职 |
| 无此字段 | 不更新 `status` | API 未返回时不覆盖已有值 |

> 注：脉脉 API 的 `hunting_status` 完整枚举值需在登录后实测确认。上表为基于现有数据的推测，实施时需校准。

### 3.4 逐字段冲突策略

当多渠道数据冲突时，`enrich.py` 按字段类型采用不同合并策略：

| 字段类型 | 策略 | 适用字段 |
|----------|------|----------|
| 最新来源优先 | 取时间最新的值 | `current_company`, `current_title`, `expected_salary`, `expected_city`, `status`, `active_state` |
| 首次来源优先 | 候选人尚无该字段时写入，已有则不覆盖 | `education_experience` |
| 合并去重 | 按唯一键合并 | `skill_tags`, `work_experience` |
| 多数投票 | 多源一致则写入 | `age`, `gender` |

---

## 四、身份判定与多匹配策略（解决 Gap 2）

### 4.1 两种匹配的严格区分

| 维度 | 身份判定（人找人） | JD 匹配（条件找人） |
|------|-------------------|---------------------|
| 目标 | 确认搜索结果中的哪一个是目标人 | 判断候选人群体中谁更适合 JD |
| 输入 | 已知候选人的 `{name, company, title}` | JD 文本或搜索条件 |
| 输出 | 0 或 1 个确认人选 | 排序后的候选人列表 |
| 判定信号 | 身份特征（公司、学历、经历交叉验证） | 适配度（技能、经验、行业对齐） |
| 规则性质 | 确定性验证（是/不是同一个人） | 概率性排序（更/不那么适合） |
| 规则存储 | `rules/identity-rules.md` | `rules/jd-match-rules.md` |

### 4.2 候选丰富模式的搜索策略

双路径搜索：

```
路径 A: query = "{name} {current_company}"
  → 精确度高，但如果人已跳槽可能搜不到

路径 B: query = "{name} {current_title}"
  → 覆盖面广，但同名干扰多

执行顺序: 先 A → 有结果用 A → 无结果走 B → 都无 → 标记"未找到"
```

### 4.3 判定流程

```
步骤 1: 精确过滤
  - company 完全匹配（含别名，别名表见 `rules/company-aliases.json`）AND position 相似度 > 70%
  → 剩余 ≤ 1: 自动选取（仅限置信度 ≥ 95%）

步骤 2: 模糊匹配
  - company 匹配 + education 重叠 OR work_experience 时间重叠
  → 剩余 ≤ 1: 向用户建议，待确认

步骤 3: 多维度评分
  对每个搜索结果打分:
  - company 匹配度 (0-30)
  - position 匹配度 (0-25)
  - education 匹配度 (0-20)
  - city 匹配度 (0-10)
  - skill_tags 重叠度 (0-15)
  + rules/identity-rules.md 中匹配到的规则加分
  → 差距 > 20: 自动选取（≥ 95%）
  → 否则: 向用户建议最优人选，待确认

步骤 4: 置信度 < 70%
  → 展示 Top 3 供用户选择，不给出建议
```

**原则**：只有"几乎确定是同一个人"（≥ 95%）才自动选，其余一律人控。

### 4.4 身份判定自学习机制

```
用户在多个同名结果中选择目标人选
  ↓
系统询问: "你选择这个人选的主要依据是什么？"
  ↓
用户用自然语言回答（可简短，可跳过）
  ↓
Claude 抽象为可复用的身份判定规则
  ↓
展示规则 → 用户确认/修改/拒绝
  ↓
确认 → 追加到 rules/identity-rules.md（标注来源日期）
拒绝 → 仅记录本次选择，不更新规则
```

### 4.5 rules/identity-rules.md 格式

```markdown
# 身份判定规则

## 自动判定规则（系统生成，由用户确认后生效）

### 规则 1: 行业方向匹配优先
- 来源: 用户判定反馈 (2026-04-15)
- 触发条件: 搜索结果中有多个同公司候选人
- 判定逻辑: 当前经历的行业/业务方向与目标匹配的候选人优先
- 加分: +15（position 维度）

## 人工兜底规则
- 无法自动判定时，展示 Top 3 给用户选择
- 用户选择"都不是"时，标记候选人为"平台未收录"
```

---

## 五、候选人唯一性与去重

### 5.1 分层匹配策略

```
匹配优先级:
1. platform_id 精确匹配（maimai_id / boss_id）  → 100% 确认同一人
2. name + education + company 时间重叠交叉验证   → 90%+ 置信度
3. name + company（同时间段）                    → 70% 置信度
4. 仅 name 相似                                 → 50% 置信度，标记待确认
```

### 5.2 sources[] 快照机制

每个 source 记录发现时的状态快照，解决"跳槽后匹配不上"的问题：

```json
{
  "channel": "maimai",
  "platform_id": "12345",
  "url": "https://maimai.cn/u/12345",
  "found_at": "2026-04-15T10:00:00",
  "enrichment_level": "enriched",
  "match_confidence": 95,
  "match_path": "A",
  "snapshot": {
    "company_at_source": "字节跳动",
    "position_at_source": "产品经理"
  }
}
```

### 5.3 跨候选人去重合并

当发现两个已存在的候选人（不同 ID）是同一自然人时：

```bash
python scripts/data-manager.py candidate dedup-merge <primary-id> <secondary-id>
```

合并规则：

1. **ID 保留**：primary-id 存活，secondary-id 重命名为 `.merged.json`
2. **sources[]**：两者合并去重
3. **字段冲突**：复用逐字段策略（Section 3.4）
4. **关联数据**：screen 记录中引用 secondary-id 的，更新为 primary-id
5. **enrichment_level**：取两者中更高的

触发路径：

| 路径 | 场景 |
|------|------|
| 自动检测 | `data-manager.py candidate dedup`（按 name+company 分组） |
| 人工发现 | 用户在查看候选人列表时发现重复 |
| 丰富过程中 | 模式 1 搜索时发现 platform_id 已被其他候选人关联 |

---

## 六、Session 管理（解决 Gap 3）

### 6.1 默认模式（CDP 连接）

```
用户操作                          系统行为
──────                          ──────────
1. 手动打开 Chrome（已登录脉脉）
2. chrome --remote-debugging-port=9222
3. /platform-match 触发 skill
                                  4. session.py status → 检查连接
                                     ├─ 可用 → 继续
                                     └─ 不可用 → 提示用户启动 Chrome
5. 执行搜索...
                                  6. session.py save → 导出 cookies 备份
```

session.py 命令：

```bash
python scripts/session.py status                           # CDP 连接状态
python scripts/session.py save [--output <path>]           # 导出 cookies
python scripts/session.py verify --platform maimai         # 验证登录态
python scripts/session.py endpoints                        # 列出 CDP 端点
```

### 6.2 降级模式（`--headless`）

通过 `--headless` 参数触发，Playwright 独立启动 + stealth + cookies 恢复。

| 维度 | 默认模式 | 降级模式 |
|------|---------|---------|
| 触发 | `/platform-match` | `/platform-match --headless` |
| 浏览器 | 连接已有 Chrome | Playwright 独立启动 + stealth |
| 登录态 | 用户手动登录 | 从 cookies 备份恢复 |
| 反检测 | 真实浏览器，零风险 | stealth 插件，中等风险 |
| 搜索间隔 | 3-8s | 8-15s |
| 单批上限 | 30 | 15 |
| 每日上限 | 200 | 80 |
| 适用场景 | 日常使用（推荐） | CI/定时任务/远程执行 |

降级模式额外命令：

```bash
python scripts/session.py restore --platform maimai [--session-file <path>]
python scripts/session.py verify --platform maimai --mode standalone
```

降级模式流程：

```
/platform-match --headless
  ├─ session.py verify --platform maimai --mode standalone
  │   ├─ cookies 存在且有效 → session.py restore → 开始执行
  │   ├─ cookies 不存在 → "未找到备份，请先用默认模式执行一次"
  │   └─ cookies 过期 → "已过期，请先用默认模式重新登录"
  └─ 执行中更保守的速率控制
```

### 6.3 Cookies 备份策略

| 时机 | 动作 |
|------|------|
| 每次搜索批次结束 | 导出到 `data/session/maimai-cookies-<timestamp>.json` |
| 保留策略 | 最多 3 份，按时间戳命名 |
| 验证失败 | 提示用户重新登录，不自动恢复 |

---

## 七、频率控制（解决 Gap 4）

### 7.1 三层频率控制

```
层级 1: 硬性底线（代码强制，不可配置）
  ├─ 单次搜索间隔: 3-8s 随机（降级模式 8-15s）
  ├─ 单页翻页间隔: 2-5s 随机
  └─ 连续操作上限: 每 30 分钟暂停 60-120s

层级 2: 弹性控制（可配置）
  ├─ 单批搜索上限: 默认 30（降级 15）
  ├─ 批次间休息: 5-10 分钟
  └─ 每日搜索上限: 默认 200（降级 80）

层级 3: 异常熔断（自动触发，不可绕过）
  ├─ 触发信号: 验证码页面 / 403 / 空结果连续 3 次 / 响应 > 10s
  ├─ 熔断动作: 立即停止 → 通知用户 → 记录事件
  └─ 恢复条件: 用户手动确认继续 / 等待 30 分钟后提示
```

### 7.2 令牌桶实现

rate_limiter.py 内部使用令牌桶算法，状态持久化到 `data/session/rate-limit-state.json`，支持每平台独立配额。

```bash
python scripts/rate_limiter.py status --platform maimai
python scripts/rate_limiter.py tick --platform maimai
python scripts/rate_limiter.py reset
```

### 7.3 待校准参数

| 指标 | 估算值 | 依据 |
|------|--------|------|
| 每小时安全搜索量 | 60-80 次 | 约 45s/次含翻页 |
| 每日安全搜索量 | 200-300 次 | 未验证，需观察 |
| 连续搜索风控阈值 | 未知 | 需实测 |

实际数字在 `references/maimai/api-reference.md` 中维护，后续实测后直接改一处。

---

## 八、错误处理（解决 Gap 5）

### 8.1 错误分级

| 级别 | 处理方式 | 用户感知 |
|------|---------|---------|
| P0（阻塞） | 暂停，提示明确解决步骤 | 明确提示 |
| P1（重试） | 自动重试 1 次，仍失败跳过 | 无感知 |
| P2（跳过） | 标记状态，继续下一个 | 报告中汇总 |
| P3（记录） | 仅记录日志 | 无感知 |

### 8.2 错误场景表

| 场景 | 级别 | 处理 |
|------|------|------|
| Chrome 未启动 / CDP 无响应 | P0 | 提示启动命令 |
| 脉脉登录态过期 | P0 | 提示重新登录 |
| 请求超时（> 15s） | P1 | 自动重试 1 次 |
| API 返回非预期 code | P1 | 记录日志，跳过 |
| 连续 3 次失败 | P1→P0 | 触发熔断 |
| 搜索 0 结果 | P2 | 标记"平台未收录" |
| API 字段缺失 | P2 | 跳过该字段 |
| data-manager.py 写入失败 | P1 | 保存临时文件，提示 |
| 每日配额耗尽 | P0 | 暂停，提示明日继续 |

### 8.3 search.py 错误返回格式

所有错误通过 stdout JSON 返回：

```json
{"status": "ok", "data": {...}}
{"status": "error", "code": "SESSION_EXPIRED", "message": "...", "retryable": false}
{"status": "error", "code": "CIRCUIT_BREAK", "message": "...", "retryable": false, "trigger_reason": "..."}
```

---

## 九、Skill 间衔接（解决 Gap 6）

### 9.1 衔接契约

| 契约 | 内容 |
|------|------|
| platform-match 不修改 `id` | 候选人 ID 一旦生成就不变 |
| platform-match 不删除候选人 | 丰富失败的标记状态 |
| enrichment_level 只升不降 | raw → partial → enriched |
| sources 只追加不覆盖 | 新增 source 追加到数组 |
| 输出报告格式固定 | markdown，screen/report 可解析 |

### 9.2 上游衔接（public-search → platform-match）

输入：`data/batches/<batch-id>.json` 或通过 `--candidates` 属性过滤

过滤条件：`enrichment_level in ["raw", "partial"]`

### 9.3 下游衔接（platform-match → screen / report）

screen 需要的字段：`name`, `current_company`, `current_title`, `work_experience[]`, `skill_tags[]`, `education_experience[]`, `expected_salary`, `expected_city`

report 读取：`sources[]`（来源追踪）+ `enrichment_level`（数据完整度）

---

## 十、多渠道扩展架构

### 10.1 适配器模式

新增平台只需：

1. 创建 `scripts/adapters/<platform>.py`，实现 `PlatformAdapter`
2. 在 `references/<platform>/` 下放 API 文档和字段映射
3. 在 rate_limiter 配置中添加默认配额
4. SKILL.md 的 `--platform` 参数自然支持

### 10.2 PlatformAdapter 协议

```python
class PlatformAdapter(Protocol):
    platform_name: str

    async def search(self, page: Page, params: SearchParams) -> SearchResult: ...
    async def get_detail(self, page: Page, platform_id: str) -> CandidateData: ...
    def map_to_schema(self, api_data: dict) -> dict: ...
    def build_search_params(self, candidate: dict | None, jd: dict | None,
                            user_input: dict | None) -> list[SearchParams]: ...
```

### 10.3 rate_limiter 多平台配额

状态文件 `data/session/rate-limit-state.json` 按 platform 分隔配额。

---

## 十一、SKILL.md 详细设计

### 11.1 Progressive Disclosure 三层结构

```
Layer 1: Frontmatter（始终加载，~50 词）
  name + description + triggers
  → 决定"什么时候激活"

Layer 2: SKILL.md body（触发时加载，<500 行）
  ├─ 参数解析与模式路由
  ├─ Session 检查流程
  ├─ 三种模式的编排步骤表
  ├─ 通用子流程（判定、合并、报告、错误处理）
  └─ 资源索引（场景 → 文件映射）

Layer 3: Bundled Resources（按需加载）
  ├─ references/maimai/api-reference.md
  ├─ references/maimai/field-mapping.md
  ├─ references/matching-strategy.md
  ├─ rules/identity-rules.md
  ├─ rules/jd-match-rules.md
  └─ assets/*.md
```

### 11.2 Frontmatter

```yaml
---
name: platform-match
description: >
  招聘平台候选人搜索与信息丰富。在脉脉等招聘平台上搜索候选人，
  丰富候选人库信息，或根据 JD/条件搜索目标人选。
triggers:
  - "匹配候选人"
  - "搜索脉脉"
  - "平台找人"
  - "丰富候选人"
  - "platform match"
  - "/platform-match"
---
```

**原则**：description 只写"做什么"，不写"怎么做"。

### 11.3 参数与模式路由

```
/platform-match                              → 对话式（模式 3）
/platform-match --candidates <filter>        → 候选丰富（模式 1）
/platform-match --jd <id|file>               → JD 驱动（模式 2）
/platform-match --headless                   → 降级模式（附加在任意模式上）
```

---

## 十二、三种执行模式详细流程

### 12.1 模式 1：候选丰富（人找人）

```
步骤 1: 选择待丰富候选人
  ├─ 输入 A: --candidates batch:<batch-id>
  │   ├─ 读取 data/batches/<batch-id>.json
  │   └─ 展示批次摘要
  ├─ 输入 B: --candidates "company=阿里巴巴" / "enrichment=raw"
  │   └─ data-manager.py candidate list + 过滤
  └─ 无参数 → 交互式选择
      ├─ 展示摘要表格（含批次 score 排序）
      ├─ 用户自然语言筛选: "只处理前10个" / "跳过李四"
      └─ 确认最终列表

步骤 2: 逐个搜索匹配
  FOR EACH candidate:
    ├─ 2.1 生成搜索参数（路径 A → B 降级）
    ├─ 2.2 检查 platform_id 是否已关联
    │   ├─ 已关联（同记录）→ 直接获取最新数据
    │   ├─ 已关联（其他记录）→ 触发去重检查
    │   └─ 未关联 → 执行搜索
    ├─ 2.3 调用 search.py
    │   ├─ 0 结果 → 标记"平台未收录"
    │   ├─ 1 结果 → 自动选取（置信度 95%）
    │   └─ 多结果 → 判定流程
    ├─ 2.4 多匹配判定
    │   ├─ ≥ 95% → 自动选取（报告中标注"请复核"）
    │   ├─ 70-94% → 向用户建议，待确认
    │   └─ < 70% → 展示 Top 3，用户选择
    │   └─ 自学习: 采集判定理由 → 提炼规则 → 确认
    ├─ 2.5 丰富写入
    │   ├─ enrich.py map → data-manager.py candidate update
    │   ├─ data-manager.py candidate merge
    │   └─ 追加 sources[]（含 platform_id + snapshot）
    └─ 2.6 速率检查

步骤 3: 生成报告
  └─ data/output/platform-match-report.md
```

### 12.2 模式 2：JD 驱动（条件找人）

```
步骤 1: 读取 JD 与搜索策略
  ├─ data-manager.py jd get <id> / 用户直接提供 JD 文本
  ├─ 解析 JD 自动提取搜索条件（基础层）
  ├─ 获取用户搜索策略（增强层，优先级更高）
  │   ├─ 用户随 JD 提供 → 例: "优先大厂经验，P7 以上"
  │   ├─ 用户未提供 → 系统主动询问
  │   └─ 用户可回答"没有"
  └─ 综合生成搜索计划（基础组 2-3 + 增强组 1-2），用户确认

步骤 2: 执行搜索
  FOR EACH 搜索组:
    ├─ search.py → 分页获取（默认前 3 页 = 90 条）
    └─ 跨组去重（按 platform_id）

步骤 3: 结果排序与筛选
  ├─ 加载 rules/jd-match-rules.md + 用户策略要求
  ├─ 构建评分维度:
  │   ├─ 基础维度: 职位(30) + 技能(25) + 行业(20) + 学历(15) + 意向(10)
  │   └─ 用户自定义维度（动态添加/调整权重）
  └─ 展示 Top N（默认 20），标注得分明细

步骤 4: 用户选择入库
  ├─ 用户批量勾选要添加的候选人
  ├─ 统一询问选择理由（一次，非逐人）
  │   "你选择了以下 8 位候选人，主要考量是什么？"
  │   ├─ 整体描述 → 提炼通用规则
  │   ├─ 个别说明 → 提炼附加规则
  │   └─ 跳过 → 不触发规则提炼
  └─ 自学习: 展示规则 → 确认 → 写入 jd-match-rules.md

步骤 5: 写入候选人库
  FOR EACH 用户选中:
    ├─ 检查是否已存在（name + company 去重）
    ├─ 不存在 → data-manager.py candidate create
    └─ 已存在 → data-manager.py candidate update + merge

步骤 6: 生成报告
  └─ data/output/platform-match-search-list.md
```

### 12.3 模式 3：对话式

```
步骤 1: 理解搜索需求
  ├─ 用户自然语言 → Claude 解析为搜索参数
  └─ 展示解析结果，用户确认

步骤 2: 执行搜索
  ├─ search.py → 分页 → 展示摘要表格

步骤 3: 用户决策
  ├─ 调整条件重新搜索
  ├─ 选择加入候选人库
  ├─ 查看某人详情
  └─ 结束搜索

步骤 4: 按需写入（同模式 2 步骤 5）
```

---

## 十三、自学习机制统一抽象

身份判定（场景 1）和 JD 匹配（场景 2）共享同一套自学习流程：

```
触发点: 用户在候选列表中做出选择
  ↓
采集: 系统询问选择理由（用户可跳过）
  ↓
提炼: Claude 将理由抽象为规则
  ↓
确认: 展示规则，用户确认/修改/拒绝
  ↓
持久化: 写入对应 rules 文件
  ├─ 场景 1 → rules/identity-rules.md
  └─ 场景 2 → rules/jd-match-rules.md
  ↓
运用: 下次匹配时加载规则，标注"命中规则 N"
```

透明性保障：

| 保障点 | 机制 |
|--------|------|
| 规则生成前 | 向用户展示原始理由 → 提炼的规则 |
| 规则生效前 | 必须用户确认 |
| 规则生效后 | 写入 rules 文件并标注来源日期，可随时编辑/删除 |
| 规则使用时 | 评分结果中标注"命中规则 N" |
| 规则退化 | 长期未命中的规则定期提醒审查 |

---

## 十四、public-search 配套改动

### 14.1 需新增内容

**1. 批次文件**：每轮搜索结束时自动创建

存储路径：`data/batches/public-search-<date>-<seq>.json`

```json
{
  "id": "public-search-20260415-1",
  "created_at": "2026-04-15T08:30:00",
  "jd_id": "jd-20260415-alibaba-aigc-pm",
  "strategy_file": "data/search-strategies/instances/2026-04-15-aigc-pm.md",
  "round": 1,
  "query_summary": "AI产品经理 AIGC 互联网",
  "candidates": [
    {
      "id": "cand-1",
      "name": "张三",
      "company": "阿里巴巴",
      "title": "产品经理",
      "score": 92,
      "match_highlights": ["AIGC产品经验", "百万DAU"]
    }
  ],
  "total": 2,
  "metadata": {
    "channels_used": ["LinkedIn", "Google"],
    "keywords_used": ["AI产品经理", "AIGC"],
    "token_cost": 30600
  }
}
```

**2. 候选人初筛评分**：每轮搜索确认时，Claude 对每个候选人打初步匹配度（0-100），存储为 `pre_screen_score`

> 注：此分数为 public-search 阶段的初步筛选依据，与 screen skill 的详细人岗评估（Tier S/A/B）是不同层级的评分。screen 会在完整候选人信息基础上做更深入的评估。

| 维度 | 分值 | 说明 |
|------|------|------|
| 职位匹配度 | 0-30 | 当前职位与 JD 目标岗位的匹配 |
| 技能重叠度 | 0-25 | 技能标签与 JD 要求的重叠 |
| 行业经验 | 0-20 | 行业背景与 JD 的相关性 |
| 公司背景 | 0-15 | 公司类型/规模与 JD 的匹配 |
| 综合印象 | 0-10 | 基于公开信息的整体判断 |

**3. public-search SKILL.md 修改**：在「候选人写入」章节后新增「批次记录」章节

**4. data-manager.py 新增批次命令**：

```bash
python scripts/data-manager.py batch list
python scripts/data-manager.py batch get <batch-id>
python scripts/data-manager.py batch candidates <batch-id> [--filter "score>80"]
```

### 14.2 上下游衔接契约

| 契约 | public-search（上游） | platform-match（下游） |
|------|---------------------|----------------------|
| 批次文件 | 每轮搜索结束时自动创建 | 通过 `--candidates batch:<id>` 读取 |
| 候选人评分 | 搜索确认时 Claude 打分 | 用于排序和筛选 |
| 候选人 ID | 批次中记录已写入的 cand-id | 直接引用 |
| 策略关联 | 批次文件中记录 strategy_file | 可追溯搜索上下文 |

### 14.3 实施顺序建议

先改 public-search（加批次机制），再重写 platform-match（依赖批次文件）。或并行设计，串行实施。

---

## 十五、data-manager.py 新增命令汇总

| 命令 | 说明 | 用途 |
|------|------|------|
| `batch list` | 列出所有搜索批次 | 查看历史批次 |
| `batch get <id>` | 查看批次详情 | 获取候选人列表 |
| `batch candidates <id> [--filter]` | 从批次中筛选候选人 ID | 模式 1 输入 |
| `candidate dedup-merge <primary> <secondary>` | 合并两个候选人为同一自然人 | 跨记录去重 |

---

## 附录 A：Spec Review 修订记录（2026-04-15）

以下问题由 spec review 发现并修复：

### HIGH 修订

**H1. sources[] schema 扩展定义**
- 问题：sources[] 新增字段（platform_id、match_confidence、snapshot 等）未在 schema 中定义
- 修复：在 Section 3.3 新增完整的 sources[] 扩展 schema 和 snapshot 结构定义

**H2. data-manager.py source 去重键 bug**
- 问题：`cmd_candidate_merge` 第 329 行使用 `src.get("type", "")` 作为去重键，但 schema 定义的是 `channel`
- 修复：实施时需将第 329 行改为 `src.get("channel", "")`，同步更新 dedup 逻辑

**H3. hunting_status 映射不完整**
- 问题：仅映射了 5→"在职-看机会"和默认→"在职-不看"，缺少离职状态映射
- 修复：新增 Section 3.3.1 完整映射表，标注待实测值

**H4. project_experience 字段结构缺失**
- 问题：声明了 array 类型但未定义 item 结构
- 修复：在 Section 3.3 定义了完整的 item 结构（name, period, role, description）

**H5. 批次断点恢复机制缺失**
- 问题：长时间批次中 Playwright 崩溃或 session 过期时无法恢复
- 修复：新增 Section 附录 B（批次断点恢复）

### MEDIUM 修订

**M1. 公司别名注册表**
- 修复：Section 4.3 步骤 1 引用 `rules/company-aliases.json`，初始内容示例：
  ```json
  {"阿里巴巴": ["阿里巴巴集团", "阿里"], "字节跳动": ["字节", "ByteDance"], "腾讯": ["腾讯科技", "Tencent"]}
  ```

**M2. "首次来源优先"歧义**
- 修复：Section 3.4 修改为"候选人尚无该字段时写入，已有则不覆盖"

**M3. rate_limiter 文件锁**
- 修复：Section 七补充——rate_limiter.py 使用 `msvcrt.locking`（Windows）/ `fcntl.flock`（Linux）进行文件锁，防止多实例并发写入

**M4. Cookie 安全**
- 修复：Section 六补充——`data/session/` 目录已加入 `.gitignore`，cookies 文件以明文存储在本地（不提交到 git），未来可考虑 AES-256-GCM 加密

**M5. "搜索组"概念定义**
- 修复：Section 12.2 明确定义——"搜索组"是一个 `SearchParams` 实例（一种特定的关键词/筛选器组合），执行后跨页收集结果

**M6. 批次评分与 screen 重叠**
- 修复：Section 14.1 评分重命名为 `pre_screen_score`，并标注与 screen 评分的层级区别

---

## 附录 B：批次断点恢复机制

### 进度文件

每次模式 1 批次开始时，创建进度文件 `data/session/batch-progress-<timestamp>.json`：

```json
{
  "batch_id": "public-search-20260415-1",
  "started_at": "2026-04-15T10:00:00",
  "candidates": [
    {"id": "cand-1", "status": "completed", "result": "enriched"},
    {"id": "cand-2", "status": "completed", "result": "not_found"},
    {"id": "cand-3", "status": "in_progress", "last_step": "search"},
    {"id": "cand-4", "status": "pending"},
    {"id": "cand-5", "status": "pending"}
  ],
  "summary": {"completed": 2, "failed": 0, "pending": 3}
}
```

### 恢复流程

```
模式 1 批次执行中发生中断（P0 错误 / Chrome 关闭 / 用户取消）:
  1. 保存当前进度到 batch-progress 文件
  2. 展示中断信息: "已处理 2/5，剩余 3 个"

用户重新执行 /platform-match --candidates batch:<batch-id>:
  1. 检查是否存在未完成的 batch-progress 文件
  2. 如存在 → 提示: "发现未完成的批次（2/5 已完成），是否从断点继续？"
  3. 用户确认 → 跳过已完成的，从 in_progress/pending 继续
  4. 用户拒绝 → 从头开始
```
