---
name: jd-talent-delivery
description: "JD 本地人才库推荐和飞书知识库交付。用于读取 JD、生成岗位画像、构建评分卡、匹配 data/talent.db、输出 TopN 推荐和外联表，并发布到飞书知识库 JD需求交付。"
---

# Claude Code Adapter: jd-talent-delivery

这是运行时私有入口。Canonical workflow 位于 `agents/workflows/jd-talent-delivery/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/workflows/jd-talent-delivery/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `human.confirm` -> 直接询问用户
4. 严格按 canonical workflow 执行；本文件不保存业务流程。
