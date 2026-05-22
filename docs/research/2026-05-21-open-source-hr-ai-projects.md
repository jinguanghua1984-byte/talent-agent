# 开源猎头/HR AI 赋能项目推荐

生成时间：2026-05-21
数据口径：本轮通过 GitHub API/仓库页面核验 stars、license、最近更新时间和项目描述。Stars 会持续变化，本文按本轮查询值记录。
筛选目标：高星、开源或源码可用、能服务猎头/HR 的 AI 提效、数据获取和流程自动化。主推荐项目最低约 4.7k stars；传统 HR 原生 ATS 项目若星数较低，仅放入观察项。

## 结论先行

如果目标是尽快搭建“AI 猎头工作台”，优先组合如下：

1. 需求深挖与人才画像：`Dify` 或 `Langflow` 负责业务入口，`Haystack` 负责结构化检索和岗位知识库，`CrewAI` 适合把招聘专家、行业研究员、面试官拆成多 Agent。
2. 自动寻访与数据获取：`Firecrawl` + `Crawl4AI` 用于公开网页清洗，`Crawlee` 用于规模化爬取，`browser-use` 用于动态页面和流程操作，`ScrapeGraphAI` 用于复杂页面的 LLM 结构化抽取。
3. 简历解析、粗筛和精排：`Docling`/`Unstructured` 做简历文档结构化，`Resume Matcher` 做 JD-简历匹配和关键词差距，`Haystack` 做向量检索、召回和 rerank，`Dify` 做可视化评审流程。
4. 简历优化与定制生成：候选人侧优先 `Reactive Resume`、`OpenResume` 和 `Resume Matcher`；若要研究自动投递链路，可看 `AIHawk`，但要注意平台条款和反自动化风险。
5. 人选生命周期管理：`Twenty` 适合做候选人 CRM，`NocoDB` 适合快速搭建人才库，`Frappe HRMS` 是 HR 原生系统，`Cal.com` 解决面试排期，`Appsmith` 适合搭招聘运营后台。
6. 多渠道触达与消息自动化：`n8n` 是首选流程编排胶水，`Novu` 做通知基础设施，`Chatwoot` 做会话收口，`Mautic` 和 `listmonk` 做邮件/营销式 nurture。

合规提醒：数据抓取、自动触达、候选人画像和简历评估都涉及隐私、平台条款、反歧视和反垃圾消息约束。建议把所有项目先用于公开信息、用户授权数据、内部人才库和人工审核工作流；不要直接用于绕过招聘平台风控或批量骚扰候选人。

## 一、职位需求深挖/目标人才画像 Top 5

### 1. Langflow

