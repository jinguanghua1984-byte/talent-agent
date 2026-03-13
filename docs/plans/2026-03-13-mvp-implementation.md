# Talent Agent MVP 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 搭建 talent-agent 猎头业务 AI 工具插件库的基础架构，实现可运行的 Claude Code 插件 MVP。

**Architecture:** Monorepo + 平台适配器模式。Core 层包含平台无关的业务逻辑（类型、Skill 定义、工具函数），adapters 层将 core 能力适配到各平台。MVP 阶段只实现 Claude Code 适配器。

**Tech Stack:** TypeScript 5.x, pnpm workspace, tsup, Vitest, Biome

---

## Phase 1: 项目基础设施

### Task 1.1: 初始化 Monorepo 结构

**Files:**
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `tsconfig.base.json`
- Create: `.gitignore`
- Create: `biome.json`

**Step 1: 创建根 package.json**

```json
{
  "name": "talent-agent",
  "version": "0.1.0",
  "private": true,
  "description": "猎头业务 AI 工具插件库",
  "scripts": {
    "build": "pnpm -r build",
    "test": "pnpm -r test",
    "lint": "biome check .",
    "format": "biome format . --write"
  },
  "devDependencies": {
    "@biomejs/biome": "^1.9.0",
    "typescript": "^5.7.0"
  },
  "packageManager": "pnpm@9.0.0",
  "engines": {
    "node": ">=20.0.0"
  }
}
```

**Step 2: 创建 pnpm-workspace.yaml**

```yaml
packages:
  - 'core'
  - 'adapters/*'
```

**Step 3: 创建 tsconfig.base.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true,
    "resolveJsonModule": true
  }
}
```

**Step 4: 创建 .gitignore**

```
node_modules/
dist/
*.log
.DS_Store
.vscode/
.idea/
*.tsbuildinfo
```

**Step 5: 创建 biome.json**

```json
{
  "$schema": "https://biomejs.dev/schemas/1.9.0/schema.json",
  "organizeImports": {
    "enabled": true
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true
    }
  },
  "formatter": {
    "enabled": true,
    "formatWithErrors": false,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100
  }
}
```

**Step 6: 安装依赖**

Run: `pnpm install`
Expected: 依赖安装成功

**Step 7: 初始化 Git**

Run: `git init && git add . && git commit -m "chore: init monorepo structure"`
Expected: Git 仓库初始化成功

---

### Task 1.2: 创建 Core 包基础结构

**Files:**
- Create: `core/package.json`
- Create: `core/tsconfig.json`
- Create: `core/src/index.ts`

**Step 1: 创建 core/package.json**

```json
{
  "name": "@talent-agent/core",
  "version": "0.1.0",
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": "./dist/index.js",
      "types": "./dist/index.d.ts"
    }
  },
  "scripts": {
    "build": "tsup src/index.ts --format esm --dts",
    "dev": "tsup src/index.ts --format esm --dts --watch",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "devDependencies": {
    "tsup": "^8.3.0",
    "vitest": "^2.1.0"
  }
}
```

**Step 2: 创建 core/tsconfig.json**

```json
{
  "extends": "../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"]
}
```

**Step 3: 创建 core/src/index.ts**

```typescript
// Talent Agent Core
// 猎头业务 AI 工具核心库

export const VERSION = "0.1.0";
```

**Step 4: 安装 core 依赖**

Run: `cd core && pnpm install`
Expected: 依赖安装成功

**Step 5: 验证构建**

Run: `cd core && pnpm build`
Expected: 构建成功，生成 dist/index.js

**Step 6: 提交**

Run: `git add . && git commit -m "chore(core): init core package structure"`

---

## Phase 2: Core 类型系统

### Task 2.1: 定义核心类型

**Files:**
- Create: `core/src/types/index.ts`
- Create: `core/src/types/skill.ts`
- Create: `core/src/types/agent.ts`
- Create: `core/src/types/resume.ts`
- Create: `core/src/types/jd.ts`
- Create: `core/tests/types/skill.test.ts`

**Step 1: 创建 core/src/types/skill.ts**

```typescript
/**
 * Skill 分类
 */
export type SkillCategory = 'resume' | 'jd' | 'communication' | 'analysis';

/**
 * 支持的平台
 */
export type Platform = 'claude-code' | 'cursor' | 'continue';

/**
 * Skill 元数据
 */
