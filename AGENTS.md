# AGENTS.md

本仓库采用运行时中立的 agent 架构。

## 工作流入口

通用工作流位于 `agents/workflows/<name>/AGENT.md`。运行时适配器必须读取 canonical workflow 后再执行。

## 可执行代码

Python 代码位于 `scripts/`。运行时目录不得保存业务脚本，只能保存入口适配文件。

## 验证

完成改造后运行：

```bash
python -m pytest tests scripts -q
```

## 沟通

默认使用中文交流；代码注释和文档也使用中文。