- GitHub：[langflow-ai/langflow](https://github.com/langflow-ai/langflow)；stars：148,574；license：MIT；最近更新：2026-05-21。
- 核心能力：可视化构建和部署 AI agent/workflow，适合把 JD 解析、胜任力模型、目标公司池、关键词包、面试题生成串成流程。
- 差异化亮点：组件化和可视化都比较强，适合招聘团队和工程团队共同迭代“岗位深挖画布”。
- 同类优势：相比纯代码框架，上手快；相比 Dify 更偏流程/组件拼装，适合探索复杂 agent 流程。
- 同类劣势：业务权限、团队协作、数据治理不一定比 Dify 成熟；复杂生产部署仍要工程把关。
- 适合场景：把“招聘经理访谈纪要 + JD + 历史成功候选人”转为目标人才画像、搜索词、排除项和面试 scorecard。

### 2. Dify

- GitHub：[langgenius/dify](https://github.com/langgenius/dify)；stars：142,067；license：GitHub API 返回 `NOASSERTION`，商业化前需核验仓库许可；最近更新：2026-05-21。
- 核心能力：面向生产的 agentic workflow 平台，支持知识库/RAG、工作流、应用发布和 API 化。
- 差异化亮点：更接近“HR 业务应用搭建器”，能把岗位深挖、候选人问答、推荐报告生成做成内部工具。
- 同类优势：比 Langflow/Flowise 更偏产品化和运营化，适合非工程用户长期使用。
- 同类劣势：深度定制和底层检索控制不如 Haystack；许可不是标准 SPDX，需要法务确认。
- 适合场景：JD intake 表单、招聘经理需求澄清机器人、岗位画像生成、寻访计划自动输出。

### 3. CrewAI

- GitHub：[crewAIInc/crewAI](https://github.com/crewAIInc/crewAI)；stars：51,830；license：MIT；最近更新：2026-05-20。
- 核心能力：编排角色化 autonomous agents，可把“岗位顾问、行业研究员、寻访顾问、面试官、薪酬顾问”拆成协作任务。
- 差异化亮点：角色分工天然贴近猎头工作法，适合复杂岗位的多视角深挖和交叉质检。
- 同类优势：比可视化工具更灵活，适合沉淀严肃 SOP 和评审链路。
- 同类劣势：需要工程实现和测试，非技术 HR 难以直接维护；成本和稳定性取决于模型与工具调用设计。
- 适合场景：高端岗位 mapping、行业公司池推演、候选人背景假设生成、面试验证点交叉审阅。

### 4. Haystack

- GitHub：[deepset-ai/haystack](https://github.com/deepset-ai/haystack)；stars：25,313；license：Apache-2.0；最近更新：2026-05-20。
- 核心能力：RAG、语义检索、pipeline、routing、memory、agent workflow 等 LLM 应用基础设施。
- 差异化亮点：更像可控的 AI 检索/评估引擎，适合把岗位画像和人才库做成可解释的召回/精排系统。
- 同类优势：生产控制力强，可把检索、rerank、生成分层治理。
- 同类劣势：没有开箱即用 HR 产品界面，需要工程团队构建业务层。
- 适合场景：岗位知识库、历史成功候选人画像库、行业术语归一、候选人向量召回和排序。

### 5. Flowise

- GitHub：[FlowiseAI/Flowise](https://github.com/FlowiseAI/Flowise)；stars：52,963；license：GitHub API 返回 `NOASSERTION`，商业化前需核验仓库许可；最近更新：2026-05-19。
- 核心能力：可视化构建 AI agents，适合快速拼接 LLM、向量库、工具调用和对话入口。
- 差异化亮点：低代码原型速度快，适合 HR 团队先验证 JD 深挖/候选人问答流程。
- 同类优势：比 CrewAI 更容易上手；比从零写 LangChain 快。
- 同类劣势：生产级权限、评估、观测和复杂业务流治理需要补强。
- 适合场景：岗位分析 bot、候选人摘要 bot、招聘顾问检索助手和内部 FAQ。

## 二、寻访策略/自动寻访 Top 5

### 1. Firecrawl

- GitHub：[firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)；stars：122,384；license：AGPL-3.0；最近更新：2026-05-21。
- 核心能力：为 AI agents 搜索、抓取、清洗网页，把公开网页转成更适合 LLM/RAG 的结构化内容。
- 差异化亮点：对“公司官网、团队页、博客、招聘页、公开简历页”的清洗链路友好，能直接进入画像/搜索词生成。
- 同类优势：比传统爬虫更接近 AI 数据准备层；比 browser automation 更轻。
- 同类劣势：动态登录站点和强反爬平台仍可能失败；AGPL 对闭源商业集成有要求。
- 适合场景：目标公司池扩展、公开组织架构/团队信息抽取、岗位竞品采集、候选人公开资料摘要。

### 2. browser-use

- GitHub：[browser-use/browser-use](https://github.com/browser-use/browser-use)；stars：94,865；license：MIT；最近更新：2026-05-20。
- 核心能力：让 AI agent 操作真实网页，适合动态页面、复杂表单、搜索过滤器和流程性网页任务。
- 差异化亮点：能处理传统 crawler 很难处理的交互页面。
- 同类优势：比 Firecrawl/Crawl4AI 更强交互能力；比手写 Playwright 更像 agent。
- 同类劣势：自动操作真实招聘平台有合规和风控风险；页面变化会影响稳定性。
- 适合场景：内部已授权系统的人才搜索、数据录入、候选人状态同步、后台运营流程自动化。

### 3. Crawl4AI

- GitHub：[unclecode/crawl4ai](https://github.com/unclecode/crawl4ai)；stars：65,969；license：Apache-2.0；最近更新：2026-05-13。
- 核心能力：面向 LLM 的开源 crawler/scraper，强调把网页转成 AI 友好的数据。
- 差异化亮点：自托管和工程可控性强，适合搭企业内部数据采集服务。
- 同类优势：Apache-2.0 许可友好；比 prompt-only scraping 更稳定。
- 同类劣势：需要工程配置爬取策略、去重、限速和合规边界。
- 适合场景：目标公司官网、公开技术博客、开源贡献者资料、职位页采集。

### 4. Crawlee

- GitHub：[apify/crawlee](https://github.com/apify/crawlee)；stars：23,342；license：Apache-2.0；最近更新：2026-05-20。
- 核心能力：Node.js/TypeScript 爬虫和浏览器自动化库，支持 Playwright、Puppeteer、Cheerio、JSDOM、raw HTTP、代理轮换等。
- 差异化亮点：成熟的规模化采集工程底座，适合做稳定的 sourcing data pipeline。
- 同类优势：比 AI scraper 更可控、更可测试；比单纯 requests 爬虫更适合复杂页面。
- 同类劣势：不自带 HR 语义理解，需要接 LLM/规则层做职位画像和候选人抽取。
- 适合场景：公开职位库/公司库/开源社区数据采集、增量更新、数据质量巡检。

### 5. ScrapeGraphAI

- GitHub：[ScrapeGraphAI/Scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai)；stars：25,691；license：MIT；最近更新：2026-05-17。
- 核心能力：基于 AI 的 Python scraper，用自然语言描述抽取目标。
- 差异化亮点：适合页面结构变化较大、字段抽取难以写死规则的场景。
- 同类优势：比 Crawlee 更快验证复杂页面抽取；比纯 LLM 复制网页更结构化。
- 同类劣势：LLM 成本、稳定性和可解释性需要监控；批量生产不如规则爬虫可控。
- 适合场景：快速抽取目标公司介绍、团队成员、职位要求、公开 profile 片段。

## 三、简历评估/粗筛和精排 Top 5

### 1. Resume Matcher

- GitHub：[srbhr/Resume-Matcher](https://github.com/srbhr/Resume-Matcher)；stars：27,105；license：Apache-2.0；最近更新：2026-05-12。
- 核心能力：根据 JD 分析简历匹配度，输出 insights、关键词建议和简历调优方向。
- 差异化亮点：最贴近“JD-简历匹配”的高星项目，可直接借鉴评分维度和关键词差距分析。
- 同类优势：比通用 LLM 工作流更 HR 垂直；比简历解析库更接近评估结果。
- 同类劣势：偏候选人优化视角，不是完整 ATS 批量精排系统；企业级审计和反偏见机制需要补。
- 适合场景：粗筛 scorecard、JD 匹配解释、简历缺口提示、候选人推荐理由生成。

### 2. Docling

- GitHub：[docling-project/docling](https://github.com/docling-project/docling)；stars：60,077；license：MIT；最近更新：2026-05-20。
- 核心能力：把 PDF、Office 等文档准备成适合 GenAI 的结构化内容。
- 差异化亮点：简历评估的第一步是可靠解析，Docling 适合处理多格式简历、PDF 表格和版式内容。
- 同类优势：比简单 PDF text extraction 更适合 LLM 管线；license 友好。
- 同类劣势：不自带招聘评分，需要接规则、向量检索或 LLM 评审层。
- 适合场景：批量简历解析、教育/工作经历结构化、项目经历抽取、附件进入人才库。

### 3. Unstructured

- GitHub：[Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured)；stars：14,747；license：Apache-2.0；最近更新：2026-05-18。
- 核心能力：把复杂文档转为干净结构化格式，支持分块、清洗、嵌入前处理。
- 差异化亮点：更偏文档 ETL，适合把简历、面试记录、背调资料统一送入 RAG/评分系统。
- 同类优势：格式覆盖广，适合企业文档流；Apache-2.0 许可友好。
- 同类劣势：上层应用和 UI 不如 Docling/Resume Matcher 直观；生产部署可能偏重。
- 适合场景：简历入库、候选人资料包解析、批量附件清洗、面试记录知识化。

### 4. Haystack

- GitHub：[deepset-ai/haystack](https://github.com/deepset-ai/haystack)；stars：25,313；license：Apache-2.0；最近更新：2026-05-20。
- 核心能力：构建召回、检索、rerank、RAG 和 LLM pipeline。
- 差异化亮点：适合把“简历解析结果 + 岗位画像 + 历史评价”变成可解释的粗筛和精排。
- 同类优势：比纯 prompt 评分更可控；可把规则、向量、重排、生成分层。
- 同类劣势：需要工程团队设计 schema、评估集和线上观测。
- 适合场景：人才库召回、TopN 排序、面试官评分辅助、候选人相似度检索。

### 5. Dify

- GitHub：[langgenius/dify](https://github.com/langgenius/dify)；stars：142,067；license：GitHub API 返回 `NOASSERTION`；最近更新：2026-05-21。
- 核心能力：用工作流把简历解析、JD 匹配、评审解释、人工复核和报告生成串起来。
- 差异化亮点：能快速把 HR 筛选 SOP 产品化，形成内部可用的“简历评审助手”。
- 同类优势：比从零开发更快交付；比单点解析库更接近业务闭环。
- 同类劣势：评分正确性、偏见控制、审计记录要额外设计；许可需核验。
- 适合场景：简历粗筛助手、推荐报告生成、候选人面试摘要、人工复核入口。

## 四、简历优化/定向简历完善/定制化简历生成 Top 5

### 1. Reactive Resume

- GitHub：[amruthpillai/reactive-resume](https://github.com/amruthpillai/reactive-resume)；stars：37,761；license：MIT；最近更新：2026-05-20。
- 核心能力：隐私友好的开源简历构建器，支持模板、编辑、导出和自托管。
- 差异化亮点：候选人侧体验成熟，适合做“候选人简历完善工作台”的前端底座。
- 同类优势：UI 完成度高、可部署、可定制；比 JSON Resume 更像产品。
- 同类劣势：不天然理解 JD，需要接 LLM/Resume Matcher 做定向改写。
- 适合场景：候选人资料标准化、顾问协助改简历、推荐前材料包装。

### 2. Resume Matcher

- GitHub：[srbhr/Resume-Matcher](https://github.com/srbhr/Resume-Matcher)；stars：27,105；license：Apache-2.0；最近更新：2026-05-12。
- 核心能力：根据目标 JD 给出简历匹配洞察、关键词建议和优化方向。
- 差异化亮点：直接解决“这份简历如何更贴合目标岗位”的问题。
- 同类优势：比通用简历编辑器更懂 JD 对齐；可作为候选人辅导工具。
- 同类劣势：不是完整简历排版/版本管理系统；对真实经历的合规表达仍需人工审核。
- 适合场景：定向简历修改、关键词覆盖度分析、候选人投递前检查。

### 3. OpenResume

- GitHub：[xitanggg/open-resume](https://github.com/xitanggg/open-resume)；stars：8,618；license：AGPL-3.0；最近更新：2024-10-29。
- 核心能力：开源简历构建器和简历解析器。
- 差异化亮点：同时覆盖 builder 和 parser，适合做“上传旧简历 -> 解析 -> 生成标准模板”的闭环。
- 同类优势：比纯 builder 更适合迁移旧简历；比解析库更有候选人侧 UI。
- 同类劣势：最近更新不如 Reactive Resume 活跃；AGPL 对商业集成有要求。
- 适合场景：候选人简历重建、统一模板输出、简历结构化入库。

### 4. AIHawk

- GitHub：[AIHawk-FOSS/Auto_Jobs_Applier_AI_Agent](https://github.com/AIHawk-FOSS/Auto_Jobs_Applier_AI_Agent)；stars：29,782；license：AGPL-3.0；最近更新：2026-05-17。
- 核心能力：用 AI 自动化求职投递流程，并按岗位做 tailored application。
- 差异化亮点：虽然是候选人侧项目，但对“定制化简历/投递材料生成 + 表单自动化”有很强参考价值。
- 同类优势：比单纯简历生成器更接近完整投递链路；能启发猎头侧候选人材料包自动化。
- 同类劣势：不适合直接用于猎头批量触达；自动投递可能违反平台条款，需要严格限制在授权场景。
- 适合场景：研究定向材料生成、候选人侧投递助手、内部 demo，不建议直接对外批量运行。

### 5. JSON Resume CLI

- GitHub：[jsonresume/resume-cli](https://github.com/jsonresume/resume-cli)；stars：4,715；license：MIT；最近更新：2024-04-03。
- 核心能力：基于 JSON Resume 标准创建、校验和渲染简历。
- 差异化亮点：把简历变成结构化 schema，便于版本管理、模板渲染和自动生成。
- 同类优势：标准化强，适合接 LLM 生成结构化简历数据；license 友好。
- 同类劣势：不是 AI 项目，且更新活跃度一般；需要另接 LLM 和模板系统。
- 适合场景：候选人简历数据标准、定制化简历版本管理、不同岗位导出不同模板。

## 五、人选跟进 SOP/人选生命周期管理 Top 5

### 1. Twenty

- GitHub：[twentyhq/twenty](https://github.com/twentyhq/twenty)；stars：45,967；license：GitHub API 返回 `NOASSERTION`；最近更新：2026-05-20。
- 核心能力：开源 Salesforce 替代品，定位为面向 AI 的 CRM。
- 差异化亮点：候选人本质上也是关系资产，Twenty 适合承载候选人、公司、职位、触达记录和下一步动作。
- 同类优势：比 NocoDB 更像正式 CRM；比 Frappe HRMS 更适合猎头关系管理。
- 同类劣势：不是 ATS，面试流程、offer、合规字段需要定制；许可需核验。
- 适合场景：候选人 CRM、人选 pipeline、客户/职位/候选人关系图谱、顾问任务跟进。

### 2. NocoDB

- GitHub：[nocodb/nocodb](https://github.com/nocodb/nocodb)；stars：63,075；license：GitHub API 返回 `NOASSERTION`；最近更新：2026-05-20。
- 核心能力：自托管 Airtable 替代品，可把数据库变成可协作表格。
- 差异化亮点：非常适合快速搭建人才库、长名单、项目看板和状态流转。
- 同类优势：比从零做后台更快；比电子表格更容易接 API 和自动化。
- 同类劣势：复杂 SOP、权限、消息策略需要 n8n/Appsmith 等补齐。
- 适合场景：候选人长名单、mapping 表、寻访项目库、状态字段和人工 review 队列。

### 3. Frappe HRMS

- GitHub：[frappe/hrms](https://github.com/frappe/hrms)；stars：7,991；license：GPL-3.0；最近更新：2026-05-20。
- 核心能力：开源 HR 和 Payroll 软件，覆盖更广义的人力资源管理。
- 差异化亮点：HR 原生度高，适合把招聘、入职和员工生命周期放在同一组织系统里。
- 同类优势：比 Twenty/NocoDB 更 HR 原生；与 Frappe/ERPNext 生态结合紧。
- 同类劣势：猎头寻访 CRM 和外部候选人关系管理不是它的最强项；实施成本高于表格型工具。
- 适合场景：企业 HR 侧招聘到入职、员工档案、组织和薪酬流程衔接。

### 4. Cal.com

- GitHub：[calcom/cal.com](https://github.com/calcom/cal.com)；stars：43,808；license：MIT；最近更新：2026-05-14。
- 核心能力：开源排期基础设施，支持自托管、日历集成和预约流程。
- 差异化亮点：招聘流程中“候选人/面试官/招聘经理”排期是高频瓶颈，Cal.com 可作为标准化面试预约层。
- 同类优势：比 CRM 自带日程更专业；API 和嵌入能力强。
- 同类劣势：不管候选人生命周期和评估，需要接 ATS/CRM/n8n。
- 适合场景：初聊预约、面试官排期、候选人自助选时段、SLA 追踪。

### 5. Appsmith

- GitHub：[appsmithorg/appsmith](https://github.com/appsmithorg/appsmith)；stars：39,865；license：Apache-2.0；最近更新：2026-05-20。
- 核心能力：构建内部管理后台、运营面板和 API/数据库驱动应用。
- 差异化亮点：可把人才库、推荐报告、跟进 SOP、顾问看板、数据质检做成一个内部工作台。
- 同类优势：比 NocoDB 更适合复杂交互和后台；比从零开发快。
- 同类劣势：不是 HR 产品，业务模型和 UI 需要自己搭。
- 适合场景：招聘运营驾驶舱、候选人审核台、顾问任务面板、数据修正后台。

## 六、人选多渠道触达/消息策略与自动化 Top 5

### 1. n8n

- GitHub：[n8n-io/n8n](https://github.com/n8n-io/n8n)；stars：188,910；license：GitHub API 返回 `NOASSERTION`；最近更新：2026-05-20。
- 核心能力：带原生 AI 能力的 workflow automation 平台，支持自托管/云、可视化流程、代码节点和大量集成。
- 差异化亮点：最适合做招聘自动化“胶水层”：候选人入库、评分完成、触达提醒、面试排期、状态回写。
- 同类优势：生态和集成数量强；比专门消息系统更适合跨系统流程。
- 同类劣势：不是候选人 CRM，也不是触达策略引擎；license/fair-code 需要核验。
- 适合场景：多系统自动化、候选人跟进提醒、飞书/Slack/邮件同步、人工审批后触达。

### 2. Novu

- GitHub：[novuhq/novu](https://github.com/novuhq/novu)；stars：38,996；license：GitHub API 返回 `NOASSERTION`；最近更新：2026-05-20。
- 核心能力：开源通知基础设施，支持 in-app inbox、Email、SMS、Push、Slack 等。
- 差异化亮点：把“通知”从业务系统中解耦出来，便于统一模板、事件、渠道和送达状态。
- 同类优势：比 n8n 更专注通知编排；比自己写邮件/SMS 可靠。
- 同类劣势：不负责候选人策略、分群和 CRM；需要上游系统提供事件和人群。
- 适合场景：候选人状态提醒、面试官提醒、顾问任务通知、触达消息模板中心。

### 3. Chatwoot

- GitHub：[chatwoot/chatwoot](https://github.com/chatwoot/chatwoot)；stars：29,595；license：GitHub API 返回 `NOASSERTION`；最近更新：2026-05-20。
- 核心能力：开源 live chat、email support、omni-channel desk。
- 差异化亮点：可把候选人回复、邮件、站内消息等会话集中到一个收件箱。
- 同类优势：比 Mautic/listmonk 更适合双向沟通；比单纯 IM bot 更有客服/会话管理能力。
- 同类劣势：定位是客服/支持，不是招聘触达；招聘字段和 SOP 要定制。
- 适合场景：候选人咨询入口、批量触达后的回复归集、顾问协同处理会话。

### 4. Mautic

- GitHub：[mautic/mautic](https://github.com/mautic/mautic)；stars：9,716；license：GitHub API 返回 `NOASSERTION`；最近更新：2026-05-20。
- 核心能力：开源营销自动化软件，支持分群、活动、邮件和 nurture 流程。
- 差异化亮点：适合把候选人运营做成“人才社区/人才池 nurture”，而不是一次性触达。
- 同类优势：比 listmonk 更有自动化和分群；比 n8n 更贴近营销漏斗。
- 同类劣势：营销域模型需要改造成招聘语义；合规、退订和触达频率必须严格控制。
- 适合场景：人才社区运营、被动候选人长期培育、活动邀请、周期性职位推荐。

### 5. listmonk

- GitHub：[knadh/listmonk](https://github.com/knadh/listmonk)；stars：20,868；license：AGPL-3.0；最近更新：2026-05-15。
- 核心能力：高性能自托管 newsletter 和 mailing list manager。
- 差异化亮点：部署简单、性能强，适合低成本管理候选人邮件订阅和人才池通讯。
- 同类优势：比 Mautic 轻量；比自己搭邮件群发可靠。
- 同类劣势：主要是邮件列表，不是多渠道自动化，也不负责候选人生命周期。
- 适合场景：人才 newsletter、职位订阅、活动邀请、候选人许可邮件通讯。

## 数据与项目元信息汇总

| 项目 | 场景 | Stars | License | 最近更新 | 链接 |
|---|---:|---:|---|---|---|
| n8n | 触达/自动化 | 188,910 | NOASSERTION | 2026-05-20 | https://github.com/n8n-io/n8n |
| Langflow | 画像/工作流 | 148,574 | MIT | 2026-05-21 | https://github.com/langflow-ai/langflow |
| Dify | 画像/筛选/工作流 | 142,067 | NOASSERTION | 2026-05-21 | https://github.com/langgenius/dify |
| Firecrawl | 数据获取/寻访 | 122,384 | AGPL-3.0 | 2026-05-21 | https://github.com/firecrawl/firecrawl |
| browser-use | 自动寻访/流程自动化 | 94,865 | MIT | 2026-05-20 | https://github.com/browser-use/browser-use |
| Crawl4AI | 数据获取 | 65,969 | Apache-2.0 | 2026-05-13 | https://github.com/unclecode/crawl4ai |
| NocoDB | 生命周期/人才库 | 63,075 | NOASSERTION | 2026-05-20 | https://github.com/nocodb/nocodb |
| Docling | 简历解析 | 60,077 | MIT | 2026-05-20 | https://github.com/docling-project/docling |
| Flowise | 画像/工作流 | 52,963 | NOASSERTION | 2026-05-19 | https://github.com/FlowiseAI/Flowise |
| CrewAI | 画像/多 Agent | 51,830 | MIT | 2026-05-20 | https://github.com/crewAIInc/crewAI |
| Twenty | 生命周期/CRM | 45,967 | NOASSERTION | 2026-05-20 | https://github.com/twentyhq/twenty |
| Cal.com | 生命周期/排期 | 43,808 | MIT | 2026-05-14 | https://github.com/calcom/cal.com |
| Appsmith | 生命周期/后台 | 39,865 | Apache-2.0 | 2026-05-20 | https://github.com/appsmithorg/appsmith |
| Novu | 触达/通知 | 38,996 | NOASSERTION | 2026-05-20 | https://github.com/novuhq/novu |
| Reactive Resume | 简历生成 | 37,761 | MIT | 2026-05-20 | https://github.com/amruthpillai/reactive-resume |
| Chatwoot | 多渠道会话 | 29,595 | NOASSERTION | 2026-05-20 | https://github.com/chatwoot/chatwoot |
| AIHawk | 定制材料/自动投递研究 | 29,782 | AGPL-3.0 | 2026-05-17 | https://github.com/AIHawk-FOSS/Auto_Jobs_Applier_AI_Agent |
| Resume Matcher | 简历评估/优化 | 27,105 | Apache-2.0 | 2026-05-12 | https://github.com/srbhr/Resume-Matcher |
| ScrapeGraphAI | 数据抽取 | 25,691 | MIT | 2026-05-17 | https://github.com/ScrapeGraphAI/Scrapegraph-ai |
| Haystack | 检索/精排 | 25,313 | Apache-2.0 | 2026-05-20 | https://github.com/deepset-ai/haystack |
| Crawlee | 数据获取/爬虫 | 23,342 | Apache-2.0 | 2026-05-20 | https://github.com/apify/crawlee |
| listmonk | 邮件触达 | 20,868 | AGPL-3.0 | 2026-05-15 | https://github.com/knadh/listmonk |
| Unstructured | 简历/文档 ETL | 14,747 | Apache-2.0 | 2026-05-18 | https://github.com/Unstructured-IO/unstructured |
| Mautic | 触达/人才运营 | 9,716 | NOASSERTION | 2026-05-20 | https://github.com/mautic/mautic |
| OpenResume | 简历解析/生成 | 8,618 | AGPL-3.0 | 2024-10-29 | https://github.com/xitanggg/open-resume |
| Frappe HRMS | HR 生命周期 | 7,991 | GPL-3.0 | 2026-05-20 | https://github.com/frappe/hrms |
| JSON Resume CLI | 简历结构化 | 4,715 | MIT | 2024-04-03 | https://github.com/jsonresume/resume-cli |

## 观察项：HR 原生但星数不足或活跃度不足

- OpenCATS：[opencats/OpenCATS](https://github.com/opencats/OpenCATS)，约 679 stars。优点是 ATS/Recruitment CRM 原生；短板是星数低于本报告高星门槛，生态和现代 AI 能力弱。
- pyresparser：[OmkarPathak/pyresparser](https://github.com/OmkarPathak/pyresparser)，约 960 stars。优点是简历解析语义直接；短板是更新较旧、星数低、现代文档解析能力不如 Docling/Unstructured。
- Resume-LM：[olyaiy/resume-lm](https://github.com/olyaiy/resume-lm)，约 266 stars。优点是 AI 简历生成定位直接；短板是星数不满足本轮“高星”要求，暂不进入 Top。

## 落地建议

1. 不要先买/改完整 ATS。先用 `NocoDB` 或 `Twenty` 建人才对象和候选人生命周期，用 `n8n` 打通事件，用 `Dify/Langflow` 做 AI 工作台。
2. 简历和候选人资料先做结构化。优先组合 `Docling` 或 `Unstructured` 解析文档，`Haystack` 做召回/精排，`Resume Matcher` 提供 JD 对齐解释。
3. 寻访数据获取分层处理。公开网页用 `Firecrawl/Crawl4AI`，规模化采集用 `Crawlee`，需要交互时再用 `browser-use`，并把平台条款和人工确认放在流程门禁里。
4. 触达不要一上来全自动。先用 `n8n` 做人工审批后的消息编排，用 `Novu` 做通知基础设施，用 `Chatwoot` 收口回复；大量邮件运营再评估 `Mautic/listmonk`。
5. 简历优化要区分“真实经历表达”与“虚构包装”。`Reactive Resume/OpenResume/Resume Matcher` 可用于格式、结构和关键词优化，但候选人事实必须人工确认。