export interface SkillMeta {
  /** 唯一标识符 */
  id: string;
  /** 显示名称 */
  name: string;
  /** 描述 */
  description: string;
  /** 版本号 */
  version: string;
  /** 分类 */
  category: SkillCategory;
  /** 支持的平台 */
  platforms: Platform[];
  /** 标签 */
  tags?: string[];
}

/**
 * 工具定义
 */
export interface Tool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

/**
 * 示例定义
 */
export interface Example {
  input: string;
  output: string;
  explanation?: string;
}

/**
 * Skill 完整定义
 */
export interface Skill extends SkillMeta {
  /** 提示词模板 */
  prompt: string;
  /** 可用工具 */
  tools?: Tool[];
  /** 使用示例 */
  examples?: Example[];
}
```

**Step 2: 创建 core/src/types/agent.ts**

```typescript
import type { Skill } from './skill.ts';

/**
 * Agent 元数据
 */
export interface AgentMeta {
  id: string;
  name: string;
  description: string;
  version: string;
}

/**
 * Agent 完整定义
 */
export interface Agent extends AgentMeta {
  /** 系统提示词 */
  systemPrompt: string;
  /** 可用的 Skills */
  skills: Skill[];
  /** 最大迭代次数 */
  maxIterations?: number;
}
```

**Step 3: 创建 core/src/types/resume.ts**

```typescript
/**
 * 工作经历
 */
export interface WorkExperience {
  company: string;
  title: string;
  startDate: string;
  endDate?: string;
  description?: string;
  highlights?: string[];
}

/**
 * 教育背景
 */
export interface Education {
  school: string;
  degree: string;
  major?: string;
  startDate: string;
  endDate?: string;
}

/**
 * 候选人信息
 */
export interface Candidate {
  name: string;
  email?: string;
  phone?: string;
  location?: string;
  title?: string;
  summary?: string;
  skills?: string[];
  workExperience?: WorkExperience[];
  education?: Education[];
  languages?: string[];
  certifications?: string[];
}

/**
 * 简历解析结果
 */
export interface ResumeParseResult {
  success: boolean;
  candidate?: Candidate;
  rawText?: string;
  error?: string;
}
```

**Step 4: 创建 core/src/types/jd.ts**

```typescript
/**
 * 职位要求
 */
export interface JobRequirement {
  /** 要求类型：必须/优先 */
  type: 'required' | 'preferred';
  /** 要求内容 */
  content: string;
  /** 分类 */
  category?: 'skill' | 'experience' | 'education' | 'certification' | 'other';
}

/**
 * 职位信息
 */
export interface JobDescription {
  title: string;
  company?: string;
  location?: string;
  salaryRange?: {
    min?: number;
    max?: number;
    currency?: string;
  };
  summary?: string;
  responsibilities?: string[];
  requirements?: JobRequirement[];
  benefits?: string[];
  rawText?: string;
}

/**
 * JD 解析结果
 */
export interface JDParseResult {
  success: boolean;
  jd?: JobDescription;
  error?: string;
}

/**
 * 匹配结果
 */
export interface MatchResult {
  score: number; // 0-100
  summary: string;
  strengths: string[];
  gaps: string[];
  recommendations?: string[];
}
```

**Step 5: 创建 core/src/types/index.ts**

```typescript
export * from './skill.ts';
export * from './agent.ts';
export * from './resume.ts';
export * from './jd.ts';
```

**Step 6: 创建测试 core/tests/types/skill.test.ts**

```typescript
import { describe, it, expect } from 'vitest';
import type { Skill, SkillCategory, Platform } from '../../src/types/skill.ts';

describe('Skill Types', () => {
  it('should define a valid skill', () => {
    const skill: Skill = {
      id: 'test-skill',
      name: 'Test Skill',
      description: 'A test skill',
      version: '1.0.0',
      category: 'resume',
      platforms: ['claude-code'],
      prompt: 'Test prompt',
    };

    expect(skill.id).toBe('test-skill');
    expect(skill.category).toBe('resume');
  });

  it('should allow optional fields', () => {
    const skill: Skill = {
      id: 'test',
      name: 'Test',
      description: 'Test',
      version: '1.0.0',
      category: 'jd',
      platforms: ['claude-code', 'cursor'],
      prompt: 'Test',
      tags: ['matching'],
      tools: [{ name: 'tool1', description: 'desc', parameters: {} }],
      examples: [{ input: 'in', output: 'out' }],
    };

    expect(skill.tags).toHaveLength(1);
    expect(skill.tools).toHaveLength(1);
    expect(skill.examples).toHaveLength(1);
  });
});
```

**Step 7: 运行测试**

Run: `cd core && pnpm test`
Expected: 测试通过

**Step 8: 更新 core/src/index.ts 导出类型**

```typescript
// Talent Agent Core
// 猎头业务 AI 工具核心库

