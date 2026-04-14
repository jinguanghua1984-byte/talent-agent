# platform-match Skill 重设计讨论

**日期**: 2026-04-13
**状态**: 讨论中
**前置文档**: 三月份的脉脉表单填充设计文档（已作废）

---

## 一、业务定位

platform-match 是全业务流程的第二个环节：

```
public-search → platform-match → screen → report
     ↑                ↑
  候选人名单      招聘平台匹配
```

### 两种入口模式

| 模式 | 输入 | 场景 | 输出 |
|------|------|------|------|
| **候选人丰富模式** | public-search 产出的候选人 list | JD 适合公域搜索，先公开搜到人再到平台验证/丰富 | 丰富后的候选人库 + 匹配报告 |
| **直接搜索模式** | JD 或搜索策略描述 | JD 不适合 public-search（职位较低等），直接进入平台搜索 | 候选人 list（md/excel） + 搜索统计 |

---

## 二、五个核心难点及设计决策

### 难点 1：多平台扩展性

**现状**: 已有脉脉适配器（form-filler、loop-orchestrator、result-merger），但全部是单体实现。

**决策**:
- 当前聚焦脉脉一个平台，但架构设计严格遵循 Anthropic 官方 skill 最佳实践
- 三月份的设计文档全部作废
- 参考 skill-creator 的 Progressive Disclosure 三层加载机制设计
- 模块化组织，为未来多渠道扩展预留接口

**已确认**: 非会员页面限制太多不可用，锁定会员人才银行页面。

### 难点 2：登录授权复杂性

**调研结论**:

| 平台 | 验证方式 | 难度 |
|------|---------|------|
| 脉脉 | 短信 + 设备指纹绑定 | 极高 |
| BOSS直聘 | 短信/扫码 + `__zp_stoken__` 动态令牌 | 最高 |
| 猎聘 | 图形验证码 + 滑块 | 中高 |
| 拉勾 | 短信/扫码 | 中 |

**决策**:
- 接受人工介入登录授权，或人工先登录后再执行 skill
- 完全自动化登录 = 与平台对抗，法律风险高
- Session 持久化 + 健康检查 + 过期通知用户重新登录
- agent-browser 已有 Session 持久化能力（AES-256-GCM 加密）

### 难点 3：人选信息提取

**策略**: API 拦截优先 + DOM/LLM 提取做补充

```
提取链路:
1. 浏览器拦截平台内部 API → 获取 JSON 结构化数据（快、准）
2. API 失败 → DOM snapshot + LLM 分析（通用、慢）
3. 两者结合 → 互相补充
```

