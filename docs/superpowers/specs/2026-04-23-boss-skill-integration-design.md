# Boss 直聘 Skill 主流程集成设计

> 日期: 2026-04-23
> 分支: feat/FEAT-017-boss-zhipin-channel
> 状态: 待实现

## 背景

Boss 直聘渠道的底层能力已就绪：`BossAdapter` 已实现搜索、字段映射、详情获取，并在适配器注册表、搜索脚本、session 管理、限流器中完成集成。但 SKILL.md 主流程中所有平台相关调用硬编码为 `maimai`，Boss 直聘未被接入。

## 目标

将 Boss 直聘接入 platform-match skill 的全部三种模式，使 SKILL.md 成为真正的多平台流程说明书。

## 方案：SKILL.md 参数泛化 + 条件分支

选择方案 A（参数泛化）而非方案 B（平台能力矩阵），理由：当前仅 2 个平台，YAGNI。

## 设计

### 1. 参数路由

新增 `--platform` 可选参数，附加在任意模式上：

```
/platform-match --platform boss --candidates "company=阿里巴巴"
/platform-match --platform maimai --jd jd-001
/platform-match --platform boss
```

规则：
- 传入 `--platform` → 直接使用，不询问
- 不传 → 交互式询问："在哪个平台搜索？当前支持：maimai、boss"
- 模式 3 始终在搜索前插入平台选择步骤

### 2. 前置检查

根据选定平台动态适配 session 检查：

| 平台 | 检查命令 | 不可用提示 |
|------|---------|-----------|
| maimai | `session.py verify --platform maimai --mode cdp` | "请先启动 Chrome: `chrome --remote-debugging-port=9222`" |
| boss | `session.py verify --platform boss --mode cdp` | "请确保 Chrome 已打开 Boss 直聘页面（需已有登录态）" |

降级模式同理，`--platform` 值替换 maimai。

### 3. 资源索引

补充 Boss 直聘 reference 文档：

| 文件 | 状态 | 内容 |
|------|------|------|
| `references/boss/api-reference.md` | 已存在 | API 端点、请求/响应格式 |
| `references/boss/field-mapping.md` | 新建 | 从 `boss.py` `map_to_schema()` 提取：geekWork.name 解析、geekEdu.name 解析、workList 日期格式化、学历枚举、技能标签、_source 生成 |
| `references/boss/search-mechanism.md` | 新建 | 被动拦截机制：iframe 定位、关键词输入、搜索图标点击、response listener 拦截 geeks.json、分页。与脉脉主动 fetch 的差异对比 |

不单独建"反检测策略"——Boss 的反检测就是被动拦截，属于搜索机制的一部分。

### 4. 模式 1（候选丰富）改造

纯文本替换，将 6 处 `maimai` 改为 `<platform>` 变量：

| 步骤 | 改动 |
|------|------|
| 2.2 平台关联检查 | `channel="maimai"` → `channel="<platform>"`，提示文案用平台中文名 |
| 2.3 调用搜索 | `--platform maimai` → `--platform <platform>` |
| 2.4 身份判定 | 不变（平台无关） |
| 2.6 丰富写入 | `--platform maimai` → `--platform <platform>` |
| 2.7 速率检查 | `--platform maimai` → `--platform <platform>` |

平台中文名映射：maimai→脉脉，boss→Boss直聘。

### 5. 模式 2（JD 驱动）和模式 3（对话式）改造

**模式 2**：同模式 1，纯文本替换。未传 `--platform` 时在步骤 1 前插入平台选择步骤。

**模式 3**：改造后流程：
1. 选择平台（`--platform` 已传入则跳过询问）
2. 理解搜索需求
3. 执行搜索（`--platform <platform>`）
4. 展示与交互
5. 按需写入（`enrich.py map --platform <platform>`）

### 6. 底层脚本

**零改动**。`search.py`、`enrich.py`、`session.py`、`rate_limiter.py` 均已通过 `ADAPTERS` 字典支持 boss。

`search.py` CLI 当前未暴露 city/education/work_years 筛选参数，但 SKILL.md 流程中也未使用这些参数，暂不需要改动。

## 影响范围

| 文件 | 改动类型 |
|------|---------|
| `.claude/skills/platform-match/SKILL.md` | 修改：参数路由 + 前置检查 + 资源索引 + 三种模式泛化 |
| `.claude/skills/platform-match/references/boss/field-mapping.md` | 新建 |
| `.claude/skills/platform-match/references/boss/search-mechanism.md` | 新建 |
| 底层 Python 脚本 | 无改动 |
