# 公域搜索渠道参考

本文档定义公域搜索中可用的渠道及其使用方法。根据候选人类型选择最合适的渠道组合。

## 渠道总览

| 渠道 | 适用候选人 | 信息丰富度 | 访问难度 | 推荐优先级 |
|------|-----------|-----------|---------|-----------|
| Google | 所有类型 | 中 | 低 | 始终使用 |
| GitHub | 开发者、技术Leader | 高 | 低 | 技术岗首选 |
| Google Scholar / 知网 | 学术论文作者 | 高 | 低 | 学术/研究岗 |
| LinkedIn (公开资料) | 职场人士 | 高 | 中 | 职能/管理岗 |
| 技术社区 (掘金/CSDN/StackOverflow) | 技术博客作者 | 中 | 低 | 技术岗辅助 |
| 个人主页/博客 | 独立开发者、创业者 | 高 | 低 | 创业者/独立开发者 |
| 行业媒体 (36氪/虎嗅) | 创业者、高管 | 中 | 低 | 高管/创业者 |

---

## 1. Google

**适用场景**: 所有类型的候选人搜索，通用起点。

**搜索语法示例**:

```
# 基础搜索
"CTO" "字节跳动" site:linkedin.com
"技术总监" "阿里巴巴" -招聘 -job

# 组合搜索
"Go语言" "架构师" "北京" (resume | CV | 简历)

# 排除干扰
"张三" "腾讯" -招聘 -job -招聘网
"AI研究员" "百度" -论文 -招聘

# 英文搜索（外企/海外候选人）
"Senior Engineer" "ByteDance" site:linkedin.com
"VP Engineering" "TikTok" -job -hiring
```

**信息提取要点**:
- 姓名 + 公司 + 职位的基础组合
- 排除招聘信息（-招聘 -job -hiring）
- 使用引号精确匹配关键词
- site: 限定特定平台
- 注意区分同名不同人

---

## 2. GitHub

**适用场景**: 开发者、技术 Leader、开源贡献者。

**搜索语法示例**:

```
# 按公司搜索
org:bytedance language:go
org:alibaba location:Beijing

# 按技术栈搜索
language:rust "distributed systems" followers:>50
language:go "microservices" location:Shanghai

# 按仓库搜索贡献者
# 先找到目标公司/项目仓库，再查看活跃贡献者
repo:bytedance/sonic contributors
repo:alibaba/druid contributors
```

**信息提取要点**:
- 用户名、真实姓名（profile）、所在地
- 当前/曾经所属组织（org membership）
- 技术栈（常用语言、starred repos）
- 活跃度（contributions、commit 频率）
- 开源影响力（followers、popular repos）
- 注意：GitHub 信息需交叉验证，用户名不等于真实姓名

**数据获取方式**:
- 使用 `mcp__github__search_users` 搜索用户
- 使用 `mcp__github__search_code` 搜索代码确认技术栈
- 搜索结果 URL 作为 source

---

## 3. Google Scholar / 知网

**适用场景**: 学术论文作者、研究员、AI/算法方向候选人。

**搜索语法示例**:

```
# Google Scholar
author:"张三" "deep learning" institution:"清华大学"
"large language model" author:"李四" site:scholar.google.com

# 知网
# 通过 WebSearch 搜索知网收录的论文
site:cnki.net "张三" "自然语言处理"
```

**信息提取要点**:
- 作者姓名、所属机构
- 研究方向（论文主题、关键词）
- 学术影响力（引用量、h-index）
- 合作网络（共同作者）
- 注意：论文发表单位不一定是当前工作单位

---

## 4. LinkedIn (公开资料)

**适用场景**: 职场人士、管理层、外企候选人。

**搜索语法示例**:

```
# Google 搜索 LinkedIn 公开资料
site:linkedin.com/in "Product Manager" "字节跳动"
site:linkedin.com/in "Engineering Manager" "北京"
site:linkedin.com/in "VP" "AI" "中国"

# 英文关键词
site:linkedin.com/in "Staff Engineer" "Bytedance"
site:linkedin.com/in "CTO" "startup" "Shanghai"
```

**信息提取要点**:
- 姓名、当前职位、公司
- 工作经历（公开摘要部分）
- 教育背景
- 所在城市
- 注意：LinkedIn 公开资料信息有限，可能需要配合其他渠道
- 注意：部分 LinkedIn 页面需要登录才能查看完整信息

---

## 5. 技术社区 (掘金/CSDN/StackOverflow)

**适用场景**: 技术博客作者、活跃的技术社区成员。

**搜索语法示例**:

```
# 掘金
site:juejin.cn "分布式架构" "字节跳动"
site:juejin.cn "Go语言" "微服务"

# CSDN
site:csdn.net "机器学习" "百度" 博客

# StackOverflow
site:stackoverflow.com/users "China" "python" "distributed"
```

**信息提取要点**:
- 作者昵称、真实姓名（如有）
- 技术方向（文章/回答主题）
- 技术深度（文章质量、回答投票数）
- 所在公司（profile 信息）
- 注意：社区昵称需交叉验证身份

---

## 6. 个人主页/博客

**适用场景**: 独立开发者、创业者、技术意见领袖。

**搜索语法示例**:

```
# 搜索个人主页
"关于我" "全栈工程师" "北京" -招聘
"个人博客" "AI创业者" "上海"
"About Me" "indie hacker" "China"

# 搜索独立作品
"独立开发" "App Store" "开发者"
"开源项目" "创始人" -公司
```

**信息提取要点**:
- 姓名、自我介绍
- 当前项目/公司
- 技能栈
- 联系方式
- 注意：个人主页信息可能过时，需验证时效性

---

## 7. 行业媒体 (36氪/虎嗅)

**适用场景**: 创业者、高管、被报道的技术负责人。

**搜索语法示例**:

```
# 36氪
site:36kr.com "CTO" "字节跳动"
site:36kr.com "创始人" "AI"

# 虎嗅
site:huxiu.com "技术负责人" "腾讯"
site:huxiu.com "VP" "电商"

# 通用媒体搜索
"独家报道" "技术VP" "公司名"
"专访" "CTO" "行业关键词"
```

**信息提取要点**:
- 被报道者的姓名、职位、公司
- 专业领域和成就
- 行业影响力
- 注意：媒体报道可能有滞后，需确认当前状态

---

## 渠道选择策略

根据搜索意图选择渠道组合：

| 候选人类型 | 首选渠道 | 辅助渠道 |
|-----------|---------|---------|
| 后端/前端开发 | GitHub, Google | 技术社区, LinkedIn |
| 技术Leader/架构师 | Google, LinkedIn, GitHub | 行业媒体, 技术社区 |
| AI/算法工程师 | Google Scholar, GitHub | Google, 技术社区 |
| 产品经理 | LinkedIn, Google | 行业媒体 |
| 创业者/高管 | 行业媒体, Google, LinkedIn | 个人主页 |
| 学术/研究员 | Google Scholar, 知网 | Google |

## 注意事项

1. **信息时效性**: 公域搜索到的信息可能不是最新的，标注发现时间
2. **信息准确性**: 交叉验证多个来源，避免被误导
3. **隐私边界**: 只收集公开可访问的信息，不尝试绕过登录限制
4. **同名处理**: 同名候选人需通过公司、技术栈等维度区分
5. **去重**: 同一候选人可能出现在多个渠道，合并而非重复记录
