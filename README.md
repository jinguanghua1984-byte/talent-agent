# Talent Agent

猎头顾问的综合 AI 助理 — 用 AI 加速找人、筛人、推荐全流程。

## 产品定位

面向独立猎头顾问和小型猎头公司。Sourcing 是一个场景而非全部。

项目已改造为运行时中立架构：业务工作流沉淀在 `agents/workflows/`，具体 agent 运行时只作为 adapter。Claude Code 仍受支持，但不再是唯一入口。

## MVP 覆盖

- **公域搜索** (/public-search) — 根据JD、团队画像或关键词，在公开渠道搜索候选人
- **平台匹配** (/platform-match) — 在脉脉等招聘平台搜索，丰富候选人信息
- **筛选评估** (/screen) — 候选人 vs JD 打分排序，支持规则进化
- **推荐报告** (/report) — 生成面向客户的推荐文档，支持版本迭代

## 数据流

```
公域搜索 → 候选人池 → 平台匹配 → 信息丰富
                                        ↕
              JD → 筛选评估 → 推荐报告
```

## 目录结构

- agents/workflows/ — 运行时中立的 agent 工作流定义
- agents/skills/ — 运行时中立的业务入口合同，定义语义触发、默认值和 workflow 交接
- agents/capabilities.md — 通用能力契约和运行时工具映射
- .claude/skills/ — Claude Code 兼容适配器
- scripts/ — 可执行 Python 代码和 CLI
- rules/ — 评分、公司别名、平台匹配规则
- data/ — 运行时数据存储（JD、候选人、筛选结果、报告）
- schemas/ — 数据校验 Schema

## 快速开始

1. 复制 `.env.example` 为 `.env`，配置 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_API_KEY`
2. 创建 JD: `python scripts/data-manager.py jd create jd.json`
3. 使用任意支持本仓库工作流的 agent 读取 `agents/skills/` 和 `agents/workflows/`
4. Claude Code 用户可继续使用 `/public-search`、`/platform-match`、`/screen`、`/report`
5. 评分 pipeline: `python scripts/score_pipeline.py run --jd-id <id> --source boss --search-keyword <keyword>`

## 数据管理

```bash
python scripts/data-manager.py validate    # 校验数据
python scripts/data-manager.py jd list       # 列出JD
python scripts/data-manager.py candidate list # 列出候选人
```

多台机器同步本地人才库时，不要直接覆盖 `data/talent.db`，使用同步 bundle：

```bash
python scripts/talent_sync.py status --db data/talent.db
python scripts/talent_sync.py export --db data/talent.db --out data/output/talent-sync-full.zip
python scripts/talent_sync.py verify-bundle --bundle data/output/talent-sync-full.zip
python scripts/talent_sync.py import --db data/talent.db --bundle data/output/talent-sync-full.zip
python scripts/talent_sync.py import --db data/talent.db --bundle data/output/talent-sync-full.zip --apply --confirm "确认同步人才库"
```
