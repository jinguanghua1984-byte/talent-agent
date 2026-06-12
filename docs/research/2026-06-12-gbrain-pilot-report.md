# GBrain 用于 Talent-Agent 第二大脑的 Pilot 报告

## Pilot 设置

- GBrain 版本：`gbrain 0.42.40.0`
- Bun 版本：`1.3.14`
- 安装方式：从 `github:garrytan/gbrain` 通过 Bun 全局安装
- 隔离 brain home：`artifacts/gbrain-pilot/smoke/home`
- Brain engine：本地 PGLite，通过 `gbrain init --pglite --no-embedding` 初始化
- Search mode：`conservative`
- Embeddings：deferred；本次 smoke test 未配置 embedding provider key
- Source tree：`artifacts/gbrain-pilot/brain`
- 是否包含 private data：否

## Pilot 语料

- Runtime fixture repo：`artifacts/gbrain-pilot/fixture-repo`
- Runtime fixture run：`artifacts/gbrain-pilot/fixture-run/jd-tencent-multimodal-2026-06-12`
- 通过当前 `scripts.second_brain_case.prepare_case` 生成
- 通过当前 `scripts.second_brain_gbrain.export_source_tree` 导出
- 导出文件：
  - `cases/client-tencent-games-multi-modal-algorithm-jd-tencent-multimodal-2026-06-12.md`
  - `events/events.jsonl`
- 导出策略：只包含 public case pages 和 public events；排除 private case pages 和 private events。

## 导入结果

- 命令：`gbrain import artifacts/gbrain-pilot/brain --no-embed`
- 结果：通过
- 导入证据：
  - `Found 1 markdown files`
  - `1 pages imported`
  - `1 chunks created`
- GBrain 忽略了 `events/events.jsonl`，因为当前 `import` 策略面向 Markdown。这确认了一个 adapter 设计要求：如果希望 event data 可搜索，应先把 event summaries 转成 Markdown。

## Query 1：中文原始搜索

- Query：`多模态视频算法 顾问反馈 不认可 原因`
- 命令：`gbrain search`
- 结果：`No results.`
- 解释：无 embeddings 的关键词搜索没有召回 CJK case content。

## Query 2：英文原始搜索

- Query：`multi modal algorithm feedback`
- 命令：`gbrain search`
- 结果：`No results.`
- 解释：在 no-embedding 模式下，自然英文词没有足够强地匹配导入页面。

## Query 3：Slug/Token 原始搜索

- Query：`client tencent games multi modal algorithm`
- 命令：`gbrain search`
- 结果：1 条命中
- 命中：`cases/client-tencent-games-multi-modal-algorithm-jd-tencent-multimodal-2026-06-12`
- 证据质量：source slug 和 title 可见；content preview 包含 JD profile text。
- 解释：近似精确的 slug/title token search 可用，但这不足以支撑 JD calibration，因为 operator 会用自然问题提问。

## Query 4：自然语言 Query

- Query：`针对新的多模态视频算法 JD，历史顾问反馈提示我应该如何调整推荐理由？请列出引用和不知道的缺口。`
- 命令：`gbrain query`
- 结果：`No results.`
- 解释：没有 embeddings 时，当前 GBrain query 路径尚未提供我们希望复用的 synthesis/citation/gap-analysis 价值。

## Query 5：Slug 混合 Query

- Query：`client_tencent_games multi_modal_algorithm 顾问反馈 推荐理由`
- 命令：`gbrain query`
- 结果：`No results.`
- 解释：即使带有 identifiers，`gbrain query` 在当前低成本配置下也没有完成检索。

## 直接读取页面

- 命令：`gbrain get cases/client-tencent-games-multi-modal-algorithm-jd-tencent-multimodal-2026-06-12`
- 结果：通过
- 输出保留了 public case content 和 evidence links。
- 解释：导入和存储是健康的；问题在于当前 no-embedding conservative setup 下的 retrieval/query 质量。

## 与本地 Fallback 的对比

- 本地 fallback 优势：
  - 对已知 client/JD family 命名是确定性的。
  - 不依赖外部工具或 model/provider keys。
  - 已经能渲染 source refs 和 L0 guardrails。
- 本次观察到的 GBrain 优势：
  - 可用 PGLite 本地安装和初始化。
  - 可快速导入 Markdown directories。
  - 可通过 `list` 和 `get` 存储并读取精确页面。
  - Search 可命中精确 slug/title tokens。
- 本次观察到的 GBrain 弱点：
  - 没有 embeddings 时，自然语言召回不可用。
  - 中文关键词搜索没有匹配 CJK case content。
  - `query` 没有返回 synthesis、citations 或 gap analysis。
  - JSONL events 不会被 Markdown import 索引，除非先转成 Markdown。

## 建议

决策：`keep_optional_adapter`

理由：

- GBrain 仍应保留为 derived index/synthesis layer 的 primary candidate，但本次 pilot 不足以证明它可以成为优先查询路径。
- 在缺少 embeddings 的情况下，当前本地 fallback 对 JD calibration 更可靠。
- 下一次有价值的 GBrain pilot 需要 embedding provider key，或需要更适配 GBrain search 的 Markdown/event 形态。
- Adapter 工作应聚焦在安全 source-tree export 和可选 CLI wrappers，不应进入 workflow-critical adoption。

后续改动：

- 保留 `export_source_tree` 和 private-event filtering。
- 暂时不要把 `build_historical_calibration` 切到 GBrain-first。
- 增加 runbook，记录本地 setup、conservative mode、no-private-data policy，以及深入采用前必须具备 embeddings。
- 如果用户希望做第二次 pilot，应先配置专用 embedding provider，然后用同一 corpus 重跑 import/search/query，再考虑改变 JD delivery 行为。
