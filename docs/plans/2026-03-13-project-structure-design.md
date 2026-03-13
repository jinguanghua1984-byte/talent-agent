# Talent Agent 项目结构设计

**日期**: 2026-03-13
**状态**: 已批准
**作者**: Claude + 用户

## 概述

Talent Agent 是一个猎头业务 AI 工具插件库，采用 Monorepo + 平台适配器架构，支持多平台（Claude Code、Cursor、Continue 等）复用核心业务逻辑。

## 设计目标

1. **多平台支持** - 核心逻辑一次编写，多平台复用
2. **可扩展性** - 便于添加新的 Skills、Agents 和平台适配器
3. **开源友好** - 结构清晰，便于未来对外发布
4. **渐进式开发** - MVP 阶段聚焦基础设施，逐步扩展业务功能

## 整体架构

```
talent-agent/
├── core/                       # 核心层 - 平台无关的业务逻辑
│   ├── skills/                 # Skill 定义
│   ├── agents/                 # Agent 定义
│   ├── tools/                  # 通用工具函数
│   ├── prompts/                # Prompt 模板
│   └── types/                  # TypeScript 类型定义
│
├── adapters/                   # 适配层 - 各平台实现
│   ├── claude-code/            # Claude Code Plugin
│   ├── cursor/                 # Cursor Rules (未来)
│   └── continue/               # Continue Config (未来)
│
├── services/                   # 服务层 (未来扩展)
│   └── api/                    # REST API 服务
│
├── docs/
│   ├── plans/                  # 设计文档
│   └── guides/                 # 使用指南
│
├── package.json                # Monorepo 根配置
├── pnpm-workspace.yaml         # pnpm 工作区
└── tsconfig.base.json          # 共享 TS 配置
```

## Core 层设计

```
core/
├── package.json
├── src/
│   ├── skills/                    # Skill 核心
│   │   ├── index.ts               # Skill 注册表
│   │   ├── base.ts                # Skill 基类/接口
│   │   ├── resume/                # 简历处理
│   │   ├── jd/                    # JD 分析
│   │   ├── communication/         # 沟通辅助
│   │   └── analysis/              # 数据分析
│   │
│   ├── agents/                    # Agent 核心
│   │   ├── index.ts
│   │   ├── base.ts
│   │   └── recruiter/             # 猎头 Agent
│   │
│   ├── tools/                     # 工具函数
│   │   ├── resume-parser.ts
│   │   ├── jd-extractor.ts
│   │   └── llm-helpers.ts
│   │
│   ├── prompts/                   # Prompt 模板
│   │   ├── templates/
│   │   └── loader.ts
│   │
│   └── types/                     # 类型定义
│       ├── skill.ts
│       ├── agent.ts
│       ├── resume.ts
│       └── jd.ts
```

### Skill 接口

```typescript
interface SkillMeta {
  id: string;
  name: string;
  description: string;
  version: string;
  category: 'resume' | 'jd' | 'communication' | 'analysis';
  platforms: ('claude-code' | 'cursor' | 'continue')[];
}

interface Skill extends SkillMeta {
  prompt: string;
  tools?: Tool[];
  examples?: Example[];
}
```

## Claude Code 适配层

```
adapters/claude-code/
├── plugin.json                    # Plugin 主配置
├── package.json
├── src/
│   ├── index.ts
│   ├── commands/                  # 斜杠命令
│   ├── skills/                    # Skills (引用 core)
│   ├── agents/                    # Agents
│   └── hooks/                     # Hooks
└── README.md
```

## 技术栈

| 类别 | 选择 | 理由 |
|-----|------|-----|
| 语言 | TypeScript 5.x | 类型安全，生态成熟 |
| 包管理 | pnpm + workspace | 高效，Monorepo 原生支持 |
| 构建 | tsup | 轻量快速 |
| 测试 | Vitest | 快速，与 Vite 生态一致 |
| 代码规范 | Biome | 比 ESLint+Prettier 更快 |

## MVP 范围

### 第一阶段（MVP）
- [x] 项目基础结构搭建
- [ ] Core 层框架 + 类型定义
- [ ] 2 个示例 Skill（resume-parse, jd-analyze）
- [ ] Claude Code 适配层
- [ ] 开发文档

### 后续迭代
- 更多业务 Skills（email、interview、salary 等）
- Cursor 适配器
- Continue 适配器
- 独立 API 服务

## 设计决策记录

### 为什么选择 Monorepo + 适配器模式？
- 核心逻辑只需维护一份
- 各平台特性通过适配层处理
- 便于版本管理和发布

### 为什么 MVP 只做 Claude Code？
- Claude Code 是目标用户的主要工具
- 验证架构可行性后再扩展其他平台
- 降低初期复杂度

### 为什么选择 TypeScript？
- 各 AI IDE 都有良好支持
- 类型安全，适合复杂业务逻辑
- 社区活跃，生态丰富