export const VERSION = "0.1.0";

// Types
export * from './types/index.ts';
```

**Step 9: 验证构建和类型**

Run: `cd core && pnpm build`
Expected: 构建成功，类型声明文件生成

**Step 10: 提交**

Run: `git add . && git commit -m "feat(core): add core type definitions"`

---

## Phase 3: Skill 基础框架

### Task 3.1: 创建 Skill 基类和注册表

**Files:**
- Create: `core/src/skills/base.ts`
- Create: `core/src/skills/registry.ts`
- Create: `core/src/skills/index.ts`
- Create: `core/tests/skills/registry.test.ts`

**Step 1: 创建 core/src/skills/base.ts**

```typescript
import type { Skill, SkillMeta } from '../types/skill.ts';

/**
 * Skill 构建器
 * 用于流畅地创建 Skill 定义
 */
export class SkillBuilder {
  private skill: Partial<Skill> = {};

  meta(meta: Partial<SkillMeta>): this {
    this.skill = { ...this.skill, ...meta };
    return this;
  }

  id(id: string): this {
    this.skill.id = id;
    return this;
  }

  name(name: string): this {
    this.skill.name = name;
    return this;
  }

  description(description: string): this {
    this.skill.description = description;
    return this;
  }

  version(version: string): this {
    this.skill.version = version;
    return this;
  }

  category(category: Skill['category']): this {
    this.skill.category = category;
    return this;
  }

  platforms(...platforms: Skill['platforms']): this {
    this.skill.platforms = platforms;
    return this;
  }

  prompt(prompt: string): this {
    this.skill.prompt = prompt;
    return this;
  }

  tags(...tags: string[]): this {
    this.skill.tags = tags;
    return this;
  }

  build(): Skill {
    if (!this.skill.id) throw new Error('Skill id is required');
    if (!this.skill.name) throw new Error('Skill name is required');
    if (!this.skill.description) throw new Error('Skill description is required');
    if (!this.skill.version) throw new Error('Skill version is required');
    if (!this.skill.category) throw new Error('Skill category is required');
    if (!this.skill.platforms) throw new Error('Skill platforms is required');
    if (!this.skill.prompt) throw new Error('Skill prompt is required');

    return this.skill as Skill;
  }
}

/**
 * 创建 Skill 构建器
 */
export function defineSkill(): SkillBuilder {
  return new SkillBuilder();
}
```

**Step 2: 创建 core/src/skills/registry.ts**

```typescript
import type { Skill } from '../types/skill.ts';

/**
 * Skill 注册表
 * 管理所有已注册的 Skills
 */
class SkillRegistry {
  private skills: Map<string, Skill> = new Map();

  /**
   * 注册一个 Skill
   */
  register(skill: Skill): void {
    if (this.skills.has(skill.id)) {
      throw new Error(`Skill with id "${skill.id}" already registered`);
    }
    this.skills.set(skill.id, skill);
  }

  /**
   * 获取一个 Skill
   */
  get(id: string): Skill | undefined {
    return this.skills.get(id);
  }

  /**
   * 获取所有 Skills
   */
  getAll(): Skill[] {
    return Array.from(this.skills.values());
  }

  /**
   * 按分类获取 Skills
   */
  getByCategory(category: Skill['category']): Skill[] {
    return this.getAll().filter((s) => s.category === category);
  }

  /**
   * 按平台获取 Skills
   */
  getByPlatform(platform: Skill['platforms'][number]): Skill[] {
    return this.getAll().filter((s) => s.platforms.includes(platform));
  }

  /**
   * 检查 Skill 是否存在
   */
  has(id: string): boolean {
    return this.skills.has(id);
  }

  /**
   * 清空注册表
   */
  clear(): void {
    this.skills.clear();
  }
}

