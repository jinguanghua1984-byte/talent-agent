# Talent-agent 场景调研：Cold Email Outreach + 人选跟进

> 日期：2026-04-16
> 关联任务：T078
> 状态：调研完成，待设计

## 1. 背景

Talent-agent 当前 pipeline 覆盖了「寻源→匹配→评估→推荐」：

```
public-search → platform-match → screen → report
```

**缺失环节：** report 之后，猎头需要手动触达候选人并持续跟进。这是整个链路中最耗时（占猎头 30-40% 工作时间）、最容易出错的环节。

本调研覆盖两个新场景：
1. **Cold Email Outreach** — 触达候选人
2. **Candidate Follow-up** — 持续跟进直到成单

## 2. 场景一：Cold Email Outreach

### 2.1 痛点

- 候选人分散在多个平台（脉脉、Boss直聘、猎聘、LinkedIn），往往没有直接邮箱
- 中文邮件需要文化校准（正式度、关系优先）
- 无系统性追踪谁被联系过、什么时候、什么结果
- 通用触达回复率持续下降（2020-2022 年 7-8%，2024-2025 年 4-5.8%）

### 2.2 核心功能

#### 2.2.1 联系方式发现

| 功能 | 技术方案 |
|------|---------|
| 邮箱模式推断 | firstName.lastName@ / firstlast@ / flast@ + SMTP 验证 |
| 平台联系方式 | 脉脉/Boss直聘/猎聘 API 或抓取 + 微信连接流 |
| LinkedIn 导出 | Sales Navigator 或 PhantomBuster |
| 微信桥接 | 已有 WeChat MCP 集成 |

#### 2.2.2 AI 邮件撰写

**已有资产：** `cold-email` skill（11 种框架 + benchmark 数据 + 个性化系统）

输入：候选人 profile（来自 screen 阶段）+ JD + 猎头/客户上下文
输出：个性化中文/英文邮件

**中国市场文化校准：**

| 因素 | 调整方向 |
|------|---------|
| 语气 | 初始用「您」，关系优先 |
| 结构 | 先建立共同语境，再推销 |
| CTA | 低摩擦：「方便聊聊吗？」而非「约个 30 分钟电话」 |
| 标题 | 短且无聊：「关于XX岗位」（2-4 字最好，Lavender 数据显示 2 字标题打开率高 60%） |
| 跟进渠道 | 微信 > 邮件 |

#### 2.2.3 发送基础设施

| 组件 | 推荐方案 |
|------|---------|
| 发送 API | Resend（开发者友好）或 SendGrid（规模） |
| 域名 | 自定义域名 + 预热 |
| 预热工具 | Smartlead.ai（无限邮箱 + 内置预热） |
| DNS | SPF + DKIM + DMARC + rDNS |
| 量级爬坡 | W1: 5-10/天, W2: 15-20/天, W3: 30-40/天 |

#### 2.2.4 邮件追踪

| 追踪项 | 技术实现 |
|--------|---------|
| 打开率 | 1x1 追踪像素（唯一 ID）嵌入 HTML |
| 点击追踪 | 包装重定向链接 |
| 回复检测 | IMAP webhook 监听 In-Reply-To 头 |
| 退信处理 | SendGrid event webhooks |
| 投递状态 | delivered / deferred / bounced / spam |

#### 2.2.5 A/B 测试

| 测试变量 | 预期影响 |
|----------|---------|
| 标题长度 | 2 字 vs 5-8 字（+60% 打开） |
| 个性化深度 | Level 1 vs Level 3-4（+50-250% 回复） |
| Hook 类型 | Timeline hook（3.4x 更易获得会议） |
| 邮件长度 | <75 字（+83% 回复） |
| 发送时间 | 周四 9-11AM（6.87% 回复率峰值） |

### 2.3 市场工具

