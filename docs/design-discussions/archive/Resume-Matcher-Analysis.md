# Resume-Matcher 项目调研分析报告

> 调研日期: 2026-04-28
> 项目地址: D:\workspace\Resume-Matcher
> 项目性质: GitHub 开源简历优化工具（Star 较多）
> 调研目标: 评估其匹配算法、架构设计对「简历与岗位JD匹配度评价系统」的可借鉴性

---

## 一、项目概述

### 1.1 项目定位

Resume-Matcher 是一个 **AI 驱动的简历定制工具**，核心功能是根据目标岗位 JD 自动优化简历内容，而非传统的 NLP 相似度匹配系统。

**关键定位差异：**
| 维度 | Resume-Matcher | 我们的匹配度评价系统 |
|------|---------------|---------------------|
| 核心目标 | 简历内容改写优化 | 简历与岗位的匹配度评分 |
| 输出 | 优化后的简历 + 求职信 | 匹配度分数 + 差距分析 |
| 用户 | 求职者（优化自己的简历） | HR/招聘方（评价候选人匹配度） |
| 技术路线 | LLM Prompt 驱动 | 需要定量评分算法 |

### 1.2 技术栈

- **后端**: Python + FastAPI + LiteLLM + TinyDB
- **前端**: Next.js 16 + React 19 + TipTap 编辑器 + Tailwind CSS
- **文档解析**: markitdown + pdfminer + python-docx
- **PDF 生成**: Playwright 无头浏览器
- **LLM**: 支持 OpenAI / Anthropic / Gemini / DeepSeek / Ollama 等多供应商

---

## 二、核心架构与数据流

### 2.1 整体处理流程

```
┌──────────────┐     ┌──────────────┐
│ 简历上传      │     │ JD 粘贴输入  │
│ PDF/DOCX     │     │ 纯文本       │
└──────┬───────┘     └──────┬───────┘
       │                    │
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│ markitdown   │     │ LLM 关键词   │
│ 转 Markdown  │     │ 提取         │
└──────┬───────┘     └──────┬───────┘
       │                    │
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│ LLM 解析为   │     │ 结构化关键词  │
│ 结构化 JSON  │     │ {skills,...} │
└──────┬───────┘     └──────┬───────┘
       │                    │
       └────────┬───────────┘
                ▼
       ┌──────────────┐
       │ 多轮优化改写  │
       │ (LLM Prompt) │
       └──────┬───────┘
              ▼
       ┌──────────────┐
       │ 关键词匹配度  │ ← 这是唯一的定量评分
       │ 计算         │
       └──────────────┘
```

### 2.2 关键模块

| 模块 | 文件 | 职责 |
|------|------|------|
| 文档解析 | `services/` | PDF/DOCX → Markdown → 结构化 JSON |
| 关键词提取 | `prompts/` + `services/` | LLM 从 JD 提取技能/经验要求 |
| 简历优化 | `services/refiner.py` | 多轮 LLM 改写 + 真实性校验 |
| 匹配评分 | `refiner.py` + 前端 `keyword-matcher.ts` | 关键词命中率计算 |
| 数据存储 | `database.py` | TinyDB JSON 文件存储 |

---

## 三、匹配算法详解（重点）

### 3.1 关键词匹配评分（核心评分机制）

这是该项目唯一的定量匹配算法，实现在两处：

**后端 (refiner.py):**
```python
def calculate_keyword_match(resume, jd_keywords):
    resume_text = _extract_all_text(resume).lower()

    all_keywords = set()
    all_keywords.update(jd_keywords.get("required_skills", []))
    all_keywords.update(jd_keywords.get("preferred_skills", []))
    all_keywords.update(jd_keywords.get("keywords", []))

    matched = sum(1 for kw in all_keywords if _keyword_in_text(kw, resume_text))
    return (matched / len(all_keywords)) * 100
```

**前端 (keyword-matcher.ts):**
```typescript
export function calculateMatchStats(resumeText: string, jdKeywords: Set<string>) {
    const resumeKeywords = extractKeywords(resumeText);
    const matchedKeywords = new Set<string>();
    for (const keyword of jdKeywords) {
        if (resumeKeywords.has(keyword)) {
            matchedKeywords.add(keyword);
        }
    }
    return {
        matchCount: matchedKeywords.size,
        totalKeywords: jdKeywords.size,
        matchPercentage: totalKeywords > 0 ?
            Math.round((matchCount / totalKeywords) * 100) : 0
    };
}
```

**评分特点：**
- 纯关键词命中统计，无语义理解
- 使用 `\b` 词边界匹配（非子串匹配）
- 大小写不敏感
- 过滤常见职位发布无意义词