// 单例导出
export const skillRegistry = new SkillRegistry();
```

**Step 3: 创建 core/src/skills/index.ts**

```typescript
export * from './base.ts';
export * from './registry.ts';
```

**Step 4: 创建测试 core/tests/skills/registry.test.ts**

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { skillRegistry } from '../../src/skills/registry.ts';
import { defineSkill } from '../../src/skills/base.ts';

describe('SkillRegistry', () => {
  beforeEach(() => {
    skillRegistry.clear();
  });

  it('should register and retrieve a skill', () => {
    const skill = defineSkill()
      .id('test')
      .name('Test')
      .description('Test skill')
      .version('1.0.0')
      .category('resume')
      .platforms('claude-code')
      .prompt('Test prompt')
      .build();

    skillRegistry.register(skill);

    expect(skillRegistry.has('test')).toBe(true);
    expect(skillRegistry.get('test')).toEqual(skill);
  });

  it('should throw on duplicate registration', () => {
    const skill = defineSkill()
      .id('duplicate')
      .name('Duplicate')
      .description('Test')
      .version('1.0.0')
      .category('resume')
      .platforms('claude-code')
      .prompt('Test')
      .build();

    skillRegistry.register(skill);

    expect(() => skillRegistry.register(skill)).toThrow('already registered');
  });

  it('should filter by category', () => {
    const resumeSkill = defineSkill()
      .id('resume-1')
      .name('Resume')
      .description('Test')
      .version('1.0.0')
      .category('resume')
      .platforms('claude-code')
      .prompt('Test')
      .build();

    const jdSkill = defineSkill()
      .id('jd-1')
      .name('JD')
      .description('Test')
      .version('1.0.0')
      .category('jd')
      .platforms('claude-code')
      .prompt('Test')
      .build();

    skillRegistry.register(resumeSkill);
    skillRegistry.register(jdSkill);

    expect(skillRegistry.getByCategory('resume')).toHaveLength(1);
    expect(skillRegistry.getByCategory('jd')).toHaveLength(1);
  });

  it('should filter by platform', () => {
    const skill = defineSkill()
      .id('multi-platform')
      .name('Multi')
      .description('Test')
      .version('1.0.0')
      .category('resume')
      .platforms('claude-code', 'cursor')
      .prompt('Test')
      .build();

    skillRegistry.register(skill);

    expect(skillRegistry.getByPlatform('claude-code')).toHaveLength(1);
    expect(skillRegistry.getByPlatform('cursor')).toHaveLength(1);
    expect(skillRegistry.getByPlatform('continue')).toHaveLength(0);
  });
});
```

**Step 5: 运行测试**

Run: `cd core && pnpm test`
Expected: 所有测试通过

**Step 6: 更新 core/src/index.ts**

```typescript
// Talent Agent Core
// 猎头业务 AI 工具核心库

export const VERSION = "0.1.0";

// Types
export * from './types/index.ts';

// Skills
export * from './skills/index.ts';
```

**Step 7: 构建验证**

Run: `cd core && pnpm build`
Expected: 构建成功

**Step 8: 提交**

Run: `git add . && git commit -m "feat(core): add skill builder and registry"`

---

## Phase 4: 示例 Skills

### Task 4.1: 创建 resume-parse Skill

**Files:**
- Create: `core/src/skills/resume/index.ts`
- Create: `core/src/skills/resume/parse.skill.ts`
- Create: `core/src/prompts/templates/resume-parse.md`
- Create: `core/src/prompts/loader.ts`
- Create: `core/tests/skills/resume/parse.test.ts`

**Step 1: 创建 core/src/prompts/loader.ts**

```typescript
/**
 * 简单的模板加载器
 * 在构建时将模板嵌入代码
 */

// 使用 Vite 的 ?raw 导入或直接内联
const templates: Record<string, string> = {};

/**
 * 注册模板
 */
export function registerTemplate(id: string, content: string): void {
  templates[id] = content;
}

/**
 * 获取模板
 */
export function getTemplate(id: string): string | undefined {
  return templates[id];
}

/**
 * 获取所有模板 ID
 */
export function getTemplateIds(): string[] {
  return Object.keys(templates);
}
```

**Step 2: 创建 core/src/prompts/templates/resume-parse.md**

```markdown
# 简历解析

你是一位专业的猎头顾问，擅长从简历中提取关键信息。

## 任务
解析用户提供的简历文本，提取以下信息并以结构化格式返回：

## 输出格式
```json
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
```

## 注意事项
- 如果某字段信息缺失，使用 null 或空数组
- 日期格式统一为 YYYY-MM
- 技能标签尽量使用行业标准术语
- 突出与猎头匹配相关的信息

## 简历内容
{{resume}}
```

