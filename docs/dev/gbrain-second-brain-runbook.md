# GBrain 第二大脑运行手册

## 边界

- Talent-Agent repo 产物是事实来源。
- GBrain 是 derived、可重建的 index/synthesis layer。
- JD delivery 不得因为 GBrain 不可用而失败。
- 当前采用决策是 `keep_optional_adapter`。
- 导入 private cases 需要明确的 access-policy approval。

## 当前 Pilot 结果

- 已测试 GBrain 版本：`0.42.40.0`
- 已测试本地 engine：PGLite，使用 `--no-embedding`
- 已测试 search mode：`conservative`
- 导入结果：Markdown public case import 可用。
- Query 结果：没有 embeddings 时，自然语言中文和英文 query 返回 `No results`。
- 决策：保持本地 fallback 为主路径；在启用 embeddings 的 pilot 证明更好的召回和引用质量前，不把 GBrain 设为 JD calibration 默认路径。

## 本地 Setup

```bash
export PATH="$HOME/.bun/bin:$PATH"
gbrain --version
gbrain doctor --json
```

隔离 smoke test：

```bash
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain init --pglite --no-embedding
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain config set search.mode conservative
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain doctor --json
```

## Source 导出

GBrain pilot 只能使用安全的 source-tree exporter：

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from scripts.second_brain_gbrain import export_source_tree
export_source_tree(repo_root=Path("."), out_dir=Path("artifacts/gbrain-pilot/brain"))
PY
```

Exporter 包含：

- `docs/second-brain/cases/*.md`
- `data/second-brain/events.jsonl` 中的 public events

Exporter 排除：

- `data/second-brain/private-cases/`
- private events
- `data/talent.db`
- raw platform captures、cookies、contact details、profile URLs 和 tokens

## 导入与查询

```bash
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain import "$(pwd)/artifacts/gbrain-pilot/brain" --no-embed
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain search "client tencent games multi modal algorithm"
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain query "multi modal algorithm historical feedback"
```

无 embeddings 时的预期：

- 精确 slug/title search 可能可用；
- 自然语言 query 可能返回 `No results`；
- 这不足以替代本地 fallback。

## 故障处理

- 缺少 binary：继续使用本地 fallback；adapter 报告 `gbrain_unavailable`。
- 缺少 embedding provider：用 `--no-embedding` 初始化，但不要期待好的自然语言召回。
- Search mode prompt：低成本 pilot 使用 `conservative`，除非用户明确批准其它模式。
- Private data concern：停止并检查导出的 source tree，再执行 import。
- JSONL events 不可搜索：在期待 GBrain import 索引事件前，先把 public event summaries 转成 Markdown。

## 下一次采用门禁

在把 GBrain 设为优先 JD calibration 路径之前，需要用专用 embedding provider 跑第二次 pilot，并证明：

- 自然语言中文 calibration queries 能召回相关 cases；
- 输出包含有用的 citations/source references；
- gap analysis 优于本地 fallback；
- 没有 private case/event data 被导入。
