---
name: platform-match
description: "招聘平台候选人搜索与信息丰富。在脉脉、Boss直聘等招聘平台上搜索候选人，丰富候选人库信息，或根据 JD/条件搜索目标人选。触发词: 匹配候选人、搜索脉脉、搜索Boss、平台找人、丰富候选人、platform match、/platform-match"
---

# platform-match 工作流

## 触发入口

```
/platform-match                              → 对话式（模式 3）
/platform-match --candidates <filter>        → 候选丰富（模式 1）
/platform-match --candidates batch:<batch-id> → 候选丰富（模式 1，从批次读取）
/platform-match --jd <id|file>               → JD 驱动（模式 2）
/platform-match --headless                   → 降级模式（附加在任意模式上）
/platform-match --platform <name>            → 平台选择（附加在任意模式上）
```

降级模式标志: `--headless` 参数。影响: 更保守的速率控制、更低的操作上限。

平台选择: `--platform` 参数。支持: maimai（脉脉）、boss（Boss直聘）。
- 传入 --platform → 直接使用，不询问
- 不传 → 交互式询问用户选择平台
- 模式 3（对话式）始终在搜索前确认平台

## 前置检查（所有模式共用）

1. 检查 Python 环境: `python --version` (需 3.11+)
2. 检查 Playwright: `python -c "from playwright.async_api import async_playwright"`
3. 检查 session 状态:
   - maimai（默认模式）: `python -m scripts.platform_match.session status`
   - maimai（降级模式）: `python -m scripts.platform_match.session verify --platform maimai --mode standalone`
   - boss: 执行 Chrome 状态检测（步骤 3a）

3a. Boss: `python -m scripts.platform_match.session chrome-check`
    解析返回的 `chrome_state` 字段:

    - `not_running` → 执行启动命令:
      ```bash
      cmd /c 'start chrome --remote-debugging-port=9222 --user-data-dir=%TEMP%\chrome-debug https://www.zhipin.com'
      ```
      提示用户: "已启动 Chrome 并打开 Boss 直聘，请完成登录后告知我"
      等待用户确认后，回到步骤 3a 重新检测

    - `running_no_debug` → 执行重启命令:
      ```bash
      taskkill /F /IM chrome.exe && cmd /c 'start chrome --remote-debugging-port=9222 https://www.zhipin.com'
      ```
      提示用户: "已重启 Chrome（session 不保留），请重新登录 Boss 直聘后告知我"
      等待用户确认后，回到步骤 3a 重新检测

    - `running_with_debug` → 检查 `zhipin_pages` 数组:
      - 数组非空 → Boss 页面已打开，进入步骤 4
      - 数组为空 → 提示用户: "Chrome 已开启调试端口，但未检测到 Boss 直聘页面。
        请在 Chrome 中打开 https://www.zhipin.com 并登录后告知我"
      等待用户确认后，回到步骤 3a 重新检测

4. 如果 session 不可用（仅 maimai）:
   - maimai → 提示用户: "请先启动 Chrome: `chrome --remote-debugging-port=9222`"

注意: Boss 渠道**禁止**调用 `session.py verify --mode cdp`，
该命令会 new_page() 触发 browser-check.min.js 导致强制登出。
参考 `agents/workflows/platform-match/references/boss/search-mechanism.md` 已知限制。

## 资源索引

| 场景 | 文件 |
|------|------|
| 脉脉 API 规格 | `agents/workflows/platform-match/references/maimai/api-reference.md` |
| 脉脉字段映射 | `agents/workflows/platform-match/references/maimai/field-mapping.md` |
| 脉脉反检测策略 | `agents/workflows/platform-match/references/maimai/anti-detect.md` |
| Boss API 规格 | `agents/workflows/platform-match/references/boss/api-reference.md` |
| Boss 字段映射 | `agents/workflows/platform-match/references/boss/field-mapping.md` |
| Boss 搜索机制 | `agents/workflows/platform-match/references/boss/search-mechanism.md` |
| 匹配策略 | `agents/workflows/platform-match/references/matching-strategy.md` |
| 身份判定规则 | `rules/identity-rules.md` |
| 人岗匹配规则 | `rules/jd-match-rules.md` |
| 公司别名 | `rules/company-aliases.json` |
| 候选人列表模板 | `agents/workflows/platform-match/assets/candidate-list-template.md` |
| 匹配报告模板 | `agents/workflows/platform-match/assets/match-report-template.md` |
| 评分报告模板 | `agents/workflows/platform-match/assets/scored-report-template.md` |