### 3.2 JD 关键词提取（LLM 驱动）

通过 LLM Prompt 从 JD 提取结构化关键词：

```python
# 提取结果结构
{
    "required_skills": ["Python", "AWS"],
    "preferred_skills": ["Kubernetes"],
    "experience_requirements": ["5+ years"],
    "education_requirements": ["Bachelor's in CS"],
    "key_responsibilities": ["Lead team"],
    "keywords": ["microservices", "agile"],
    "experience_years": 5,
    "seniority_level": "senior"
}
```

**可借鉴价值：** 这套 Prompt 设计思路可以直接复用，用于从 JD 中提取结构化要求。

### 3.3 简历结构化解析（LLM 驱动）

通过 LLM 将 Markdown 简历解析为结构化 JSON：

```python
class ResumeData(BaseModel):
    personalInfo: PersonalInfo           # 姓名、联系方式
    summary: str                         # 专业概述
    workExperience: list[Experience]     # 工作经历
    education: list[Education]           # 教育背景
    personalProjects: list[Project]      # 项目经历
    additional: AdditionalInfo           # 技能、证书、奖项
    sectionMeta: list[SectionMeta]       # 板块元数据
    customSections: dict[str, CustomSection]  # 自定义板块
```

**可借鉴价值：** Pydantic 数据模型设计可以作为我们简历解析的数据模型参考。

### 3.4 多轮优化改写流程

```
Pass 1: 初始定制改写（LLM Prompt）
  ├── nudge 模式: 最小改动，仅调整措辞
  ├── keywords 模式: 注入关键词，不改变职责范围
  └── full 模式: 全面定制改写

Pass 2: 关键词注入
  └── 从 Master Resume 中注入 JD 需要但当前简历缺失的关键词

Pass 3: AI 短语清除（本地处理，无 LLM）
  └── 移除 ~60 个 AI 生成常用套话词汇
  └── 如 "spearheaded", "orchestrated", "synergized" 等

Pass 4: Master Resume 对齐验证
  └── 确保改写后的内容不虚构经历
  └── 技能必须来自 Master Resume
  └── 证书、公司名必须真实存在
```

---

## 四、可借鉴内容评估

### 4.1 高价值可直接借鉴

| 内容 | 来源文件 | 借鉴方式 | 适配工作量 |
|------|---------|---------|-----------|
| **JD 关键词提取 Prompt** | `prompts/` | 直接复用/微调 | 低 |
| **简历结构化解析 Prompt** | `prompts/` | 直接复用/微调 | 低 |
| **Pydantic 数据模型** | `schemas/models.py` | 参考设计，按需调整 | 中 |
| **关键词匹配算法** | `refiner.py` + `keyword-matcher.ts` | 作为基础评分维度之一 | 低 |
| **文档解析流程** (PDF/DOCX → Markdown) | `services/` | 直接复用 | 低 |
| **LLM 多供应商集成** (LiteLLM) | `llm.py` | 架构参考 | 中 |
| **AI 套话检测列表** (~60 个词) | `refiner.py` | 直接复用 | 极低 |
| **关键词哈希缓存** | `refiner.py` | 直接复用 | 极低 |

### 4.2 中等价值需改造

| 内容 | 说明 | 改造方向 |
|------|------|---------|
| **简历改写 Prompt** | 3 种模式 (nudge/keywords/full) | 改造为匹配度分析 Prompt |
| **真实性校验机制** | Master Resume 对齐验证 | 适配为简历信息可信度评估 |
| **前端对比视图** | 原简历 vs 优化简历的 Diff 展示 | 改造为简历 vs JD 的差距分析展示 |
| **PDF 生成** | Playwright 无头渲染 | 可用于生成匹配报告 PDF |

### 4.3 不适用内容

| 内容 | 原因 |
|------|------|
| 简历编辑器 (TipTap) | 我们不需要用户编辑简历 |
| 求职信生成 | 非匹配度评价需求 |
| 模板系统 | 非核心需求 |
| TinyDB 存储 | 不适合生产环境，建议用 PostgreSQL/SQLite |
| Next.js 前端 | 技术栈不同，仅参考设计 |
| 拖拽排序功能 | 非核心需求 |

---

## 五、与我们系统的差距分析

### 5.1 Resume-Matcher 缺失的能力

我们的匹配度评价系统需要但该项目 **没有实现** 的能力：