| 工具 | 功能 | 价格 |
|------|------|------|
| **Gem** | AI sourcing + 邮件个性化 + 自动跟进 + send-on-behalf-of | $135-2000+/mo |
| **hireEZ** | AI sourcing + 自动 campaign + EZGPT 邮件生成 + CRM | 企业定价 |
| **Smartlead** | 冷邮件基础设施：无限邮箱 + 预热 + 多序列 | $39-94/mo |
| **Lyne.ai** | AI 个性化开场白批量生成 | ~$120/mo |
| **Lavender** | 实时邮件评分 + coaching | $29-89/user/mo |

## 3. 场景二：人选跟进

### 3.1 痛点

- 猎头同时管理 30-50 个活跃候选人，跟进混乱
- 候选人容易掉出漏斗（不跟进 = 丢失成单）
- 多渠道协调（邮件 + 微信 + 电话）手动且易出错
- 无数据支撑最优跟进节奏

**中国市场特殊性：**
- 微信是主导跟进渠道（不是邮件）
- 脉脉私信也用于专业跟进
- 候选人期望更快的回复速度（几小时内，不是几天）
- 关系建设 > 交易式沟通

### 3.2 核心功能

#### 3.2.1 候选人状态管线

```
SOURCED → CONTACTED → RESPONDED → INTERESTED →
INTERVIEWING → OFFER → PLACED → OFFBOARDING

分支：
  RESPONDED → NOT_INTERESTED（归档）
  INTERESTED → GHOSTED（重入培育）
  OFFER → REJECTED → 回到 INTERVIEWING
  PLACED → GUARANTEE_PERIOD → COMPLETED
```

每次状态转换记录：时间戳、渠道、消息内容、触发自动跟进规则。

#### 3.2.2 跟进节奏系统

| 阶段 | 时机 | 渠道优先级（中国） |
|------|------|-------------------|
| 初次发送后 | Day 3 | 微信 > 邮件 |
| 第二次跟进 | Day 7-8 | 微信 > 电话 |
| 第三次跟进 | Day 14 | 电话 > 微信 |
| 结束/归档 | Day 21-28 | 微信（礼貌结束） |
| 面试后 | 24h 内 | 微信 > 电话 |
| Offer 后 | 24h 内 | 微信 > 电话 |
| 保证期内 | 每周 check-in | 微信 > 电话 |
| 重新激活（休眠） | 30-60 天 | 微信 |

**中国市场关键规则：**
- 微信消息要有对话感，不能像自动化
- 不要同时在多个渠道发相同消息
- 电话在中国比西方更被接受
- Boss直聘消息有平台频率限制

#### 3.2.3 自动提醒触发

| 触发事件 | 自动动作 |
|----------|---------|
| 邮件发送 48h 未打开 | 考虑微信跟进 |
| 邮件打开 3 天未回复 | 发 Follow-up 1 |
| 候选人回复「感兴趣」 | 提醒猎头，准备面试材料 |
| 候选人回复「暂时不考虑」 | 3 个月后重新激活 |
| 面试已排期 | 发准备材料 + 日历提醒 |
| 面试完成 | 24h 内跟进反馈 |
| 14 天无活动 | 「休眠候选人」告警 |

#### 3.2.4 多渠道协调

核心设计：一个候选人的交互历史应跨所有渠道。

```
候选人：张伟
├── 邮件：zhang.wei@company.com
│   ├── 04-16 冷邮件发送（追踪：04-16 14:32 打开）
│   └── 04-19 Follow-up 1（未打开）
├── 微信：zhangwei_wx
│   ├── 04-22 「张总您好，之前给您发过邮件...」（回复：感兴趣）
│   └── 04-23 电话面试排期
├── 脉脉
│   └── 04-10 查看主页，发送连接请求
└── Boss直聘
    └── 04-09 初始聊天消息
```

实现：统一候选人记录 + 渠道消息日志 + 「下一步动作」字段 + 渠道偏好自动检测。

### 3.3 市场工具