**参考项目**: [mcp-jobs](https://github.com/mergedao/mcp-jobs) 已实现多平台 API 拦截。

### 难点 4：反爬机制与浏览器工具选型

**调研方案对比**:

| 方案 | 反检测能力 | MCP 集成 | Session 持久化 | API 拦截 | Windows | 推荐度 |
|------|-----------|---------|---------------|---------|---------|--------|
| agent-browser | 中（已有） | 已集成 | AES-256-GCM | 支持 | 支持 | 已有，作为可选项 |
| Playwright + stealth | 高 | 需自建 | 需自建 | 支持 | 支持 | 推荐 |
| CloakBrowser（2026新） | 最高（C++源码级修改Chromium） | 需自建 | 需自建 | 支持 | 需验证 | 值得关注 |
| browser-use + MCP | 中高 | mcp-browser-use | 需自建 | 支持 | 支持 | 推荐 |
| 指纹浏览器 API | 最高（商业） | 需对接 | 内置 | 支持 | 支持 | 多账号场景 |
| Puppeteer + stealth | 高（stealth已停维护） | 需自建 | 需自建 | 支持 | 支持 | 不推荐 |

**PoC 验证结果（Playwright + stealth v2.0.3）**:

| 测试项 | 结果 | 详情 |
|--------|------|------|
| 反检测 | 待重新验证 | BotD 检测站已下线(404)，但未触发脉脉风控 |
| API 拦截 | 通过 | 成功拦截 8 个 XHR/Fetch 请求，4 个 JSON 响应 |
| Session 持久化 | 通过 | 13 cookies + 1 localStorage 完整保存和恢复，访问人才银行页面未被重定向 |

**脉脉首页拦截到的 API**:
- `maimai.cn/web/pingback` — 心跳
- `maimai.cn/sdk/jobs/get_ent_version` — 版本检测
- `maimai.cn/sdk/jobs/recruiter/spring_activity_pc_banner` — 招聘业务 API
- `ios-sentry.mm.taou.com/api/11/envelope/` — Sentry 监控

**注意**: 以上是未登录状态。登录后访问人才银行页面会暴露更多业务 API（搜索、候选人列表、详情），届时需要实际抓取分析。

**决策**:
- Playwright + stealth 作为**首选方案**，PoC 验证通过
- agent-browser 作为**备选**（已有集成但反检测能力一般）
- 反检测能力需在登录状态下进一步验证（计划用 fingerprint 检测站重新测试）
- 核心考虑：反检测能力 + MCP 集成难度 + 维护成本

**反爬策略（通用）**:
- 层级 1（必须）：行为伪装（随机间隔 3-8s、模拟鼠标轨迹、限制每日操作量）
- 层级 2（推荐）：环境隔离（指纹浏览器、代理 IP 轮换）
- 层级 3（必须）：降级策略（风控触发 → 暂停 → 通知用户 → 暂停当日任务）

### 难点 5：流程灵活性

#### 入口 1（候选人丰富模式）— 多匹配人选判定

**问题**: 用"姓名+公司"搜索时，可能查到多个同名候选人，如何判定目标人选？

**决策**:
- 自动优先：结合已有信息（职位、行业、城市、教育等）做置信度评分
- 兜底：人工参与选择（但会降低自动化能力）
- 目标：自动判定准确率 > 90%，减少人工介入

#### 入口 2（直接搜索模式）— 搜索条件取舍

**教训**: 之前实现脉脉人才银行复杂查询时，调试搜索控件耗费大量时间且效果不理想。

**决策**:
- 不死磕全部搜索条件，只实现**必要**的
- 考虑部分与人工查询结合的机制（人工设置复杂条件 → 自动执行搜索和提取）

---

## 三、Skill 架构设计（基于 Anthropic 最佳实践）

### Progressive Disclosure 三层加载

```
Layer 1: Metadata（始终在上下文，~100词）
  name + description → 触发机制

Layer 2: SKILL.md body（触发时加载，<500行）
  核心流程 + 场景→资源索引表

Layer 3: Bundled Resources（按需加载）
  references/（平台文档）、scripts/（自动化脚本）、assets/（模板）
```

### 目录结构（草案）

```
platform-match/
├── SKILL.md                          # 主入口（<500行）
├── scripts/                          # 可执行脚本
│   ├── search-maimai.py              # 脉脉搜索脚本
│   ├── extract-profile.py            # 人选信息提取
│   └── session-manager.py            # Session 管理
├── references/                       # 按需加载文档
│   ├── maimai/                       # 脉脉平台文档
│   │   ├── search-guide.md           # 搜索能力与操作指南
│   │   ├── anti-detect.md            # 反检测策略
│   │   └── api-interception.md       # API 拦截参考
│   ├── browser-tools.md              # 浏览器工具选型对比
│   └── matching-strategy.md          # 匹配判定策略
├── assets/                           # 输出模板
│   ├── candidate-list-template.md    # 候选人列表模板
│   └── match-report-template.md      # 匹配报告模板
└── evals/                            # 测试用例
    └── evals.json
```

### SKILL.md 设计要点

- description 只写触发条件，不写工作流（避免 Claude 走捷径）
- 包含具体触发短语（"匹配候选人"、"搜索脉脉"、"平台找人"等）
- 核心流程用步骤表 + 场景→资源索引表
- references/ 文件按场景索引，不一次性加载

---

## 四、合规边界

**法律依据**:
- 《个人信息保护法》(2021.11.1)
- 《数据安全法》(2021.9.1)
- 《网络数据安全管理条例》(2025.1.1)
- 前车之鉴：巧达科技案（非法爬取 2 亿简历，公司被查封）

**合规原则**:
- 公开数据都可以抓（职位、公司、工作经历等公开信息）
- 联系方式等敏感信息平台本身就不会展示给普通用户
- 控制请求频率，模拟正常用户行为
- 仅用于合法猎头业务，不转售或商业利用

---

## 五、脉脉 API 分析（2026-04-14 实测）

### 核心发现：搜索 API 可直接调用

**搜索端点**: `POST /api/ent/v3/search/basic?channel=www&is_mapping_pfs=1&version=1.0.0`

**请求体结构** (`search` 对象):
```json
{
  "query": "产品经理",          // 搜索关键词
  "search_query": "产品经理",   // 同 query
  "cities": "",                 // 城市筛选
  "companyscope": 0,            // 公司范围
  "degrees": "",                // 学历要求
  "positions": "",              // 职位名称
  "professions": "",            // 行业方向
  "schools": "",                // 毕业学校
  "worktimes": "",              // 工作年限
  "gender": "",                 // 性别
  "age": "",                    // 年龄
  "salary": "",                 // 期望月薪
  "major": "",                  // 专业
  "sortby": "0",                // 排序方式
  "query_relation": 0,          // 关键词关系
  "page": 0,                    // 页码
  "size": 30,                   // 每页数量（默认30）
  "data_version": "4.1",        // 数据版本
  "is_mapping_pfs": "",         // 职位匹配
  "sid": "pc_xxx",              // 会话 ID
  "sessionid": "pc_xxx",        // 会话 ID
  "highlight_exp": 1            // 高亮工作经验
}
```

**响应结构** (data 对象):
```json
{
  "total": 1000,           // 总匹配数
  "total_match": 1000,     // 总匹配数（同 total）
  "count": 30,             // 当前页返回数
  "list": [...],           // 候选人列表
  "to_uids": [...],        // 当前页 uid 列表
  "segment_words": [...]   // 搜索分词
  "banner": {}             // 广告
}
```

### 单个候选人字段结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 脉脉用户 ID（`dstu`） |
| `name` | string | 姓名 |
| `gender` / `gender_str` | int/string | 性别（1=男, 2=女） |
| `age` | int | 年龄 |
| `province` / `city` | string | 省份/城市 |
| `company` | string | 当前公司 |
| `position` | string | 当前职位 |
| `sdegree` / `degree` | string/int | 学历（硕士=2, 本科=1） |
| `major` | string | 专业 |
| `avatar` | string | 头像 URL |
| `active_state` | string | 活跃状态（"今日活跃"/"在线"） |
| `detail_url` | string | 详情页 URL |
| `exp[]` | array | 工作经历 |
| `edu[]` | array | 教育经历 |
| `job_preferences` | object | 求职意向 |
| `user_project[]` | array | 项目经历 |
| `tag_list[]` | array | 标签 |
| `exp_tags[]` | array | 经验标签 |
| `resume_tags[]` | array | 简历标签 |
| `hunting_status` | int | 求职状态（5=在看机会） |
| `worktime` | string | 工作年限（"4年7个月"） |
| `schools[]` | array | 教育经历简版 |

### 工作经历详情 (exp[])

| 字段 | 说明 |
|------|------|
| `company` | 公司名称 |
| `position` | 职位 |
| `v` | 时间段（"2021-09-01至今"） |
| `description` | 工作描述 |
| `tags[]` | 能力标签（["AI Agent", "AI产品"]） |
| `worktime` | 时长（"4年7个月"） |
| `company_info` | 公司信息（logo、链接等） |
| `score` | 评分 |

### 教育经历详情 (edu[])

| 字段 | 说明 |
|------|------|
| `school` | 学校名称 |
| `department` | 院系 |
| `degree` | 学历等级 |
| `sdegree` | 学历文本 |
| `v` | 时间段 |
| `school_level` | 学校级别（985/211/QS500等） |
| `hover` | 悬浮信息（排名、QS排名等） |

### 求职意向 (job_preferences)

| 字段 | 说明 |
|------|------|
| `positions[]` | 期望职位（["aigc产品经理", "AI产品经理"]） |
| `regions[]` | 期望城市（["北京", "浙江杭州"]） |
| `salary` | 期望薪资（"29k-35k/月"） |
| `prefessions[]` | 期望行业 |

### 搜索后关联 API

| API | 说明 | 数据量 |
|-----|------|--------|
| `/api/ent/card/console/dynamic` | 候选人动态 | 5.5KB |
| `/api/ent/discover/virtual_phone` | 虚拟电话状态 | 17KB |
| `/api/ent/card/console/intelligence/screen` | AI 智能筛选 | 13KB |
| `/sdk/jobs/workbench/cmf_and_colleague_info` | 同事/校友关系 | 2.8KB |
| `/sdk/jobs/get_job_search_sugs` | 搜索建议 | 小 |

### 关键结论

1. **API 拦截方案完全可行** — 搜索 API 返回完整的结构化 JSON，包含工作经历、教育经历、项目经历、求职意向
2. **不需要 DOM 提取** — API 返回的数据比 DOM 丰富得多，且格式稳定
3. **详情页 403** — 直接访问详情页被反爬拦截，但搜索 API 返回的数据已足够
4. **请求方式** — POST，body 为 `{"search": {...}}` 格式
5. **分页** — `page` + `size` 参数控制
6. **筛选条件** — 13 个筛选维度（城市、学历、年限、公司、职位、行业、学校、专业、性别、年龄、薪资、家乡、关键词关系）

---

## 六、架构决策（讨论确认）

### 决策 1：搜索条件 — 全部维度可用，无技术障碍

API 抓取结果表明：搜索条件只是 JSON 字段，不需要 DOM 控件操作。原 FormFiller 模块可废弃。

**实现方式**：所有 13 个维度通过 API 请求体直接传参，SKILL.md 提供常用组合模板。

### 决策 2：三种执行模式

| 模式 | 触发方式 | 输入 | 流程 |
|------|---------|------|------|
| **候选丰富** | `/platform-match --candidates <filter>` | public-search 候选人列表 | 逐个搜索匹配 → 提取信息 → 更新人才库 |
| **JD 驱动** | `/platform-match --jd <id\|file>` | JD 文本 | 提取搜索条件 → 生成多组搜索 → 展示计划 → 执行 |
| **对话式** | `/platform-match` 或自然语言 | 用户描述搜索需求 | Claude 生成请求体 → 用户确认 → 执行 |

**人工介入点**：搜索计划确认、多匹配人工选择、异常处理。

### 决策 3：多匹配判定 + 业务 know-how 可扩展

**判定流程**：

```
精确匹配 (company+position 完全一致) → 置信度 95% → 自动选取
    ↓ 失败
模糊匹配 (company 一致 + position 相似) → 置信度 70-90% → 自动选取
    ↓ 失败
多维度综合评分 → 置信度 60-80% → 自动选取
    ↓ 失败
置信度相近且 < 60% → 暂存为"待确认" → 人工复核
```

**业务 know-how 扩展机制**：

判定策略之后，追加业务 know-how 规则用于排序优先级和筛选过滤。这些规则是**经验性的、不断积累的**，需要保留扩展灵活性：

- 存放位置：`rules/match-rules.md`（纯文本规则文件，Claude 按需读取）
- 规则格式：自然语言描述，Claude 理解并执行（不需要代码化）
- 示例：
  ```
  - 同公司候选人优先按工作年限降序
  - 有竞品公司经验的候选人标记高潜
  - 活跃状态 > 3 天未活跃的降低优先级
  - XX 行业候选人关注是否有海外背景
  ```
- 优点：不需要写代码，随业务发展持续追加即可
- 触发时机：判定完成后、输出排序时读取

---

## 七、待办 / 下一步

- [x] 探索脉脉非会员页面的搜索能力 → 不可用，锁定会员人才银行页面
- [x] 完成浏览器工具选型评估 → Playwright + stealth PoC 通过，作为首选方案
- [ ] 标记三月份设计文档为作废
- [x] 脉脉 API 分析 — 搜索 API 可直接调用，返回完整结构化数据
- [x] 设计多匹配人选自动判定策略
- [x] 确定"必要搜索条件"的最小集合 — 全部维度可用，无技术障碍
- [x] 设计人工+AI 混合查询机制 — 三种执行模式
- [x] 业务 know-how 扩展机制 — rules/match-rules.md 自然语言规则文件
- [ ] 按 Anthropic 最佳实践编写新 SKILL.md

---

## 八、待解决的设计缺口

### 缺口 1：端到端数据流（高优）

各环节数据格式未完全对齐：

```
public-search 输出                    platform-match 需要
─────────────────                    ──────────────────
name, current_company, current_title   → query（搜索关键词拼接）
city, skill_tags, sources             → 候选人丰富（写入 candidates/）
JD 文本/搜索策略                      → 搜索条件（cities, worktimes 等）

搜索 API 返回                         → 写入 candidates/ 的字段
name, company, position, exp, edu...   → 和 candidate.schema.json 的对齐
```

**待确认**：
- `data-manager.py` 的 `candidate create/update` 命令是否满足写入需求？
- API 返回字段与 `candidate.schema.json` 之间有无 gap？
- 输出文件格式（md/excel）的模板长什么样？

### 缺口 2：候选丰富模式的关联逻辑（高优）

public-search 给了 `{name, company, title}`，去脉脉搜时：
- 搜索关键词怎么拼接？`"张三 阿里巴巴"` 还是分开填 `query` + `companyscope`？
- 搜到多个结果时，怎么把 API 返回的 `id` 和本地候选人记录关联？
- 关联键是 `name + company`？还需要 fuzzy match？

### 缺口 3：CDP 依赖和降级（中优）

- skill 依赖 chrome-cdp skill + 用户开启 Chrome 调试端口
- 降级方案：导出 cookies → Playwright 脚本（增加复杂度）
- 是否值得做降级？还是直接要求用户装 chrome-cdp？

### 缺口 4：频率控制策略（中优）

- 批量搜索 100 个候选人，每次间隔多久？
- 每日上限多少次搜索？脉脉的 visible rate limit 是什么？

### 缺口 5：错误处理（低优）

- Session 过期 → 提示用户重新登录
- API 报错 code ≠ 0 → 记录日志跳过
- 搜索 0 结果 → 标记为"未找到"

### 缺口 6：skill 间衔接（低优）

- platform-match 输出 → screen skill 输入格式
- platform-match 输出 → report skill 数据来源