| 缺失能力 | 重要性 | 建议方案 |
|---------|--------|---------|
| **语义相似度计算** | 高 | 引入 Embedding 模型 (BGE/OpenAI Embedding) 计算向量余弦相似度 |
| **多维度评分体系** | 高 | 设计评分维度：技能匹配、经验匹配、教育匹配、软技能匹配等 |
| **权重配置** | 高 | 支持按岗位类型自定义各维度权重 |
| **批量匹配** | 中 | 支持一份简历匹配多个 JD，或一份 JD 匹配多份简历 |
| **中文简历支持** | 高 | 该项目 Prompt 虽有多语言 UI，但关键词匹配以英文为主 |
| **经验年限匹配** | 中 | 结构化提取简历中的工作年限并与 JD 要求比较 |
| **匹配解释** | 中 | 为每个评分维度提供可解释的分析说明 |
| **历史趋势** | 低 | 匹配度随时间的变化趋势 |

### 5.2 建议的匹配度评分架构

结合 Resume-Matcher 可借鉴部分 + 我们需要补充的部分：

```
                    ┌─────────────────────────┐
                    │     输入层               │
                    │  简历 (PDF/DOCX/TXT)    │
                    │  JD (文本/URL)           │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     解析层               │
                    │  文档 → Markdown (复用)  │
                    │  Markdown → 结构化 JSON  │
                    │  JD → 结构化要求 (复用)  │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
    ┌─────────▼────────┐ ┌──────▼───────┐ ┌────────▼────────┐
    │ 关键词匹配 (复用) │ │ 语义匹配 (新增)│ │ 结构化匹配 (新增)│
    │ 命中率: X%       │ │ 相似度: X%    │ │ 经验/学历: X%   │
    └─────────┬────────┘ └──────┬───────┘ └────────┬────────┘
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     融合评分层            │
                    │  加权综合评分             │
                    │  = w1*关键词 + w2*语义   │
                    │  + w3*结构化 + ...       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     输出层               │
                    │  总分 + 维度分 + 分析报告 │
                    │  差距分析 + 改进建议      │
                    └─────────────────────────┘
```

---

## 六、可直接复用的代码清单

### 6.1 推荐直接移植

```
# 1. 文档解析
apps/backend/app/services/        # PDF/DOCX 解析服务
  └── markitdown 相关调用逻辑

# 2. Prompt 模板
apps/backend/app/prompts/         # JD 关键词提取 + 简历解析 Prompt

# 3. 数据模型
apps/backend/app/schemas/models.py  # Pydantic 模型定义

# 4. 关键词匹配
apps/backend/app/services/refiner.py  # calculate_keyword_match 函数
  + AI_PHRASE_BLACKLIST

# 5. LLM 集成
apps/backend/app/llm.py           # LiteLLM 多供应商封装
```

### 6.2 需要适配后使用

```
# 1. 前端关键词匹配逻辑
apps/frontend/lib/keyword-matcher.ts  # 移植为 Python 版本或保持 TS

# 2. 配置系统
apps/backend/app/config.py        # 简化，适配我们的配置需求

# 3. 数据库层
apps/backend/app/database.py      # 替换为适合的存储方案
```

---

## 七、总结与建议

### 7.1 一句话评价

Resume-Matcher 是一个优秀的 **简历改写工具**，但不是一个匹配度评价系统。它的价值在于提供了**文档解析 + 结构化提取 + 关键词匹配**的完整 baseline，可以作为我们系统的**起点而非终点**。

### 7.2 核心建议

1. **复用其文档解析链路** — PDF/DOCX → Markdown → 结构化 JSON 这条路径经过验证，直接复用
2. **复用其 JD 关键词提取 Prompt** — 结构化提取能力成熟，微调即可
3. **以关键词匹配为基础评分维度之一** — 但不能仅靠此，需要补充语义匹配和结构化匹配
4. **补充语义相似度计算** — 使用 Embedding 模型实现真正的语义理解
5. **设计多维度加权评分体系** — 这是我们的核心差异化能力
6. **重点投入中文优化** — 原项目以英文为主，中文分词、语义匹配需要额外处理

### 7.3 工作量估算

| 模块 | 来源 | 预估工时 |
|------|------|---------|
| 文档解析集成 | 复用 Resume-Matcher | 0.5 天 |
| JD 结构化提取 | 复用 + 微调 Prompt | 1 天 |
| 简历结构化解析 | 复用 + 微调 Prompt | 1 天 |
| 关键词匹配评分 | 复用 + 中文化 | 0.5 天 |
| 语义相似度计算 | 新开发 | 2 天 |
| 结构化匹配（经验/学历） | 新开发 | 1.5 天 |
| 多维度加权评分 | 新开发 | 1 天 |
| 匹配报告生成 | 新开发 | 1.5 天 |
| **合计** | | **~9 天** |
