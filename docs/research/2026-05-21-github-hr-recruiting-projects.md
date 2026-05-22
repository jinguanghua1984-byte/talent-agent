# GitHub 猎头/HR 相关高星开源项目调研

> 调研日期：2026-05-21 | 覆盖 6 大场景，筛选标准：GitHub stars、活跃度、功能独特性

---

## 场景一：简历评估 / 粗筛和精排

### 1. Resume Matcher — ⭐ 27,105

- **仓库**：[srbhr/Resume-Matcher](https://github.com/srbhr/Resume-Matcher)
- **核心能力**：AI 驱动的简历-JD 匹配引擎。解析简历 PDF → 提取关键词 → 与职位描述做向量相似度计算 → 输出匹配评分和差距分析。支持本地 AI 和云端 API 两种模式。
- **差异化亮点**：
  - 真正的语义匹配（向量搜索 + 词嵌入），非简单关键词命中
  - 同时支持 Python 和 Next.js 前端，可视化匹配结果
  - Apache-2.0 许可证，商用友好
  - 社区极度活跃（4,839 forks），GitHub Topic 标签覆盖 ATS/NLP/向量搜索
- **vs 同类**：大多数简历分析器只做关键词提取 + ATS 评分，Resume Matcher 做到了语义层面的"匹配度理解"。劣势是面向求职者视角设计，猎头侧批量处理能力需自行扩展。
- **重要信息**：TypeScript + Python 双栈，4,839 forks，56 个 open issues，持续活跃更新。

### 2. AI-Resume-Analyzer (deepakpadhi986) — ⭐ 852

- **仓库**：[deepakpadhi986/AI-Resume-Analyzer](https://github.com/deepakpadhi986/AI-Resume-Analyzer)
- **核心能力**：NLP 驱动的简历解析 + 技能聚类 + 行业分类 + 推荐预测。将非结构化简历数据转为结构化技能标签，按行业聚类。
- **差异化亮点**：
  - 自动将简历技能聚类到行业赛道（sector clustering）
  - 提供求职者视角的推荐和预测分析
  - Python + Streamlit，部署简单
- **vs 同类**：比 Resume Matcher 更偏"简历理解"而非"JD 匹配"。适合作为猎头系统的简历解析预处理层。劣势：技术栈较老，NLP 模型非 LLM。
- **重要信息**：MIT 许可证，Python，231 forks，适合二次开发。

### 3. AI-Recruitment-Agent (Ancastal) — ⭐ 41

- **仓库**：[Ancastal/AI-Recruitment-Agent](https://github.com/Ancastal/AI-Recruitment-Agent)
- **核心能力**：基于 Microsoft AutoGen 的多 Agent 招聘助手。多个专业 AI Agent 协同工作：简历筛选 Agent、候选人评估 Agent、面试准备 Agent。
- **差异化亮点**：
  - 多 Agent 协作架构（AutoGen 框架），模拟真实招聘团队分工
  - 每个 Agent 职责明确：screening → evaluation → interview prep
  - 真正的"招聘流程自动化"而非单点工具
- **vs 同类**：不是又一个简历分析器，而是一套完整的多 Agent 招聘编排系统。劣势：star 数低，代码较新（2025.02），生产级可靠性待验证。
- **重要信息**：Python + AutoGen，MIT 许可证。

### 4. Smart-AI-Resume-Analyzer — ⭐ 216

- **仓库**：[Hunterdii/Smart-AI-Resume-Analyzer](https://github.com/Hunterdii/Smart-AI-Resume-Analyzer)
- **核心能力**：一站式简历分析器：ATS 兼容性检测 + 专业模板生成 + AI 驱动优化建议。提供完整的 Dashboard 界面。
- **差异化亮点**：
  - 内置 ATS 兼容性检测（ATS-friendly analysis）
  - 提供可视化 Dashboard（Streamlit）
  - 包含简历模板库 + 反馈表单 + 课程推荐
- **vs 同类**：功能最全面的一站式方案，但更偏向求职者自助工具而非猎头系统。
- **重要信息**：C 语言 + Python（Streamlit），78 forks，MIT 许可证。

### 5. Resume-Analyzer (Anubhav-Goyal01) — ⭐ 较新

- **仓库**：[Anubhav-Goyal01/Resume-Analyzer](https://github.com/Anubhav-Goyal01/Resume-Analyzer)
- **核心能力**：基于 OpenAI GPT + LangGraph + Azure AI Document Intelligence 的简历解析和排序系统。支持按 JD 自动排序候选人。
- **差异化亮点**：
  - 使用 LangGraph 构建有状态的简历分析工作流
  - Azure AI Document Intelligence 做文档解析（比 PyPDF 准确率高）
  - GPT 模型做语义理解和排序
- **vs 同类**：技术栈最现代（LangGraph + GPT + Azure DI），适合需要高准确率简历解析的场景。
- **重要信息**：Python，企业级组件组合。

---

## 场景二：简历优化 / 定向简历完善 / 定制化简历生成

### 1. Reactive Resume — ⭐ 37,759

- **仓库**：[amruthpillai/reactive-resume](https://github.com/amruthpillai/reactive-resume)
- **核心能力**：开源简历构建器标杆。拖拽式编辑器 + 多模板 + 实时预览 + PDF 导出。无需注册即可使用，完全自托管。
- **差异化亮点**：
  - **GitHub 同类项目 star 数断层第一**（37,759 vs 第二名 27,105）
  - 自托管、隐私优先、无需账号
  - TypeScript + React + TailwindCSS 现代技术栈
  - 支持多语言、自定义字体、OpenAI 集成
- **vs 同类**：OpenResume (8,618 stars) 功能类似但无 AI 能力。Reactive Resume v4 已集成 OpenAI 做内容优化建议。劣势：面向求职者设计，缺少批量处理和猎头管理视角。
- **重要信息**：MIT 许可证，4,263 forks，72 open issues，持续活跃。**如果要基于开源项目做猎头简历工具，这是最佳基座**。

### 2. OpenResume — ⭐ 8,618

- **仓库**：[xitanggg/open-resume](https://github.com/xitanggg/open-resume)
- **核心能力**：开源简历构建器 + ATS 解析器双重功能。不仅能创建简历，还内置 ATS 解析器验证简历的 ATS 兼容性。
- **差异化亮点**：
  - 独有的**内置 ATS 解析器**（Resume Parser），可在创建简历的同时验证 ATS 可读性
  - 纯前端实现，无需后端（Next.js + React）
  - 拖拽排序、实时预览、多种模板
- **vs 同类**：与 Reactive Resume 相比少了 AI 能力和自托管的灵活性，但多了一个独特的 ATS 解析验证功能。对猎头而言，这个 ATS 验证器可直接用来预检候选人简历。
- **重要信息**：AGPL-3.0 许可证（注意商用限制），TypeScript，994 forks。

### 3. JadeAI — ⭐ 1,649

- **仓库**：[LingyiChen-AI/JadeAI](https://github.com/LingyiChen-AI/JadeAI)
- **核心能力**：AI 驱动的智能简历构建器。50+ 专业模板 + PDF/图片解析 + AI 优化 + JD 匹配分析 + 多格式导出。Docker 一键部署。
- **差异化亮点**：
  - **50+ 专业模板**，同类开源项目中最丰富
  - 支持从 PDF 和图片直接解析简历（OCR）
  - 内置 JD 匹配分析功能（不仅构建简历，还能针对目标职位优化）
  - Docker 一键部署，对企业友好
- **vs 同类**：模板数量远超 Reactive Resume 和 OpenResume。JD 匹配分析是独特的猎头侧功能。劣势：社区规模较小（180 forks vs Reactive Resume 的 4,263）。
- **重要信息**：Apache-2.0 许可证，TypeScript，3 个 open issues，2026 年仍活跃。

### 4. Resume-Builder (jananthan30) — ⭐ 43

- **仓库**：[jananthan30/Resume-Builder](https://github.com/jananthan30/Resume-Builder)
- **核心能力**：Claude Code 插件式简历生成器。双 ATS + HR 评分系统，支持任意职业。输入个人信息和目标 JD，自动生成优化简历和 Cover Letter。
- **差异化亮点**：
  - **Claude Code 原生插件**，可直接在 Claude Code 中调用
  - **双评分系统**：ATS 评分 + HR 评分（模拟双重筛选视角）
  - 适用于任意职业（非仅 tech）
- **vs 同类**：唯一一个作为 AI 编码助手插件存在的简历工具。评分系统设计思路（ATS + HR 双维度）对猎头有直接参考价值。劣势：star 数低，功能较新。
- **重要信息**：Python，MIT 许可证，Claude Code Plugin。

### 5. cv-generator (destbreso) — ⭐ 较新

- **仓库**：[destbreso/cv-generator](https://github.com/destbreso/cv-generator)
- **核心能力**：AI 简历构建器，核心理念是"Build once, tailor infinitely"——一次构建基础简历，无限次针对不同职位定制。
- **差异化亮点**：
  - **隐私优先设计**（Privacy-first），数据不离开本地
  - "一次构建 + 无限定制"的工作流，天然适合猎头为候选人定制简历场景
  - TypeScript 实现，完全免费开源
- **vs 同类**：定位最接近猎头"简历定制化"需求。与 Reactive Resume 的通用构建不同，cv-generator 专注于"基础简历 → 多版本定制"的工作流。
- **重要信息**：MIT 许可证，TypeScript。

---

## 场景三：寻访策略 / 自动寻访

### 1. linkedin-sourcing-ai — ⭐ 较新

- **仓库**：[Aadesh998/linkedin-sourcing-ai](https://github.com/Aadesh998/linkedin-sourcing-ai)
- **核心能力**：自主 AI Agent 自动化 LinkedIn 人才寻访。大规模自动搜索 LinkedIn Profile → 自定义匹配度算法评估候选人 → 生成个性化触达消息。
- **差异化亮点**：
  - **唯一真正的开源 LinkedIn 自动寻访工具**
  - 自定义 Fit Score 算法（非简单关键词匹配）
  - 自动生成个性化 Outreach 消息
  - 端到端自动化：搜索 → 评估 → 触达
- **vs 同类**：市面上几乎没有开源的 LinkedIn sourcing 工具（商业工具有 HireEZ、SeekOut 等）。劣势：LinkedIn 反爬限制可能影响实用性，需注意合规风险。
- **重要信息**：TypeScript，2025 年创建。

### 2. AI-Recruitment-Agent (Ancastal) — ⭐ 41

- 已在"简历评估"场景介绍。其多 Agent 架构中的 Screening Agent 可自动执行简历初筛，模拟寻访流程中的初步过滤。

### 3. Multiagent-Recruitment (ARYA) — ⭐ 较新

- **仓库**：[mohamedamineelabidi/Multiagent-Recruitment](https://github.com/mohamedamineelabidi/Multiagent-Recruitment)
- **核心能力**：ARYA (AI Recruitment & Yield Assessment) 企业级 API 平台。多 Agent 架构自动化候选人评估工作流。
- **差异化亮点**：
  - **企业级 API 平台设计**（非 demo/玩具项目）
  - 多 Agent 评估流程，支持复杂招聘场景
  - Azure 集成，适合企业环境
- **vs 同类**：架构设计最接近企业生产环境。劣势：文档较少，社区规模小。

### 4. RecruitmentAgent-AI — ⭐ 较新

- **仓库**：[hari7261/RecruitmentAgent-AI](https://github.com/hari7261/RecruitmentAgent-AI)
- **核心能力**：智能招聘平台：AI 简历分析 + 自动邮件沟通 + 视频面试排期集成。
- **差异化亮点**：
  - 自动化邮件沟通（候选人触达自动化）
  - 视频面试排期集成
  - 完整的寻访 → 触达 → 面试编排

### 5. HR-Buddy — ⭐ 较新

- **仓库**：[skandvj/HR-Buddy-AI-Assistant-for-Recruitment](https://github.com/skandvj/HR-Buddy-AI-Assistant-for-Recruitment)
- **核心能力**：基于 LangGraph 的 Agentic 招聘编排器。自动化招聘工作流 + JD 优化 + 战略招聘计划生成。带状态记忆。
- **差异化亮点**：
  - **LangGraph 有状态工作流**，支持复杂的招聘流程编排
  - JD 优化功能（帮助猎头/HR 写出更好的职位描述）
  - 战略招聘计划生成（Strategic Hiring Plan）
  - 有状态记忆（跨会话保留招聘上下文）
- **重要信息**：Python，LangGraph 架构。

---

## 场景四：职位需求深挖 / 目标人才画像

> **坦率说明**：GitHub 上专门做"职位需求深挖 / 人才画像"的开源项目极少，这更多是商业 SaaS（如 HireEZ、SeekOut、Eightfold）的领域。以下项目在相关能力上有独特价值。

### 1. Resume Matcher — ⭐ 27,105

- 已在场景一介绍。其语义匹配能力可反向使用：从 JD 提取人才画像需求 → 量化技能要求 → 自动生成候选人评估标准。

### 2. HR-Buddy (LangGraph) — ⭐ 较新

- 已在场景三介绍。JD 优化功能本质上是"职位需求深挖"——将模糊的 JD 需求转化为结构化的技能要求和评估维度。

### 3. hound-system-v0.1 — ⭐ 较新

- **仓库**：[FeixueCode/hound-system-v0.1](https://github.com/FeixueCode/hound-system-v0.1)
- **核心能力**：AI 招聘助手，设计理念独特——"不打分，只数命中"。三层独立评估（任务/能力/事件）+ HR vs 用人部门双维议事。
- **差异化亮点**：
  - **唯一中英文双语**的招聘 AI 工具
  - "数命中不数分"的评估哲学——将"匹配度 85%"转为可讨论的具体判断
  - 三层独立评估维度：任务匹配、能力匹配、事件匹配
  - HR 与用人部门双视角评估（模拟真实招聘决策过程）
- **vs 同类**：评估方法论最成熟的开源项目。Claude Code 技能格式，可直接集成。
- **重要信息**：Python，中英双语，Claude Code 集成。

### 4. AI-Agent-for-HR-AzureOpenAI — ⭐ 较新

- **仓库**：[AlbertCySe/AI-Agent-for-HR-AzureOpenAI](https://github.com/AlbertCySe/AI-Agent-for-HR-AzureOpenAI)
- **核心能力**：HR AI 助手，分析简历 + JD → 识别硬性要求 → 生成面试问题 → 评估候选人回答。
- **差异化亮点**：
  - 自动从 JD 识别硬性/软性要求
  - 面试问题生成 + 候选人回答评估的闭环
  - Azure OpenAI 企业级集成

### 5. OpenCATS — ⭐ 679

- 见场景五详细介绍。其 Job Order 管理模块支持定义和跟踪职位需求。

---

## 场景五：人选跟进 SOP / 人选生命周期管理

### 1. OpenCATS — ⭐ 679

- **仓库**：[opencats/OpenCATS](https://github.com/opencats/OpenCATS)
- **核心能力**：开源 ATS 标杆。完整的候选人生命周期管理：Job Order → 简历入库 → 筛选 → 面试排期 → Offer → 入职。Pipeline 看板 + 活动记录 + 邮件集成。
- **差异化亮点**：
  - **GitHub 上最成熟的开源 ATS**（2009 年创建，17 年历史）
  - 完整的招聘 CRM 功能：候选人数据库、Pipeline 管理、活动日志
  - 支持多招聘者协作、权限管理
  - 内置邮件客户端集成
  - 可与 Bullhorn、CEIPAL 等商业系统对接
- **vs 同类**：OpenCATS 是唯一真正可替代商业 ATS（如 Bullhorn、Greenhouse）的开源方案。劣势：PHP/MySQL 技术栈偏老，UI/UX 需要现代化。
- **重要信息**：PHP + MySQL，297 forks，139 open issues。**猎头公司自建系统的最佳起点**。

### 2. OrangeHRM — ⭐ 1,055

- **仓库**：[orangehrm/orangehrm](https://github.com/orangehrm/orangehrm)
- **核心能力**：全面的人力资源管理系统。招聘模块 + 入职管理 + 员工生命周期 + 考勤 + 薪资。从候选人到员工的全生命周期覆盖。
- **差异化亮点**：
  - **HRMS + ATS 一体化**（不是纯 ATS，而是完整 HR 系统）
  - 包含招聘管理、入职流程、绩效管理
  - RESTful API，支持集成
  - 企业客户基础广泛（实际商用产品）
- **vs 同类**：比 OpenCATS 功能更全面（含入职后管理），但招聘模块深度不如 OpenCATS。适合需要从招聘到入职全流程管理的企业。
- **重要信息**：GPL-3.0 许可证（注意商用限制），PHP，711 forks。

### 3. reqcore — ⭐ 28

- **仓库**：[reqcore-inc/reqcore](https://github.com/reqcore-inc/reqcore)
- **核心能力**：现代开源 ATS。候选人 Pipeline 管理 + 团队协作 + 看板式招聘流程。Vue + Nuxt.js 前端。
- **差异化亮点**：
  - **技术栈最现代的开源 ATS**（Vue + Nuxt.js）
  - Pipeline 看板式界面（类似 Trello/Greenhouse）
  - 持续活跃开发（2026-05 仍有更新）
  - 专注招聘流程管理，无多余 HR 模块
- **vs 同类**：UI/UX 远优于 OpenCATS。劣势：功能成熟度不如 OpenCATS，社区较小。
- **重要信息**：AGPL-3.0 许可证，Vue + Node.js，22 open issues。

### 4. SpotAxis — ⭐ 较新

- **仓库**：[Assystant/SpotAxis](https://github.com/Assystant/SpotAxis)
- **核心能力**：MIT 许可的开源 ATS，目标成为最易适配的招聘系统。
- **差异化亮点**：
  - **MIT 许可证**（最宽松的开源协议，商用无忧）
  - 设计理念强调可适配性
- **vs 同类**：许可证最友好。劣势：功能完整度和社区活跃度不如 OpenCATS。

### 5. HR-AI-Agent — ⭐ 较新

- **仓库**：[ADLIN-BABI/HR-AI-Agent](https://github.com/ADLIN-BABI/HR-AI-Agent)
- **核心能力**：AI 招聘工具：简历筛选 + 候选人排序 + AI 摘要生成 + Google Calendar 面试排期 + 邮件邀请自动化。
- **差异化亮点**：
  - **自动化面试排期**（Google Calendar 集成）
  - 自动邮件邀请（候选人触达自动化）
  - AI 生成候选人摘要（加速招聘者决策）
- **vs 同类**：最接近"AI + ATS"融合的开源项目。功能轻量但覆盖面试排期这个关键环节。

---

## 场景六：人选多渠道触达 / 消息策略与自动化

> **坦率说明**：GitHub 上专门做招聘触达/消息自动化的开源项目极少。这更多是商业产品（如 Gem、Outreach.io、HireEZ）的核心功能。以下项目在相关能力上有参考价值。

### 1. linkedin-sourcing-ai — ⭐ 较新

- 已在场景三介绍。自动生成个性化触达消息是核心功能之一。

### 2. RecruitmentAgent-AI — ⭐ 较新

- 已在场景三介绍。自动化邮件沟通是其核心能力。

### 3. HR-AI-Agent — ⭐ 较新

- 已在场景五介绍。邮件邀请自动化。

### 4. AI-Powered-Resume-Evaluation-Agent (n8n) — ⭐ 较新

- **仓库**：[vuyyurusairamreddy/AI-Powered-Resume-Evaluation-Agent-for-Automated-Candidate-Screening](https://github.com/vuyyurusairamreddy/AI-Powered-Resume-Evaluation-Agent-for-Automated-Candidate-Screening)
- **核心能力**：基于 n8n 自动化平台的简历评估 Agent。解析简历 → JD 匹配 → 评分 → **自动化沟通**（邮件通知候选人和招聘者）。
- **差异化亮点**：
  - **基于 n8n**（可视化工作流引擎），非代码用户也可配置
  - 自动化沟通环节（评估后自动发邮件）
  - 可扩展到 Slack、WhatsApp 等多渠道
- **vs 同类**：唯一基于低代码平台（n8n）的方案，最容易扩展多渠道触达。

### 5. voice-agent-sayitdont-pasteit — ⭐ 较新

- **仓库**：[narenkarthikx/voice-agent-sayitdont-pasteit](https://github.com/narenkarthikx/voice-agent-sayitdont-pasteit)
- **核心能力**：AI 语音招聘筛选系统。超越简历关键词——进行简历资格检查 + AI 语音面试 + 生成面后洞察。
- **差异化亮点**：
  - **唯一的开源语音面试方案**
  - 语音 AI 面试替代传统电话初筛
  - 生成结构化的面后评估报告
- **vs 同类**：开辟了全新的触达渠道（语音），而非邮件/消息。适合需要高质量初筛的猎头场景。

---

## 综合推荐矩阵

| 需求场景 | 首选项目 | Stars | 备选方案 |
|---------|---------|-------|---------|
| 简历评估/筛选 | Resume Matcher | 27,105 | AI-Resume-Analyzer |
| 简历构建/优化 | Reactive Resume | 37,759 | JadeAI |
| ATS/生命周期管理 | OpenCATS | 679 | reqcore |
| 自动寻访/触达 | linkedin-sourcing-ai | 新 | HR-Buddy |
| 职位需求深挖 | hound-system | 新 | Resume Matcher(反向) |
| 多渠道触达 | n8n 简历评估 Agent | 新 | voice-agent |

---

## 关键结论

1. **简历工具生态最成熟**：Reactive Resume (37.7K) + Resume Matcher (27.1K) + OpenResume (8.6K) 形成完整工具链——构建 → 分析 → 匹配。
2. **ATS 是最薄弱环节**：OpenCATS (679 stars) 是唯一成熟的开源 ATS，但技术栈老旧。reqcore 是最有希望的现代替代。
3. **自动寻访/触达几乎空白**：LinkedIn sourcing 和多渠道触达基本被商业产品垄断，开源方案稀缺。
4. **多 Agent 招聘是趋势**：AutoGen/LangGraph/CrewAI 框架下的招聘 Agent 开始涌现，但都处于早期。
5. **猎头视角项目极度稀缺**：绝大多数项目面向求职者（resume builder/analyzer），面向招聘方/猎头的工具极少。hound-system 是少数明确从招聘决策流程出发设计的项目。