## 数据存储规范

运行时产生的数据统一存放在项目根目录 `data/` 下，**禁止**在运行时私有目录内创建 `data/` 子目录。

| 数据类型 | 存放路径 | 命名规则 | 说明 |
|----------|----------|----------|------|
| 搜索原始结果 | `data/boss-search/` | `search-{keyword}.json` | Boss 搜索完整数据（含个人信息，不提交 git） |
| 搜索原始结果 | `data/maimai-search/` | `search-{keyword}.json` | 脉脉搜索完整数据 |
| 评分结果 | `data/{platform}-search/` | `scored-{keyword}.json` | 评分后结构化数据 |
| 限频器状态 | `data/session/` | `rate-limit-state.json` | 运行时状态快照 |
| 搜索报告 | `data/output/` | `{platform}-search-{date}-{slug}.md` | 未评分搜索列表 |
| 评分报告 | `data/output/` | `{platform}-scored-{date}-{slug}.md` | 含评分的搜索结果 |
| 丰富报告 | `data/output/` | `{platform}-enrich-{date}-{slug}.md` | 模式 1 丰富结果 |
| 原始摘要 | `data/output/` | `{platform}-summary-{date}-{slug}.txt` | 原始文本 dump |
| 候选人数据 | `data/candidates/` | `{candidate-id}.json` | 已入库候选人 |
| JD 数据 | `data/jds/` | `{jd-id}.json` | 职位描述 |

路径约定：
- 工作流文档和脚本中引用数据路径时，统一使用相对于项目根目录的 `data/` 前缀
- `data/session/` 和 `data/output/` 已在 `.gitignore` 中配置，无需额外处理

### 输出文件命名规范

`data/output/` 下所有文件遵循: `{platform}-{type}-{YYYY-MM-DD}-{slug}.{ext}`

- `platform`: boss / maimai
- `type`: search（搜索列表）、scored（评分报告）、enrich（丰富报告）、summary（原始摘要）
- `slug`: 搜索关键词，空格替换为 `-`，保留中文
- 判定规则: 报告包含评分维度和分数 → `scored`，否则 → `search`
- 已有文件不重命名，仅新文件遵循此规范

## 模式 1: 候选丰富（人找人）

### 步骤 1: 选择待丰富候选人

输入 A: `--candidates batch:<batch-id>`
  1. 读取批次: `python scripts/data-manager.py batch get <batch-id>`
  2. 获取候选人列表: `python scripts/data-manager.py batch candidates <batch-id> --filter "score>0"`
  3. 展示批次摘要表格（name, company, title, score）
  4. 用户确认或筛选

输入 B: `--candidates "company=阿里巴巴"` 或 `--candidates "enrichment=raw"`
  1. 列出候选人: `python scripts/data-manager.py candidate list`
  2. 按条件过滤（agent 在内存中过滤）
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

    平台中文名映射: maimai→脉脉, boss→Boss直聘
  2.2 检查 platform_id 是否已关联
    - 在 candidates sources[] 中查找 channel="<platform>" 的记录
    - 已关联（同记录）→ 跳过搜索，提示"已有{平台中文名}数据"
    - 已关联（其他记录）→ 提示可能重复，建议去重
    - 未关联 → 执行搜索

  2.3 调用搜索
    ```bash
    python -m scripts.platform_match.search search --platform <platform> --query "<query>" --pages 1
    ```
    - 解析 JSON 输出
    - 0 结果 → 标记"平台未收录"
    - 1 结果 → 进入判定
    - 多结果 → 进入判定

  2.4 身份判定（参考 `agents/workflows/platform-match/references/matching-strategy.md`）

    **agent 在内存中执行评分**（不调用脚本）:

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
    - 如果用户提供了理由 → agent 归纳为规则 → 展示规则 → 用户确认/修改/拒绝
    - 确认 → 追加到 `rules/identity-rules.md`（标注来源日期）

  2.6 丰富写入
    ```bash
    # 映射 API 数据
    python -m scripts.platform_match.enrich map --platform <platform> --api-data '<json>'
    # 写入候选人
    python -m scripts.platform_match.enrich merge --candidate-id <id> --new-data <tmp-file>
    ```
    - 临时文件包含映射后的数据 + _source 信息
    - enrich.py 处理逐字段合并和 source 追加

  2.7 速率检查
    ```bash
    python -m scripts.platform_match.rate_limiter tick --platform <platform> [--headless]
    ```
    - 如果 allowed=false → 等待 wait_seconds → 继续

