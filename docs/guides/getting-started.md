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

1. 在 `core/src/prompts/templates/` 创建 Prompt 模板（可选，也可以内联）
2. 在 `core/src/skills/<category>/` 创建 Skill 定义
3. 在适配层添加对应的 Command（如需要）

### 示例：添加邮件撰写 Skill

```typescript
// core/src/skills/communication/email.skill.ts
import { defineSkill } from '../base.ts';
import { skillRegistry } from '../registry.ts';

const emailDraftPrompt = `你是一位专业的猎头顾问，擅长撰写各类沟通邮件...`;

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

然后在 `core/src/skills/index.ts` 中导出：

```typescript
export * from './communication/index.ts';
```

## 测试

所有代码都应该有对应的测试：

```bash
# 运行所有测试
pnpm test

# 监听模式
cd core && pnpm test:watch
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

## 可用的 Skills

| Skill ID | 名称 | 分类 | 描述 |
|----------|------|------|------|
| `resume-parse` | 简历解析 | resume | 从简历中提取候选人信息 |
| `jd-analyze` | JD 分析 | jd | 从职位描述中提取招聘要求 |
