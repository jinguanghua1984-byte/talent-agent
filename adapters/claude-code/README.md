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
