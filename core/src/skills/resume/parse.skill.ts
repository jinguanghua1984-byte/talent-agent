import { defineSkill } from '../base.ts';
import { skillRegistry } from '../registry.ts';

// 内联 prompt 模板，避免 ?raw 导入在 tsup 构建时的问题
const resumeParsePrompt = `# 简历解析

你是一位专业的猎头顾问，擅长从简历中提取关键信息。

## 任务
解析用户提供的简历文本，提取以下信息并以结构化格式返回：

## 输出格式
\`\`\`json
{
  "name": "候选人姓名",
  "title": "当前职位",
  "email": "邮箱",
  "phone": "电话",
  "location": "所在地",
  "summary": "个人简介",
  "skills": ["技能1", "技能2"],
  "workExperience": [
    {
      "company": "公司名称",
      "title": "职位",
      "startDate": "开始日期",
      "endDate": "结束日期（在职则为空）",
      "description": "工作描述",
      "highlights": ["亮点1", "亮点2"]
    }
  ],
  "education": [
    {
      "school": "学校名称",
      "degree": "学位",
      "major": "专业",
      "startDate": "开始日期",
      "endDate": "结束日期"
    }
  ],
  "languages": ["语言1", "语言2"],
  "certifications": ["证书1", "证书2"]
}
\`\`\`

## 注意事项
- 如果某字段信息缺失，使用 null 或空数组
- 日期格式统一为 YYYY-MM
- 技能标签尽量使用行业标准术语
- 突出与猎头匹配相关的信息

## 简历内容
{{resume}}`;

/**
 * 简历解析 Skill
 * 从简历文本中提取结构化的候选人信息
 */
export const resumeParseSkill = defineSkill()
  .id('resume-parse')
  .name('简历解析')
  .description('解析简历文本，提取候选人的关键信息，包括工作经历、教育背景、技能等')
  .version('1.0.0')
  .category('resume')
  .platforms('claude-code', 'cursor', 'continue')
  .tags('简历', '解析', '候选人')
  .prompt(resumeParsePrompt)
  .build();

// 自动注册
skillRegistry.register(resumeParseSkill);