| 工具 | 跟进功能 | 中国支持 | 价格 |
|------|---------|---------|------|
| **谷露 CRM** | 企业微信小程序 + ATS + 人才库 | 原生中国 | 企业定价 |
| **liex2** | 简历管理 + 推荐报告 + 过程追踪 | 原生中国 | 企业定价 |
| **Gem** | 自动序列 + AI 个性化 + 响应追踪 | 有限 | $135-2000+/mo |
| **hireEZ CRM** | 自动 campaign + 人才池培育 | 有限 | 企业定价 |
| **Ashby** | Pipeline 可视化 + 自定义阶段 + AI 助手 | 有限 | 企业定价 |

## 4. 集成设计：完整 Pipeline

```
1. PLATFORM-MATCH（已完成 FEAT-012）
   └── 搜索匹配候选人

2. SCREEN（待开发 FEAT-013）
   └── 深度评估 + 评分

3. REPORT（待开发 FEAT-014）
   └── 生成推荐报告

4. EMAIL OUTREACH（新场景）
   ├── 联系方式发现
   ├── AI 撰写个性化邮件（复用 cold-email skill）
   ├── 发送 + 追踪
   └── 输出：已触达候选人 + 追踪 ID

5. FOLLOW-UP（新场景）
   ├── 自动跟进节奏（Day 3/7/14/21）
   ├── 多渠道协调（邮件 + 微信 + 电话）
   ├── 状态管线追踪
   ├── 智能提醒
   └── 输出：转化分析 + 成单追踪
```

## 5. 已有可复用资产

| 资产 | 位置 | 覆盖范围 |
|------|------|---------|
| cold-email skill | `.claude/skills/cold-email/` | 11 框架 + benchmark + 个性化系统，邮件撰写 80% 已解决 |
| email-sequence skill | `.claude/skills/email-sequence/` | 节奏设计 + 时序 + 触发自动化 |
| WeChat MCP | `wechat-channel` | 微信收发消息，中国跟进主渠道 |
| benchmark 数据 | `cold-email/benchmarks.md` | 打开率/回复率/转化漏斗/资历/行业数据 |

**真正缺失的是基础设施**：发送引擎、追踪像素、状态管理、多渠道日志。

## 6. 实施优先级建议

| 优先级 | 功能 | 工作量 | 影响 |
|--------|------|--------|------|
| **P0** | 邮件撰写（复用 cold-email skill） | 低 | 高 — 立即可用 |
| **P0** | 基础状态追踪（contacted/responded/interested） | 中 | 高 — 防止候选人掉漏斗 |
| **P1** | 邮件发送 + 追踪像素 + 点击追踪 | 中 | 高 — 可见性 |
| **P1** | 跟进节奏引擎（定时触发） | 中 | 高 — 自动化最手动环节 |
| **P2** | 微信跟进集成（已有 WeChat MCP） | 低-中 | 很高 — 中国市场 |
| **P2** | 多渠道消息日志 | 中 | 高 — 统一历史 |
| **P3** | A/B 测试框架 | 中 | 中 — 长期优化 |
| **P3** | 邮箱发现/推断 | 中-高 | 高 — 冷触达 |
| **P3** | 分析 Dashboard | 中 | 中 — 数据驱动优化 |

## 7. 参考资料

- [Gem Pricing](https://www.gem.com/pricing)
- [hireEZ Automated Campaigns](https://hireez.com/automated-campaigns/)
- [AI Outreach Personalization - Metaview](https://www.metaview.ai/resources/blog/personalize-recruiting-outreach-emails)
- [Candidate Sourcing Email Templates - Prospeo](https://prospeo.io/s/candidate-sourcing-email-template)
- [12 Top AI Candidate Outreach Platforms - Metaview](https://www.metaview.ai/resources/blog/ai-candidate-outreach-platforms)
- [Lyne.ai Personalization Framework](https://lyne.ai/how-to-personalize-a-cold-email-5-step-framework/)
- [谷露招聘CRM](https://cn.gllue.com/news_gllue_recruitment_crm/)
- [liex2 猎头管理系统](https://www.liex2.com/)
- [Cold Mail 开发信优化 - 知乎](https://zhuanlan.zhihu.com/p/403913722)
- [Recruiting Email Templates - RecruitCRM](https://recruitcrm.io/zh-hans/blogs/recruiting-email-templates/)