**Step 3: 创建 core/src/skills/resume/parse.skill.ts**

```typescript
import { defineSkill } from '../base.ts';
import { skillRegistry } from '../registry.ts';
import resumeParsePrompt from '../../prompts/templates/resume-parse.md?raw';

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
  .prompt(ressumeParsePrompt)
  .build();

// 自动注册
skillRegistry.register(resumeParseSkill);
```

**Step 4: 创建 core/src/skills/resume/index.ts**

```typescript
export * from './parse.skill.ts';
```

**Step 5: 创建测试 core/tests/skills/resume/parse.test.ts**

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { skillRegistry } from '../../../src/skills/registry.ts';
import { resumeParseSkill } from '../../../src/skills/resume/parse.skill.ts';

describe('resume-parse skill', () => {
  beforeEach(() => {
    skillRegistry.clear();
  });

  it('should be defined correctly', () => {
    expect(resumeParseSkill.id).toBe('resume-parse');
    expect(resumeParseSkill.name).toBe('简历解析');
    expect(resumeParseSkill.category).toBe('resume');
  });

  it('should be registered', () => {
    expect(skillRegistry.has('resume-parse')).toBe(true);
  });

  it('should have prompt template', () => {
    expect(resumeParseSkill.prompt).toContain('简历解析');
    expect(resumeParseSkill.prompt).toContain('{{resume}}');
  });

  it('should support multiple platforms', () => {
    expect(resumeParseSkill.platforms).toContain('claude-code');
    expect(resumeParseSkill.platforms).toContain('cursor');
    expect(resumeParseSkill.platforms).toContain('continue');
  });
});
```

**Step 6: 配置 Vitest 支持 raw 导入**

创建 `core/vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts'],
  },
  assetsInclude: ['**/*.md'],
});
```

**Step 7: 运行测试**

Run: `cd core && pnpm test`
Expected: 测试通过

**Step 8: 提交**

Run: `git add . && git commit -m "feat(core): add resume-parse skill"`

---

### Task 4.2: 创建 jd-analyze Skill

**Files:**
- Create: `core/src/skills/jd/index.ts`
- Create: `core/src/skills/jd/analyze.skill.ts`
- Create: `core/src/prompts/templates/jd-analyze.md`
- Create: `core/tests/skills/jd/analyze.test.ts`

**Step 1: 创建 core/src/prompts/templates/jd-analyze.md**

```markdown
# JD 分析

你是一位专业的猎头顾问，擅长分析职位描述（JD）并提取关键招聘要求。

## 任务
分析用户提供的职位描述（JD），提取以下信息并以结构化格式返回：

## 输出格式
```json
{
  "title": "职位名称",
  "company": "公司名称（如有）",
  "location": "工作地点",
  "salaryRange": {
    "min": 最低薪资（数字，单位：千/月）,
    "max": 最高薪资（数字，单位：千/月）,
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
```

## 注意事项
- 区分必须要求和优先要求
- 将要求分类以便后续匹配
- 提取薪资范围时统一单位
- 识别关键技能和经验要求

## JD 内容
{{jd}}
```

**Step 2: 创建 core/src/skills/jd/analyze.skill.ts**

```typescript
import { defineSkill } from '../base.ts';
import { skillRegistry } from '../registry.ts';
import jdAnalyzePrompt from '../../prompts/templates/jd-analyze.md?raw';

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
```

**Step 3: 创建 core/src/skills/jd/index.ts**

```typescript
export * from './analyze.skill.ts';
```

**Step 4: 创建测试 core/tests/skills/jd/analyze.test.ts**

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { skillRegistry } from '../../../src/skills/registry.ts';
import { jdAnalyzeSkill } from '../../../src/skills/jd/analyze.skill.ts';

describe('jd-analyze skill', () => {
  beforeEach(() => {
    skillRegistry.clear();
  });

  it('should be defined correctly', () => {
    expect(jdAnalyzeSkill.id).toBe('jd-analyze');
    expect(jdAnalyzeSkill.name).toBe('JD 分析');
    expect(jdAnalyzeSkill.category).toBe('jd');
  });

  it('should be registered', () => {
    expect(skillRegistry.has('jd-analyze')).toBe(true);
  });

  it('should have prompt template', () => {
    expect(jdAnalyzeSkill.prompt).toContain('JD 分析');
    expect(jdAnalyzeSkill.prompt).toContain('{{jd}}');
  });
});
```

