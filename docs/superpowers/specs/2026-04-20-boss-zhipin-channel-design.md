---
id: FEAT-013
title: platform-match 新增 Boss 直聘渠道
category: FEAT
status: pending
created: 2026-04-20
updated: 2026-04-20
---

# FEAT-013 | platform-match 新增 Boss 直聘渠道

**日期**: 2026-04-20
**前置文档**: `docs/superpowers/specs/2026-04-15-platform-match-redesign-design.md` (FEAT-012)
**状态**: 已确认，待实施

---

## 一、背景与目标

### 1.1 背景

platform-match 当前仅支持脉脉渠道（`maimai`）。Boss 直聘是中国最大的招聘平台之一，其人才搜索功能是招聘工作流的重要补充。

### 1.2 目标

- 新增 `boss` 渠道，支持 Boss 直聘 `/web/chat/search` 页面的人才搜索
- 复用现有 adapter 架构，实现 `BossAdapter`
- 支持全部三种执行模式（候选丰富 / JD 驱动 / 对话式）
- 后续可扩展到 Boss 直聘的其他页面

### 1.3 约束

- Boss 直聘搜索 API 结构未知，需先调研
- 采用 API 拦截模式（与脉脉一致），通过 `page.evaluate(fetch)` 在已登录浏览器上下文中调用
- 不修改现有基础设施代码（session.py, enrich.py, rate_limiter.py）

---

## 二、架构

### 2.1 文件结构

```
platform-match/
├── scripts/adapters/
│   ├── base.py          # 不变
│   ├── maimai.py        # 不变
│   └── boss.py          # 新增 — Boss 直聘适配器
├── references/
│   ├── maimai/          # 不变
│   └── boss/            # 新增
│       ├── api-reference.md    # 搜索 API 请求/响应规格
│       ├── field-mapping.md    # API 字段 → candidate.schema 映射表
│       └── anti-detect.md      # 反检测策略
└── (其余文件不变)
```

### 2.2 注册方式

`search.py` 中 `ADAPTERS` 字典新增：

```python
ADAPTERS = {
    "maimai": MaimaiAdapter(),
    "boss": BossAdapter(),  # 新增
}
```

### 2.3 不修改的文件

| 文件 | 原因 |
|------|------|
| `session.py` | 共享 CDP 连接，天然支持 |
| `enrich.py` | 通过 `map_to_schema` 输出标准格式 |
| `rate_limiter.py` | 已按 platform 独立配额 |
| `base.py` | 协议定义不变 |
| `batch_progress.py` | 按 platform 字段区分 |

---

## 三、实施阶段

### 阶段 1：API 调研（无代码产出）

**目标**：抓取并记录 Boss 直聘搜索页面的 API 调用链。

**操作步骤**：

1. 用户打开 Chrome（已登录 Boss 直聘），开启 DevTools Network 面板
2. 在 `/web/chat/search` 页面执行几次搜索：
   - 不同关键词搜索
   - 带城市筛选搜索
   - 带学历/工作年限筛选搜索
3. 记录以下信息：
   - 搜索 API 端点 URL
   - HTTP 方法（GET/POST）
   - 请求参数结构（关键词、城市、学历、工作年限、分页等）
   - 请求头（必要的 cookies/tokens/特殊 header）
   - 响应结构（候选人列表字段、分页信息、总量）
   - 详情 API 端点（如有）
   - 是否有加密/签名机制

**交付物**：

- `references/boss/api-reference.md` — API 请求/响应规格
- `references/boss/field-mapping.md` — 字段映射表
- `references/boss/anti-detect.md` — 反检测策略

**验收标准**：

- 能用 `page.evaluate(fetch)` 成功发起搜索请求并获取 JSON 响应
- 字段映射表覆盖 candidate.schema 的核心字段
- 明确了搜索、详情两个 API 端点

### 阶段 2：适配器实现

**目标**：基于调研结果实现 `BossAdapter`。

**交付物**：

- `adapters/boss.py` — 完整的 Boss 直聘适配器
- `search.py` 中注册 `ADAPTERS["boss"]`

**验收标准**：

- 通过 `PlatformAdapter` 协议的所有方法
- 三种模式（候选丰富 / JD 驱动 / 对话式）均可用
- 搜索结果正确映射到 candidate.schema
- 与现有 session/rate_limiter/enrich 基础设施无缝集成

---

## 四、BossAdapter 核心设计

### 4.1 API 调用方式

与脉脉相同，使用 `page.evaluate(fetch)` 在已登录浏览器上下文中发起请求：

```python
response = await page.evaluate(
    """async ({url, data}) => {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
            credentials: 'include',
        });
        return { status: resp.status, body: await resp.text() };
    }""",
    {"url": BOSS_SEARCH_API_URL, "data": request_data},
)
```

### 4.2 搜索参数构建

#### 模式 1（候选丰富）

双路径搜索（与脉脉一致）：

```
路径 A: query = "{name} {current_company}"
  → 精确度高，但如果人已跳槽可能搜不到

路径 B: query = "{name} {current_title}"
  → 覆盖面广，但同名干扰多

执行顺序: 先 A → 有结果用 A → 无结果走 B → 都无 → 标记"未找到"
```

