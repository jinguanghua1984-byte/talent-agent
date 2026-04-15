---
name: platform-match
description: "招聘平台候选人搜索与信息丰富。在脉脉等招聘平台上搜索候选人，丰富候选人库信息，或根据 JD/条件搜索目标人选。触发词: 匹配候选人、搜索脉脉、平台找人、丰富候选人、platform match、/platform-match"
---

# platform-match Skill

## 参数解析与模式路由

```
/platform-match                              → 对话式（模式 3）
/platform-match --candidates <filter>        → 候选丰富（模式 1）
/platform-match --candidates batch:<batch-id> → 候选丰富（模式 1，从批次读取）
/platform-match --jd <id|file>               → JD 驱动（模式 2）
/platform-match --headless                   → 降级模式（附加在任意模式上）
```

降级模式标志: `--headless` 参数。影响: 更保守的速率控制、更低的操作上限。

## 前置检查（所有模式共用）

1. 检查 Python 环境: `python --version` (需 3.11+)
2. 检查 Playwright: `python -c "from playwright.async_api import async_playwright"`
3. 检查 session 状态:
   - 默认模式: `python scripts/session.py status`
   - 降级模式: `python scripts/session.py verify --platform maimai --mode standalone`
4. 如果 session 不可用:
   - 默认模式 → 提示用户: "请先启动 Chrome: `chrome --remote-debugging-port=9222`"
   - 降级模式 → 提示用户: "未找到 cookies 备份，请先用默认模式执行一次"

## 资源索引

| 场景 | 文件 |
|------|------|
| 脉脉 API 规格 | `references/maimai/api-reference.md` |
| 字段映射 | `references/maimai/field-mapping.md` |
| 反检测策略 | `references/maimai/anti-detect.md` |
| 匹配策略 | `references/matching-strategy.md` |
| 身份判定规则 | `rules/identity-rules.md` |
| 人岗匹配规则 | `rules/jd-match-rules.md` |
| 公司别名 | `rules/company-aliases.json` |
| 候选人列表模板 | `assets/candidate-list-template.md` |
| 匹配报告模板 | `assets/match-report-template.md` |

## 模式 1: 候选丰富（人找人）

### 步骤 1: 选择待丰富候选人

输入 A: `--candidates batch:<batch-id>`
  1. 读取批次: `python scripts/data-manager.py batch get <batch-id>`
  2. 获取候选人列表: `python scripts/data-manager.py batch candidates <batch-id> --filter "score>0"`
  3. 展示批次摘要表格（name, company, title, score）
  4. 用户确认或筛选

输入 B: `--candidates "company=阿里巴巴"` 或 `--candidates "enrichment=raw"`
  1. 列出候选人: `python scripts/data-manager.py candidate list`
  2. 按条件过滤（Claude 在内存中过滤）
  3. 展示筛选结果
  4. 用户确认

无参数 → 交互式选择
  1. 列出所有候选人
  2. 展示摘要表格
  3. 用户自然语言筛选: "只处理前10个" / "跳过李四"
  4. 确认最终列表

过滤条件: `enrichment_level in ["raw", "partial"]`

### 步骤 2: 逐个搜索匹配

FOR EACH candidate:
  2.1 生成搜索参数
    - 路径 A: query = "{name} {current_company}"
    - 路径 B: query = "{name} {current_title}"（路径 A 无结果时降级）

  2.2 检查 platform_id 是否已关联
    - 在 candidates sources[] 中查找 channel="maimai" 的记录
    - 已关联（同记录）→ 跳过搜索，提示"已有脉脉数据"
    - 已关联（其他记录）→ 提示可能重复，建议去重
    - 未关联 → 执行搜索

  2.3 调用搜索
    ```bash
    python scripts/search.py search --platform maimai --query "<query>" --pages 1
    ```
    - 解析 JSON 输出
    - 0 结果 → 标记"平台未收录"
    - 1 结果 → 进入判定
    - 多结果 → 进入判定

  2.4 身份判定（参考 `references/matching-strategy.md`）

    **Claude 在内存中执行评分**（不调用脚本）:

    a) 加载公司别名: 读取 `rules/company-aliases.json`
    b) 对每个搜索结果打分（5 维度，总分 100）
    c) 加载身份判定规则: 读取 `rules/identity-rules.md`
    d) 应用匹配到的规则加分

    判定结果:
    - ≥ 95% → 自动选取（报告中标注"请复核"）
    - 70-94% → 向用户建议最优人选，展示评分明细，待确认
    - < 70% → 展示 Top 3 供用户选择

  2.5 用户确认后的自学习
    - 询问: "你选择这个人选的主要依据是什么？"（用户可跳过）
    - 如果用户提供了理由 → Claude 抽象为规则 → 展示规则 → 用户确认/修改/拒绝
    - 确认 → 追加到 `rules/identity-rules.md`（标注来源日期）

  2.6 丰富写入
    ```bash
    # 映射 API 数据
    python scripts/enrich.py map --platform maimai --api-data '<json>'
    # 写入候选人
    python scripts/enrich.py merge --candidate-id <id> --new-data <tmp-file>
    ```
    - 临时文件包含映射后的数据 + _source 信息
    - enrich.py 处理逐字段合并和 source 追加

  2.7 速率检查
    ```bash
    python scripts/rate_limiter.py tick --platform maimai [--headless]
    ```
    - 如果 allowed=false → 等待 wait_seconds → 继续

### 步骤 3: 生成报告

