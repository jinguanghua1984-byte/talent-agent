# GBrain Pilot Report For Talent-Agent Second Brain

## Pilot Setup

- GBrain version: `gbrain 0.42.40.0`
- Bun version: `1.3.14`
- Install mode: Bun global install from `github:garrytan/gbrain`
- Isolated brain home: `artifacts/gbrain-pilot/smoke/home`
- Brain engine: local PGLite initialized with `gbrain init --pglite --no-embedding`
- Search mode: `conservative`
- Embeddings: deferred; no embedding provider key configured for this smoke test
- Source tree: `artifacts/gbrain-pilot/brain`
- Private data included: no

## Pilot Corpus

- Runtime fixture repo: `artifacts/gbrain-pilot/fixture-repo`
- Runtime fixture run: `artifacts/gbrain-pilot/fixture-run/jd-tencent-multimodal-2026-06-12`
- Generated through current `scripts.second_brain_case.prepare_case`
- Exported through current `scripts.second_brain_gbrain.export_source_tree`
- Exported files:
  - `cases/client-tencent-games-multi-modal-algorithm-jd-tencent-multimodal-2026-06-12.md`
  - `events/events.jsonl`
- Export policy: public case pages and public events only; private case pages and private events are excluded.

## Import Result

- Command: `gbrain import artifacts/gbrain-pilot/brain --no-embed`
- Result: passed
- Import evidence:
  - `Found 1 markdown files`
  - `1 pages imported`
  - `1 chunks created`
- GBrain ignored `events/events.jsonl` because current `import` strategy is Markdown-oriented. This confirms the adapter should convert event summaries to Markdown if event data is meant to be searchable.

## Query 1: Chinese Raw Search

- Query: `多模态视频算法 顾问反馈 不认可 原因`
- Command: `gbrain search`
- Result: `No results.`
- Interpretation: keyword search without embeddings did not recall the CJK case content.

## Query 2: English Raw Search

- Query: `multi modal algorithm feedback`
- Command: `gbrain search`
- Result: `No results.`
- Interpretation: natural English terms did not match the imported page strongly enough in no-embedding mode.

## Query 3: Slug/Token Raw Search

- Query: `client tencent games multi modal algorithm`
- Command: `gbrain search`
- Result: one hit
- Hit: `cases/client-tencent-games-multi-modal-algorithm-jd-tencent-multimodal-2026-06-12`
- Evidence quality: source slug and title are visible; content preview includes JD profile text.
- Interpretation: exact-ish slug/title token search works, but this is not enough for JD calibration because operators will ask natural questions.

## Query 4: Natural Language Query

- Query: `针对新的多模态视频算法 JD，历史顾问反馈提示我应该如何调整推荐理由？请列出引用和不知道的缺口。`
- Command: `gbrain query`
- Result: `No results.`
- Interpretation: without embeddings, current GBrain query path does not yet provide the synthesis/citation/gap-analysis value we wanted to reuse.

## Query 5: Slug-Mixed Query

- Query: `client_tencent_games multi_modal_algorithm 顾问反馈 推荐理由`
- Command: `gbrain query`
- Result: `No results.`
- Interpretation: even with identifiers, `gbrain query` did not retrieve in this low-cost configuration.

## Direct Page Read

- Command: `gbrain get cases/client-tencent-games-multi-modal-algorithm-jd-tencent-multimodal-2026-06-12`
- Result: passed
- Output preserved the public case content and evidence links.
- Interpretation: import and storage are healthy; the problem is retrieval/query quality in the current no-embedding conservative setup.

## Comparison Against Local Fallback

- Local fallback strengths:
  - Deterministic for known client/JD family naming.
  - Works without external tools or model/provider keys.
  - Already renders source refs and L0 guardrails.
- GBrain strengths observed:
  - Installs and initializes locally with PGLite.
  - Imports Markdown directories quickly.
  - Stores and retrieves exact pages through `list` and `get`.
  - Search can hit exact slug/title tokens.
- GBrain weaknesses observed:
  - No useful natural-language recall without embeddings.
  - Chinese keyword search did not match the CJK case content in this pilot.
  - `query` returned no synthesis, citations, or gap analysis in no-embedding mode.
  - JSONL events are ignored by Markdown import unless converted to Markdown.

## Recommendation

Decision: `keep_optional_adapter`

Rationale:

- GBrain should remain the primary candidate for a derived index/synthesis layer, but this pilot does not justify making it the preferred query path yet.
- The current local fallback is more reliable for JD calibration in the absence of embeddings.
- The next useful GBrain pilot requires either an embedding provider key or a Markdown/event shape optimized for GBrain search.
- The adapter work should focus on safe source-tree export and optional CLI wrappers, not workflow-critical adoption.

Next changes:

- Keep `export_source_tree` and private-event filtering.
- Do not switch `build_historical_calibration` to GBrain-first yet.
- Add a runbook documenting local setup, conservative mode, no-private-data policy, and the need for embeddings before deeper adoption.
- If the user wants a second pilot, configure a dedicated embedding provider and rerun import/search/query on the same corpus before changing JD delivery behavior.
