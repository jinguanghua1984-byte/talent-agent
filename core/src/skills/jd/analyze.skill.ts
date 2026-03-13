import { defineSkill } from '../base.ts';
import { skillRegistry } from '../registry.ts';

// 内联 prompt 模板，避免 ?raw 导入在 tsup 构建时的问题
const jdAnalyzePrompt = `# JD 分析

你是一位专业的猎头顾问，擅长分析职位描述（JD）并提取关键招聘要求。

## 任务
分析用户提供的职位描述（JD），提取以下信息并以结构化格式返回：

## 输出格式
\`\`\`json
{
  "title": "职位名称",
  "company": "公司名称（如有）",
  "location": "工作地点",
  "salaryRange": {
    "min": "最低薪资（数字，单位：千/月）",
    "max": "最高薪资（数字，单位：千/月）",
    "currency": "CNY"
  },
  "summary": "职位概述",
  "responsibilities": ["职责1", "职责2"],
  "requirements": [
    {
      "type": "required/preferred",
      "content": "要求内容",
      "category": "skill/experience/education/certification/other"
    }
  ],
  "benefits": ["福利1", "福利2"]
}
\`\`\`

## 注意事项
- 区分必须要求和优先要求
- 将要求分类以便后续匹配
- 提取薪资范围时统一单位
- 识别关键技能和经验要求

## JD 内容
{{jd}}`;

/**
 * JD 分析 Skill
 * 从职位描述中提取结构化的招聘要求
 */
export const jdAnalyzeSkill = defineSkill()
  .id('jd-analyze')
  .name('JD 分析')
  .description('分析职位描述（JD），提取职位要求、职责、薪资范围等关键信息')
  .version('1.0.0')
  .category('jd')
  .platforms('claude-code', 'cursor', 'continue')
  .tags('JD', '职位描述', '分析', '招聘')
  .prompt(jdAnalyzePrompt)
  .build();

// 自动注册
skillRegistry.register(jdAnalyzeSkill);