使用 `assets/match-report-template.md` 模板生成报告。
输出到 `data/output/platform-match-report.md`。

## 模式 2: JD 驱动（条件找人）

### 步骤 1: 读取 JD 与搜索策略

输入 A: `--jd <jd-id>`
  ```bash
  python scripts/data-manager.py jd get <jd-id>
  ```

输入 B: `--jd <file-path>`
  读取本地文件

输入 C: 用户直接提供 JD 文本

然后:
1. Claude 解析 JD 自动提取搜索条件（关键词、行业、职位等）
2. 获取用户搜索策略（增强层）:
   - 用户随 JD 提供 → 例: "优先大厂经验，P7 以上"
   - 用户未提供 → 系统主动询问
   - 用户可回答"没有"
3. 综合生成搜索计划（基础组 2-3 + 增强组 1-2），用户确认

### 步骤 2: 执行搜索

FOR EACH 搜索组:
  ```bash
  python scripts/search.py search --platform maimai --query "<query>" --pages 3
  ```
  - 默认前 3 页 = 90 条
  - 跨组去重（按 platform_id，Claude 在内存中处理）

### 步骤 3: 结果排序与筛选

1. 加载 `rules/jd-match-rules.md`
2. 对每个结果评分（5 维度，总分 100）:
   - 职位匹配度(30) + 技能重叠度(25) + 行业经验(20) + 学历背景(15) + 意向匹配(10)
3. 标注命中规则
4. 展示 Top N（默认 20），标注得分明细

### 步骤 4: 用户选择入库

1. 用户批量勾选要添加的候选人
2. 统一询问选择理由:
   - "你选择了以下 8 位候选人，主要考量是什么？"
   - 整体描述 → 提炼通用规则
   - 个别说明 → 提炼附加规则
   - 跳过 → 不触发规则提炼
3. 自学习: 展示规则 → 确认 → 写入 `rules/jd-match-rules.md`

### 步骤 5: 写入候选人库

FOR EACH 用户选中:
  1. 检查是否已存在（name + company 去重）
  2. 不存在 → 创建临时 JSON → `python scripts/data-manager.py candidate create <tmp-file>`
  3. 已存在 → 合并数据 → `python scripts/enrich.py merge --candidate-id <id> --new-data <tmp-file>`

### 步骤 6: 生成报告

使用 `assets/candidate-list-template.md` 模板。
输出到 `data/output/platform-match-search-list.md`。

## 模式 3: 对话式

### 步骤 1: 理解搜索需求

1. 用户自然语言 → Claude 解析为搜索参数
2. 展示解析结果，用户确认
3. 如有歧义 → 主动询问

### 步骤 2: 执行搜索

```bash
python scripts/search.py search --platform maimai --query "<query>" --pages 3
```

### 步骤 3: 展示与交互

1. 展示摘要表格（name, company, title, education, active_state）
2. 用户可选择:
   - 调整条件重新搜索
   - 选择加入候选人库（同模式 2 步骤 5）
   - 查看某人详情
   - 结束搜索

### 步骤 4: 按需写入

同模式 2 步骤 5。

## 错误处理

所有 Python 脚本通过 stdout JSON 返回结果和错误:

```json
{"status": "ok", "data": {...}}
{"status": "error", "code": "SESSION_EXPIRED", "message": "...", "retryable": false}
{"status": "error", "code": "CIRCUIT_BREAK", "message": "...", "retryable": false, "trigger_reason": "..."}
```

### 错误分级

| 级别 | 处理方式 | Claude 行为 |
|------|---------|------------|
| P0（阻塞） | 暂停，提示解决步骤 | 明确告知用户，等待用户操作后继续 |
| P1（重试） | 自动重试 1 次 | 静默处理，报告中汇总 |
| P2（跳过） | 标记状态，继续 | 报告中标注"已跳过" |
| P3（记录） | 仅记录 | 无感知 |

### 熔断恢复

触发熔断后:
1. 停止所有搜索操作
2. 通知用户: "触发熔断: {reason}，建议等待 30 分钟"
3. 用户手动确认继续 → 重置限流 → 继续
4. 或等待 30 分钟后自动提示

## Skill 间衔接契约

| 契约 | 说明 |
|------|------|
| 不修改 id | 候选人 ID 一旦生成就不变 |
| 不删除候选人 | 丰富失败的标记状态，不删除 |
| enrichment_level 只升不降 | raw → partial → enriched |
| sources 只追加不覆盖 | 新增 source 追加到数组 |
| 输出报告格式固定 | markdown，screen/report 可解析 |

## 断点恢复

模式 1 批次中断后:
1. 保存进度:
    ```bash
    python scripts/batch_progress.py create --batch-id <batch-id> --candidates '<json>'
    ```
2. 每处理一个候选人后更新状态:
    ```bash
    python scripts/batch_progress.py update --batch-id <id> --candidate-id <cand-id> --status completed --result enriched
    ```
3. 发生中断（P0 错误 / Chrome 关闭 / 用户取消）时:
   - 将当前候选人标记为 `in_progress`
   - 展示: "已处理 X/Y，剩余 Z 个"
4. 用户重新执行时检测断点:
    ```bash
    python scripts/batch_progress.py resume <batch-id>
    ```
5. 提示: "发现未完成的批次（X/Y 已完成），是否从断点继续？"
   - 用户确认 → 跳过已完成的，从 in_progress/pending 继续
   - 用户拒绝 → 从头开始