### 步骤 3: 生成报告

使用 `agents/workflows/platform-match/assets/match-report-template.md` 模板生成报告。
输出到 `data/output/{platform}-enrich-{YYYY-MM-DD}-{slug}.md`。
slug 取值: 批次 ID（如 batch-001）或候选人范围描述。

## 模式 2: JD 驱动（条件找人）

### 步骤 0: 选择平台

如果 `--platform` 已传入 → 直接使用。
未传入 → 交互式询问用户选择平台（支持: maimai、boss）。

### 步骤 1: 读取 JD 与搜索策略

输入 A: `--jd <jd-id>`
  ```bash
  python scripts/data-manager.py jd get <jd-id>
  ```

输入 B: `--jd <file-path>`
  读取本地文件

输入 C: 用户直接提供 JD 文本

然后:
1. agent 解析 JD 自动提取搜索条件（关键词、行业、职位等）
2. 获取用户搜索策略（增强层）:
   - 用户随 JD 提供 → 例: "优先大厂经验，P7 以上"
   - 用户未提供 → 系统主动询问
   - 用户可回答"没有"
3. 综合生成搜索计划（基础组 2-3 + 增强组 1-2），用户确认

### 步骤 2: 执行搜索

FOR EACH 搜索组:
  ```bash
  python -m scripts.platform_match.search search --platform <platform> --query "<query>" --pages 3
  ```
  - 默认前 3 页 = 90 条
  - 跨组去重（按 platform_id，agent 在内存中处理）

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
  3. 已存在 → 合并数据 → `python -m scripts.platform_match.enrich merge --candidate-id <id> --new-data <tmp-file>`

### 步骤 6: 生成报告

使用 `agents/workflows/platform-match/assets/candidate-list-template.md` 模板（未评分）或 `agents/workflows/platform-match/assets/scored-report-template.md` 模板（含评分）。
输出文件名: `data/output/{platform}-search-{YYYY-MM-DD}-{slug}.md` 或 `data/output/{platform}-scored-{YYYY-MM-DD}-{slug}.md`。
slug 取值: 搜索关键词，空格替换为 `-`。

## 模式 3: 对话式

### 步骤 1: 选择平台

如果 `--platform` 已传入 → 直接使用。
未传入 → 交互式询问用户选择平台（支持: maimai、boss）。

### 步骤 2: 理解搜索需求

1. 用户自然语言 → agent 解析为搜索参数
2. 展示解析结果，用户确认
3. 如有歧义 → 主动询问

### 步骤 3: 执行搜索

```bash
python -m scripts.platform_match.search search --platform <platform> --query "<query>" --pages 3
```

### 步骤 4: 展示与交互

1. 展示摘要表格（name, company, title, education, active_state）
2. 用户可选择:
   - 调整条件重新搜索
   - 选择加入候选人库（同模式 2 步骤 5）
   - 查看某人详情
   - 结束搜索

### 步骤 5: 按需写入

同模式 2 步骤 5。输出命名同模式 2 步骤 6。

## 错误处理

所有 Python 脚本通过 stdout JSON 返回结果和错误:

```json
{"status": "ok", "data": {...}}
{"status": "error", "code": "SESSION_EXPIRED", "message": "...", "retryable": false}
{"status": "error", "code": "CIRCUIT_BREAK", "message": "...", "retryable": false, "trigger_reason": "..."}
```

### 错误分级

| 级别 | 处理方式 | agent 行为 |
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

## 工作流间衔接契约

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