**Step 5: 运行测试**

Run: `cd core && pnpm test`
Expected: 测试通过

**Step 6: 更新 core/src/skills/index.ts 导出所有 skills**

```typescript
export * from './base.ts';
export * from './registry.ts';

// 导出所有已注册的 skills
export * from './resume/index.ts';
export * from './jd/index.ts';
```

**Step 7: 构建验证**

Run: `cd core && pnpm build`
Expected: 构建成功

**Step 8: 提交**

Run: `git add . && git commit -m "feat(core): add jd-analyze skill"`

---

## Phase 5: Claude Code 适配层

### Task 5.1: 创建 Claude Code Plugin 结构

**Files:**
- Create: `adapters/claude-code/plugin.json`
- Create: `adapters/claude-code/package.json`
- Create: `adapters/claude-code/tsconfig.json`
- Create: `adapters/claude-code/src/index.ts`
- Create: `adapters/claude-code/README.md`

**Step 1: 创建目录结构**

Run: `mkdir -p adapters/claude-code/src`

**Step 2: 创建 adapters/claude-code/package.json**

```json
{
  "name": "@talent-agent/adapter-claude-code",
  "version": "0.1.0",
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "scripts": {
    "build": "tsup src/index.ts --format esm --dts",
    "dev": "tsup src/index.ts --format esm --dts --watch"
  },
  "dependencies": {
    "@talent-agent/core": "workspace:*"
  },
  "devDependencies": {
    "tsup": "^8.3.0",
    "typescript": "^5.7.0"
  }
}
```

**Step 3: 创建 adapters/claude-code/tsconfig.json**

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"]
}
```

**Step 4: 创建 adapters/claude-code/plugin.json**

```json
{
  "name": "talent-agent",
  "version": "0.1.0",
  "description": "猎头业务 AI 工具集 - Claude Code 适配器",
  "author": "talent-agent",
  "commands": [
    {
      "name": "parse-resume",
      "description": "解析简历，提取候选人关键信息"
    },
    {
      "name": "analyze-jd",
      "description": "分析职位描述，提取招聘要求"
    },
    {
      "name": "match-candidate",
      "description": "候选人-JD 匹配分析"
    }
  ],
  "skills": ["./skills"],
  "repository": {
    "type": "git",
    "url": "https://github.com/your-org/talent-agent"
  }
}
```

**Step 5: 创建 skills 目录和链接**

Run: `mkdir -p adapters/claude-code/skills`

创建 `adapters/claude-code/skills/resume-parse.md`:

```markdown
---
name: resume-parse
description: 解析简历文本，提取候选人的关键信息
---

# 简历解析

{{resume-parse-skill-content}}
```

创建 `adapters/claude-code/skills/jd-analyze.md`:

```markdown
---
name: jd-analyze
description: 分析职位描述（JD），提取职位要求、职责等关键信息
---

# JD 分析

{{jd-analyze-skill-content}}
```

**Step 6: 创建 adapters/claude-code/src/index.ts**

```typescript
/**
 * Talent Agent - Claude Code Adapter
 * 猎头业务 AI 工具集的 Claude Code 适配器
 */

import { skillRegistry, resumeParseSkill, jdAnalyzeSkill } from '@talent-agent/core';

// 确保所有 skills 已注册
void resumeParseSkill;
void jdAnalyzeSkill;

// 导出所有可用的 skills
export const availableSkills = skillRegistry.getAll();

// 导出适配器信息
export const adapterInfo = {
  name: 'talent-agent',
  version: '0.1.0',
  platform: 'claude-code' as const,
  skillCount: skillRegistry.getAll().length,
};
```

**Step 7: 创建 adapters/claude-code/README.md**

```markdown
# Talent Agent - Claude Code 适配器

猎头业务 AI 工具集的 Claude Code 插件。

## 安装

将此目录复制到 Claude Code 的插件目录：

```bash
cp -r adapters/claude-code ~/.claude/plugins/talent-agent
```

## 可用命令

| 命令 | 描述 |
|------|------|
| `/parse-resume` | 解析简历，提取候选人关键信息 |
| `/analyze-jd` | 分析职位描述，提取招聘要求 |
| `/match-candidate` | 候选人-JD 匹配分析 |

## Skills

