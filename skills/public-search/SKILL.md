---
name: public-search
description: 公域搜索候选人——根据JD、团队画像或关键词，在公开渠道搜索候选人信息
---

# 公域搜索

## 触发

```
/public-search <搜索意图描述>
```

## 参数

`<搜索意图描述>` 可以是以下三种之一：

1. **JD 文本或 JD ID** — 从 `data/jds/` 读取 JD，提取关键要求后搜索
2. **团队画像描述** — 如"搜索字节跳动 Seedance 2.0 团队成员"
3. **自由关键词** — 如"Go语言 后端架构师 北京"

## 工具依赖

| 工具 | 用途 |
|------|------|
| `WebSearch` / `mcp__ddg-search__search` | 执行搜索 |
| `mcp__jina-reader__jina_reader` / `mcp__ddg-search__fetch_content` | 提取页面内容 |
| `mcp__github__search_users` / `mcp__github__search_code` | GitHub 渠道搜索 |
| `Read` / `Write` | 读取 JD、写入策略和结果文件 |
| `Bash` | 调用 `python scripts/data-manager.py candidate create <file>` |

## 参考文档

`skills/public-search/references/search-sources.md` — 各渠道的搜索语法、适用场景和信息提取要点。执行搜索前必须参考此文档。

## 流程

### Step 1: 理解搜索意图

判断输入类型并提取关键信息：

**JD 驱动**（输入是 JD 文本或 JD ID）：
- 读取 JD 内容：`data/jds/<id>.json`
- 提取：职位名称、技能要求、行业、公司类型、工作年限、城市
- 生成搜索关键词矩阵

**团队画像**（输入是团队/产品描述）：
- 提取：目标公司、产品线、角色类型
- 搜索该团队成员的公开信息

**自由关键词**（输入是关键词组合）：
- 直接使用关键词作为搜索基础

### Step 2: 生成搜索策略

基于意图生成搜索策略，参考 `references/search-sources.md` 选择渠道。

**策略包含：**
- 关键词组合（中英文、同义词、变体）
- 目标渠道选择及优先级
- 预计搜索量和产出

将策略写入 `data/output/public-search-<YYYY-MM-DD>-<slug>.md`，供用户确认。

**策略文件格式：**

```markdown
# 搜索策略

## 搜索意图
<一句话概括搜索目标>

## 关键词矩阵
| 组合 | 渠道 | 优先级 |
|------|------|--------|
| "CTO" + "字节跳动" site:linkedin.com | LinkedIn | 高 |
| "CTO" "字节跳动" -招聘 | Google | 高 |
| org:bytedance language:go followers:>20 | GitHub | 中 |
| ... | ... | ... |

## 渠道计划
| 渠道 | 搜索条数 | 预计有效结果 |
|------|---------|------------|
| Google | 5 | 10-20 |
| GitHub | 2 | 5-10 |
| LinkedIn | 3 | 5-15 |

## 预期产出
预计搜索 N 个渠道，提取约 X 个候选人信息
```

**等待用户确认策略后继续。** 用户可能调整关键词、增减渠道、或修改优先级。

### Step 3: 执行搜索

按策略逐条执行搜索。每个搜索步骤：

1. **调用搜索工具** — 根据渠道选择合适的工具
   - 通用搜索：`WebSearch` 或 `mcp__ddg-search__search`
   - GitHub：`mcp__github__search_users`、`mcp__github__search_code`
   - 页面提取：`mcp__jina-reader__jina_reader` 或 `mcp__ddg-search__fetch_content`

2. **提取页面内容** — 对有价值的搜索结果，读取页面全文

3. **识别候选人信息** — 从页面内容中判断是否包含候选人信息：
   - 有姓名 + 公司/职位的 → 候选人
   - 是招聘帖、广告、无关文章 → 过滤
   - 信息不完整但有关联价值的 → 记录已有信息

### Step 4: 提取候选人信息

从搜索结果中提取以下字段：

| 字段 | 必须 | 来源 |
|------|------|------|
| 姓名 | 是 | 页面内容 |
| 当前公司 | 否 | 页面内容 |
| 当前职位 | 否 | 页面内容 |
| 城市 | 否 | 页面内容 |
| 技能标签 | 否 | 推断（技术栈、专业领域） |
| 来源渠道 | 是 | 搜索渠道名称 |
| 来源 URL | 是 | 搜索结果 URL |

**提取规则：**
- 姓名是唯一必填字段，其他字段按可用性填写
- 无法确定的字段留空，不要猜测
- 技能标签从技术栈描述、项目经历中推断
- 记录发现时间作为 `found_at`

### Step 5: 输出结果

将搜索结果追加到策略文件中（在策略内容之后）：

```markdown
## 搜索结果

### 渠道 1: Google
| 姓名 | 公司 | 职位 | 城市 | 技能标签 | 来源 |
|------|------|------|------|---------|------|
| 张三 | 字节跳动 | 技术VP | 北京 | AI, 大模型 | [linkedin.com/xxx](url) |
| 李四 | 腾讯 | 首席架构师 | 深圳 | Go, 分布式 | [个人博客](url) |

### 渠道 2: GitHub
| 姓名 | 公司 | 职位 | 城市 | 技能标签 | 来源 |
|------|------|------|------|---------|------|
| 王五 | 字节跳动 | Staff Engineer | 北京 | Rust, 系统编程 | [github.com/xxx](url) |

## 统计
- 搜索渠道数：N
- 发现候选人：M 人
- 重复候选人：K 人（已合并）
```

**等待用户确认结果后继续。** 用户可以：
- 标记不需要的候选人
- 补充遗漏的信息
- 要求搜索更多渠道

### Step 6: 写入候选人池

用户确认后，将候选人写入 `data/candidates/`：

1. 为每个候选人创建临时 JSON 文件（`/tmp/cand-<slug>.json`）：

```json
{
  "name": "张三",
  "current_company": "字节跳动",
  "current_title": "技术VP",
  "city": "北京",
  "skill_tags": ["AI", "大模型"],
  "enrichment_level": "raw",
  "sources": [
    {
      "channel": "Google",
      "url": "https://linkedin.com/in/xxx",
      "found_at": "2026-04-09T10:00:00Z"
    }
  ]
}
```

2. 调用 `data-manager.py` 创建候选人：

```bash
python scripts/data-manager.py candidate create /tmp/cand-<slug>.json
```

3. 创建完成后清理临时文件

**注意：** `data-manager.py` 会自动生成 ID 和时间戳，不需要手动指定。

## 注意事项

1. **公域搜索不依赖 JD** — 搜索结果直接进入候选人池，JD 匹配由 `/screen` 完成
2. **多渠道去重** — 同一候选人可能从多个渠道发现，合并 sources 而非重复创建
3. **信息过滤** — 搜索结果中不是候选人的内容（招聘帖、广告、新闻）直接过滤
4. **信息不完整** — 无法提取完整信息的候选人，记录已有信息，`enrichment_level` 设为 `"raw"`，后续由 `/platform-match` 补充
5. **隐私边界** — 只收集公开可访问的信息，不尝试绕过登录限制或付费墙
6. **信息时效性** — 标注 `found_at` 时间，公域信息可能不是最新的
7. **幂等性** — 重复执行不会创建重复候选人（`data-manager.py` 会检测 ID 冲突）
