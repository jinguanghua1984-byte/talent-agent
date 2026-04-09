# Talent Agent

猎头顾问的综合 AI 助理 — 用 AI 加速找人、筛人、推荐全流程。

## 产品定位

面向独立猎头顾问和小型猎头公司。Sourcing 是一个场景而非全部。

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

- skills/ — 4 个 CC Skill 定义
- data/ — JSON 数据存储（JD、候选人、筛选结果、报告）
- scripts/ — 数据管理工具（data-manager.py）
- schemas/ — 数据校验 Schema

## 快速开始

1. 在 Claude Code 中安装为插件
2. 创建 JD: `python scripts/data-manager.py jd create jd.json`
3. 搜索候选人: `/public-search CTO 10年经验 AI方向`
4. 平台匹配: `/platform-match --platform maimai`
5. 筛选评估: `/screen jd-001`
6. 生成报告: `/report jd-001`

## 数据管理

```bash
python scripts/data-manager.py validate    # 校验数据
python scripts/data-manager.py jd list       # 列出JD
python scripts/data-manager.py candidate list # 列出候选人
```