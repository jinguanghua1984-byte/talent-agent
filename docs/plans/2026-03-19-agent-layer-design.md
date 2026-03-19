# Talent Agent - Agent 层设计

**日期**: 2026-03-19
**状态**: 已实现
**作者**: Claude + 用户

## 概述

Agent 层是 Talent Agent 的自主执行单元，负责处理复杂的多步骤任务。与 Skill（被动响应用户命令）不同，Agent 可以自主规划、执行和调整任务流程。

## 设计目标

1. **自主执行** - Agent 可以独立完成多步骤任务，无需用户逐步指导
2. **可复用** - 核心定义与平台无关，可跨 Claude Code、Cursor 等平台使用
3. **可扩展** - 便于添加新的 Agent 类型
4. **类型安全** - 完整的 TypeScript 类型定义

## 架构

```
core/src/agents/
├── base.ts              # Agent Builder（构建器模式）
├── registry.ts          # Agent 注册表（单例模式）
├── index.ts             # 导出入口
└── recruiter/           # 猎头 Agent 集合
    ├── index.ts
    ├── sourcing.agent.ts   # 候选人寻访 Agent
    └── jd-manager.agent.ts # 职位管理 Agent

adapters/claude-code/agents/
├── candidate-sourcing.md   # 候选人寻访 Agent（Markdown 格式）
└── jd-manager.md           # 职位管理 Agent（Markdown 格式）
```

## 类型定义

### AgentMeta

```typescript
interface AgentMeta {
  id: string;           // 唯一标识符 (3-50字符)
  name: string;         // 显示名称
  description: string;  // 描述 + 触发示例
  version: string;      // 版本号
  model: AgentModel;    // 模型选择
  color: AgentColor;    // UI 颜色标识
  platforms: Platform[]; // 支持的平台
}
```

### Agent

```typescript
interface Agent extends AgentMeta {
  systemPrompt: string;      // 系统提示词
  tools?: AgentTool[];       // 可用工具列表
  skillIds?: string[];       // 可用的 Skills
  examples?: AgentExample[]; // 触发示例
  maxIterations?: number;    // 最大迭代次数
}
```

### 枚举类型

```typescript
type AgentModel = "inherit" | "sonnet" | "opus" | "haiku";
type AgentColor = "blue" | "cyan" | "green" | "yellow" | "magenta" | "red";
type Platform = "claude-code" | "cursor" | "continue";
```

## Agent Builder

使用构建器模式创建 Agent：

```typescript
import { defineAgent } from "@talent-agent/core";

const myAgent = defineAgent()
  .id("my-agent")
  .name("我的 Agent")
  .version("1.0.0")
  .model("inherit")
  .color("blue")
  .platforms("claude-code")
  .description(`触发条件描述...`)
  .systemPrompt(`系统提示词...`)
  .skillIds("skill-1", "skill-2")
  .maxIterations(15)
  .build();
```

## Agent 注册表

单例模式管理所有 Agent：

```typescript
import { agentRegistry } from "@talent-agent/core";

// 注册
agentRegistry.register(myAgent);

// 查询
agentRegistry.get("my-agent");
agentRegistry.getByPlatform("claude-code");
agentRegistry.getByModel("sonnet");
agentRegistry.getAll();
```

## 内置 Agents

### 1. candidate-sourcing（候选人寻访）

| 属性 | 值 |
|------|-----|
| ID | `candidate-sourcing` |
| 颜色 | cyan |
| 功能 | 候选人搜索、简历解析、智能筛选 |
| 依赖 Skills | parse-resume, analyze-jd, maimai-scraper, jd-extractor |

**触发场景：**
- "帮我找一下 Java 架构师的候选人"
- "从脉脉抓取一些符合条件的候选人"
- "帮我筛选一下这个文件夹里的简历"

### 2. jd-manager（职位管理）

| 属性 | 值 |
|------|-----|
| ID | `jd-manager` |
| 颜色 | blue |
| 功能 | JD 分析、需求拆解、候选人匹配 |
| 依赖 Skills | analyze-jd, jd-extractor, parse-resume |

**触发场景：**
- "帮我整理一下这些 JD 文件"
- "分析这个职位，看看有没有合适的候选人"
- "比较一下这几个候选人和这个职位的匹配情况"

## ID 验证规则

Agent ID 必须符合以下规则：
- 长度：3-50 字符
- 只能包含：小写字母、数字、连字符
- 必须以字母或数字开头和结尾
- 格式：`^[a-z0-9]+(-[a-z0-9]+)*$`

**有效示例：**
- `candidate-sourcing`
- `jd-manager`
- `agent123`
- `my-agent-v2`

**无效示例：**
- `ab`（太短）
- `-agent`（以连字符开头）
- `my_agent`（包含下划线）

## 与 Skill 的区别

| 特性 | Skill | Agent |
|------|-------|-------|
| 触发方式 | 用户显式调用 `/skill-name` | 自动触发（基于描述匹配） |
| 执行模式 | 单次请求-响应 | 多轮迭代，自主规划 |
| 复杂度 | 简单任务 | 复杂多步骤任务 |
| 工具访问 | 可限制工具 | 可调用 Skills |

## Claude Code 适配层

Markdown 格式的 Agent 文件，放在 `adapters/claude-code/agents/` 目录：

```markdown
---
name: agent-name
description: |
  触发条件描述...

  Examples:
  <example>...</example>
model: inherit
color: blue
---

系统提示词内容...
```

## 测试

测试文件位于 `core/tests/agents/registry.test.ts`，覆盖：
- Agent 注册和获取
- 重复注册检测
- 按平台/模型过滤
- ID 格式验证

## 后续扩展

1. **更多 Agent 类型**
   - `interview-coordinator` - 面试协调
   - `offer-negotiator` - 薪资谈判
   - `market-analyst` - 市场分析

2. **Agent 编排**
   - Agent 之间的协作
   - 工作流编排
   - 状态共享

3. **监控和日志**
   - Agent 执行追踪
   - 性能指标
   - 错误恢复

## 设计决策记录

### 为什么使用 Builder 模式？
- 流畅的 API，易于阅读和编写
- 类型安全，IDE 自动补全
- 分步构建，便于验证

### 为什么需要 Agent 注册表？
- 集中管理所有 Agent
- 支持运行时查询和过滤
- 避免重复注册

### 为什么 Agent 要引用 Skill ID 而不是 Skill 对象？
- 解耦 Agent 和 Skill 的实现
- 支持跨包引用
- 便于序列化和持久化