#### 模式 2（JD 驱动）

Claude 从 JD 中提取搜索条件，构建多组 `SearchParams`：
- 基础组：关键词 + 城市筛选
- 增强组：根据用户策略添加学历、工作年限等筛选

#### 模式 3（对话式）

用户自然语言 → Claude 解析为 `SearchParams` → 执行搜索。

#### 具体支持的筛选参数

取决于 API 调研结果，预估支持：

| 参数 | 对应 candidate.schema | 说明 |
|------|---------------------|------|
| 关键词 | `name` / 搜索 query | 文本搜索 |
| 城市 | `city` | 可选筛选 |
| 学历 | `education` | 可选筛选 |
| 工作年限 | `work_years` | 可选筛选 |

> 注：最终支持的筛选参数以阶段 1 调研结果为准。

### 4.3 字段映射（预估）

基于 Boss 直聘搜索结果页通常展示的信息，预估以下映射。阶段 1 完成后校准。

| Boss API 字段（预估） | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| `name` / `encryptUserName` | `name` | 直接映射 |
| `cityName` | `city` | 直接映射 |
| `brandName` | `current_company` | 直接映射 |
| `jobName` | `current_title` | 直接映射 |
| `degree` | `education` | 枚举映射（需校准） |
| `workYear` | `work_years` | 数字直接映射 |
| `goldHunter` | `status` | 求职状态映射 |
| `skills[]` | `skill_tags` | 直接映射 |
| `experienceList[]` | `work_experience[]` | 需结构转换 |
| `educationList[]` | `education_experience[]` | 需结构转换 |

### 4.4 sources[] 记录

搜索结果写入 candidate 时，追加 source：

```json
{
    "channel": "boss",
    "url": "https://www.zhipin.com/web/chat/search?...",
    "platform_id": "boss_user_id",
    "found_at": "2026-04-20T10:00:00",
    "enrichment_level": "enriched",
    "match_confidence": 95,
    "match_path": "A",
    "snapshot": {
        "company_at_source": "字节跳动",
        "position_at_source": "产品经理"
    }
}
```

---

## 五、频率控制

### 5.1 Boss 直聘独立配额（初始保守值）

| 参数 | CDP 模式 | Headless 模式 |
|------|---------|-------------|
| 单次搜索间隔 | 5-10s | 10-20s |
| 单批搜索上限 | 20 | 10 |
| 每日搜索上限 | 150 | 60 |
| 连续操作上限 | 每 30 分钟暂停 60-120s | 每 20 分钟暂停 60-120s |
| 单页翻页间隔 | 2-5s | 5-10s |

> 注：初始值偏保守，实测后根据实际风控表现调整。rate_limiter 天然支持按 platform 独立配额。

### 5.2 rate_limiter 使用

```bash
python scripts/rate_limiter.py status --platform boss
python scripts/rate_limiter.py tick --platform boss
```

---

## 六、Session 验证

### 6.1 登录态检查

`session.py verify --platform boss` 需检查 Boss 直聘登录态：

- 访问 Boss 直聘页面，检查是否跳转到登录页
- 或调用一个轻量 API（如用户信息接口）确认 token 有效

### 6.2 Cookies 备份

与脉脉共享 `data/session/` 目录，按平台前缀区分：

- `data/session/boss-cookies-<timestamp>.json`
- 保留策略：最多 3 份

---

## 七、错误处理

### 7.1 Boss 直聘特有错误场景

| 场景 | 级别 | 处理 |
|------|------|------|
| Boss 登录态过期 | P0 | 提示重新登录 Boss 直聘 |
| 搜索频率限制（429） | P1 | 自动等待 + 重试 |
| 验证码触发 | P0 | 立即停止，提示用户手动处理 |
| 搜索结果为空 | P2 | 标记"平台未收录" |
| API 返回非预期结构 | P1 | 记录原始响应，跳过当前搜索 |
| 请求超时（> 15s） | P1 | 自动重试 1 次 |

### 7.2 错误返回格式

与现有格式一致：

```json
{"status": "ok", "data": {...}}
{"status": "error", "code": "SESSION_EXPIRED", "message": "Boss 直聘登录态过期", "retryable": false}
```

### 7.3 反检测策略

- 请求间隔随机化（非固定间隔）
- User-Agent 保持与浏览器一致（使用 `page.evaluate` 天然满足）
- 单次搜索翻页不超过 3 页
- 连续搜索 30 分钟后暂停 60-120s
- 不在凌晨高频请求
- 详见 `references/boss/anti-detect.md`

---

## 八、后续扩展

本阶段仅实现搜索页面 (`/web/chat/search`)。后续可扩展：

| 页面 | 用途 | 优先级 |
|------|------|--------|
| 候选人详情页 | 获取更完整的候选人信息 | P1 |
| 牛人推荐页 | 平台推荐候选人列表 | P2 |
| 沟通页面 | 自动打招呼/发送消息 | P3 |

每个新页面的扩展方式相同：在 `BossAdapter` 中新增方法，或在 `adapters/` 下创建子模块。