### resume-parse
解析简历文本，提取以下信息：
- 候选人基本信息（姓名、联系方式）
- 工作经历
- 教育背景
- 技能标签

### jd-analyze
分析职位描述，提取：
- 职位要求（必须/优先）
- 工作职责
- 薪资范围
- 福利待遇

## 开发

```bash
# 安装依赖
pnpm install

# 构建
pnpm build

# 开发模式（监听变化）
pnpm dev
```

## 许可证

MIT
```

**Step 8: 安装依赖并构建**

Run: `cd adapters/claude-code && pnpm install && pnpm build`
Expected: 依赖安装成功，构建成功

**Step 9: 提交**

Run: `git add . && git commit -m "feat(adapter): add claude-code adapter"`

---

### Task 5.2: 创建 Commands

**Files:**
- Create: `adapters/claude-code/src/commands/parse-resume.ts`
- Create: `adapters/claude-code/src/commands/analyze-jd.ts`
- Create: `adapters/claude-code/src/commands/match-candidate.ts`

**Step 1: 创建 adapters/claude-code/src/commands/parse-resume.ts**

```typescript
/**
 * /parse-resume 命令
 * 解析简历文本
 */

export const parseResumeCommand = {
  name: 'parse-resume',
  description: '解析简历，提取候选人关键信息',
  prompt: `你是一位专业的猎头顾问。请解析用户提供的简历内容，提取结构化的候选人信息。

请按以下格式输出：
1. 基本信息：姓名、联系方式、所在地
2. 当前职位：职位名称、公司
3. 核心技能：列出主要技能标签
4. 工作经历：按时间倒序列出
5. 教育背景：学历信息
6. 亮点总结：2-3 句话概括候选人优势

如果信息不完整，请标注"未提供"。

请等待用户输入简历内容。`,
};
```

**Step 2: 创建 adapters/claude-code/src/commands/analyze-jd.ts**

```typescript
/**
 * /analyze-jd 命令
 * 分析职位描述
 */

export const analyzeJdCommand = {
  name: 'analyze-jd',
  description: '分析职位描述，提取招聘要求',
  prompt: `你是一位专业的猎头顾问。请分析用户提供的职位描述（JD），提取关键招聘信息。

请按以下格式输出：
1. 职位概述：职位名称、地点、薪资范围
2. 核心职责：3-5 条主要工作内容
3. 必备要求：必须满足的条件
4. 优先要求：加分项
5. 关键词标签：用于搜索候选人的关键词

如果信息不完整，请标注"未提供"。

请等待用户输入 JD 内容。`,
};
```

**Step 3: 创建 adapters/claude-code/src/commands/match-candidate.ts**

```typescript
/**
 * /match-candidate 命令
 * 候选人-JD 匹配分析
 */

export const matchCandidateCommand = {
  name: 'match-candidate',
  description: '候选人-JD 匹配分析',
  prompt: `你是一位专业的猎头顾问。请分析候选人与职位的匹配度。

你将收到：
1. 候选人简历或信息
2. 职位描述（JD）

请输出匹配分析报告：
1. **匹配度评分**：0-100 分
2. **匹配亮点**：候选人符合要求的方面
3. **差距分析**：候选人不足或缺失的方面
4. **推荐建议**：是否推荐、推荐理由、面试建议
5. **面试重点**：建议在面试中重点考察的方面

请等待用户依次输入候选人信息和 JD。`,
};
```

**Step 4: 创建 commands index**

创建 `adapters/claude-code/src/commands/index.ts`:

```typescript
export * from './parse-resume.ts';
export * from './analyze-jd.ts';
export * from './match-candidate.ts';

export const allCommands = [
  parseResumeCommand,
  analyzeJdCommand,
  matchCandidateCommand,
];
```

**Step 5: 更新 adapters/claude-code/src/index.ts**

```typescript
/**
 * Talent Agent - Claude Code Adapter
 */

import { skillRegistry, resumeParseSkill, jdAnalyzeSkill } from '@talent-agent/core';
export * from './commands/index.ts';

// 确保所有 skills 已注册
void resumeParseSkill;
void jdAnalyzeSkill;

export const availableSkills = skillRegistry.getAll();

