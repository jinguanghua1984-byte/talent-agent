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
│   ├── src/
│   │   ├── types/      # TypeScript 类型定义
│   │   ├── skills/     # Skill 定义和注册表
│   │   └── prompts/    # Prompt 模板
│   └── tests/          # 单元测试
├── adapters/           # 平台适配器
│   └── claude-code/    # Claude Code 插件
├── docs/               # 文档
│   └── guides/         # 使用指南
└── package.json
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