export const adapterInfo = {
  name: 'talent-agent',
  version: '0.1.0',
  platform: 'claude-code' as const,
  skillCount: skillRegistry.getAll().length,
};
```

**Step 6: 构建**

Run: `cd adapters/claude-code && pnpm build`
Expected: 构建成功

**Step 7: 提交**

Run: `git add . && git commit -m "feat(adapter): add claude-code commands"`

---

## Phase 6: 文档与收尾

### Task 6.1: 创建项目 README

**Files:**
- Create: `README.md`
- Create: `docs/guides/getting-started.md`

**Step 1: 创建根 README.md**

```markdown
# Talent Agent

猎头业务 AI 工具插件库 - 让 AI 成为猎头的得力助手。

## 概述

Talent Agent 是一个专为猎头业务设计的 AI 工具集，提供：

- 📄 **简历解析** - 自动提取候选人关键信息
- 📋 **JD 分析** - 智能分析职位要求
- 🎯 **匹配分析** - 候选人-职位匹配度评估
- ✉️ **沟通辅助** - 邮件撰写、面试提纲等

## 架构

```
talent-agent/
├── core/               # 核心业务逻辑（平台无关）
├── adapters/           # 平台适配器
│   └── claude-code/    # Claude Code 插件
├── services/           # API 服务（未来）
└── docs/               # 文档
```

## 快速开始

### 前置要求

- Node.js >= 20
- pnpm >= 9

### 安装

```bash
pnpm install
```

### 构建

```bash
pnpm build
```

### 安装 Claude Code 插件

```bash
# 将适配器复制到 Claude Code 插件目录
cp -r adapters/claude-code ~/.claude/plugins/talent-agent
```

## 使用

在 Claude Code 中使用以下命令：

- `/parse-resume` - 解析简历
- `/analyze-jd` - 分析 JD
- `/match-candidate` - 匹配分析

## 开发

```bash
# 运行测试
pnpm test

# 代码检查
pnpm lint

# 格式化
pnpm format
```

## 许可证

MIT
```

**Step 2: 创建 docs/guides/getting-started.md**

```markdown
# 快速开始指南

本指南帮助你快速上手 Talent Agent 开发。

## 项目结构

### Core 层

`core/` 目录包含平台无关的核心业务逻辑：

- `src/types/` - TypeScript 类型定义
- `src/skills/` - Skill 定义和注册表
- `src/prompts/` - Prompt 模板

### 适配层

`adapters/` 目录包含各平台的适配器：

- `claude-code/` - Claude Code 插件

## 添加新 Skill

1. 在 `core/src/prompts/templates/` 创建 Prompt 模板
2. 在 `core/src/skills/<category>/` 创建 Skill 定义
3. 在适配层添加对应的 Command（如需要）

### 示例：添加邮件撰写 Skill

```typescript
// core/src/skills/communication/email.skill.ts
import { defineSkill } from '../base.ts';
import { skillRegistry } from '../registry.ts';

export const emailDraftSkill = defineSkill()
  .id('email-draft')
  .name('邮件撰写')
  .description('根据场景生成专业的猎头沟通邮件')
  .version('1.0.0')
  .category('communication')
  .platforms('claude-code')
  .prompt(emailDraftPrompt)
  .build();

skillRegistry.register(emailDraftSkill);
```

## 测试

所有代码都应该有对应的测试：

```bash
# 运行所有测试
pnpm test

# 监听模式
pnpm test:watch
```

## 构建与发布

```bash
# 构建所有包
pnpm build

# 构建 Core
cd core && pnpm build

# 构建适配器
cd adapters/claude-code && pnpm build
```
```

**Step 3: 提交**

Run: `git add . && git commit -m "docs: add README and getting started guide"`

---

### Task 6.2: 最终验证

**Step 1: 运行完整测试套件**

Run: `pnpm test`
Expected: 所有测试通过

**Step 2: 运行构建**

Run: `pnpm build`
Expected: 所有包构建成功

**Step 3: 运行代码检查**

Run: `pnpm lint`
Expected: 无错误

**Step 4: 格式化代码**

Run: `pnpm format`
Expected: 代码格式化完成

**Step 5: 最终提交**

Run: `git add . && git commit -m "chore: mvp complete - talent-agent v0.1.0"`

---

## 完成检查清单

- [ ] Monorepo 基础结构
- [ ] Core 类型系统
- [ ] Skill 基类和注册表
- [ ] resume-parse Skill
- [ ] jd-analyze Skill
- [ ] Claude Code 适配器
- [ ] Commands（parse-resume, analyze-jd, match-candidate）
- [ ] 项目文档
- [ ] 测试通过
- [ ] 构建成功
