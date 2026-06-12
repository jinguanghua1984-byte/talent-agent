# GBrain Adoption Fit For Talent-Agent Second Brain

## Decision

Status: proposed

Recommendation: run a local pilot before changing the JD delivery workflow or making GBrain the preferred query path.

Current judgment: the P0 second-brain foundation is directionally aligned with GBrain, but the open-source adoption loop is not closed. Talent-Agent has a repo-first event/case/fallback layer and a thin optional `gbrain` wrapper, but it has not yet verified current GBrain install, import, search, query/synthesis, MCP, citation quality, or gap-analysis behavior against our artifacts.

## Why We Are Evaluating GBrain

- Avoid rebuilding long-term memory, hybrid retrieval, synthesis, citations, gap analysis, graph traversal, and MCP surfaces.
- Keep Talent-Agent repo artifacts as the fact source: event ledger, public case pages, private case pages, source refs, and workflow output.
- Use GBrain only as a derived, rebuildable index until a real pilot proves operational value.
- Preserve JD delivery reliability: GBrain must never block local recommendations, Feishu publishing, BOSS/Maimai workflows, or `data/talent.db` operations.

## Current Talent-Agent Implementation

- Repo artifacts exist: `data/second-brain/events.jsonl`, `docs/second-brain/cases/`, `data/second-brain/private-cases/`, and JD run `second-brain/` outputs.
- `scripts/second_brain_gbrain.py` currently exports a zip bundle and calls `gbrain import <bundle> --brain <name>` when a binary exists.
- `scripts/second_brain_query.py` primarily uses local public case fallback and only labels status as `gbrain` if a caller supplies `gbrain_results`.
- `requirements.txt` has no `grain` or `gbrain` package dependency.
- Current tests only cover missing-binary fallback and zip bundle creation, not real GBrain behavior.

## Upstream Facts Checked

Sources checked on 2026-06-12:

- `https://github.com/garrytan/gbrain`
- `https://github.com/garrytan/gbrain/blob/master/INSTALL_FOR_AGENTS.md`
- `https://github.com/garrytan/gbrain/blob/master/docs/tutorials/connect-coding-agent.md`
- `https://github.com/garrytan/gbrain/blob/master/docs/INSTALL.md`

Observed upstream shape:

- GBrain is a Bun + TypeScript CLI, installed with `bun install -g github:garrytan/gbrain`.
- Local setup can use `gbrain init` or `gbrain init --pglite` for an embedded local brain.
- Markdown folders can be imported with `gbrain import ~/notes/`.
- Agent connection uses `gbrain serve` as an MCP stdio server; remote HTTP MCP is also documented.
- CLI querying is described through `gbrain search`, and agent-facing synthesized answers are described through `query` over MCP; some docs also refer to `gbrain query`.
- API keys are not strictly required for keyword search, but embedding/reranking/synthesis quality depends on provider keys and search mode.
- The installer guide explicitly says not to silently accept the default search mode; an operator must confirm the mode because of cost/quality tradeoffs.

Implication for Talent-Agent: our current zip import wrapper is likely the wrong abstraction. The safer adapter shape is to export a sanitized Markdown source tree, import/sync that tree into GBrain, and query through verified CLI/MCP commands with local fallback.

## Capabilities To Reuse

| Capability | Upstream evidence | Talent-Agent use | Adoption status |
| --- | --- | --- | --- |
| Local PGLite brain | README / install guide / coding-agent tutorial | isolated local pilot | unverified |
| Markdown import | coding-agent tutorial | import redacted public case pages and event summaries | unverified |
| Search | README / coding-agent tutorial | raw historical calibration retrieval | unverified |
| Query/synthesis | README / MCP protocol docs | cited calibration suggestions and gap notes | unverified |
| MCP server | install docs / coding-agent tutorial | optional Codex/agent memory tool | later |
| Search mode controls | install guide | prevent surprise spend | must gate |
| Company-brain permissions | README / tutorials | possible future shared/team memory | later |
| Graph traversal / gap analysis | README claims | richer post-delivery learning | unverified |

## Risks

- GBrain is young and fast-moving; command names and data model can drift.
- Bun/global install and postinstall migrations can fail; upstream docs mention migration recovery.
- Real value may require embedding provider keys, reranker keys, or model keys.
- Search mode defaults can create unexpected cost if accepted silently.
- Importing private case pages before access policy is defined would violate Talent-Agent data boundaries.
- GBrain may be excellent for Markdown-first personal/team memory but still too broad or operationally heavy for JD delivery P0.
- If the adapter remains zip-oriented, we may keep building against a false assumption instead of upstream reality.

## Pilot Acceptance Criteria

The pilot can pass only if all of these are true:

- Install or explicit blocker is documented with version/error evidence.
- `gbrain doctor --json` or equivalent health output is captured.
- A sanitized Talent-Agent source tree imports without private case data.
- At least three calibration queries are run against GBrain or a documented blocker explains why not.
- Query output is evaluated for source/citation quality, gap analysis quality, and actionability.
- Local fallback remains available and tested when GBrain is missing.
- Adoption decision is one of:
  - `adopt_primary_index`: GBrain becomes the preferred optional index/synthesis path.
  - `keep_optional_adapter`: GBrain stays manual/optional while local fallback remains primary.
  - `reject_for_now`: freeze or remove GBrain adapter work and document why.

## Proposed Pilot Corpus

Use public or redacted sources only:

- `docs/second-brain/cases/*.md`
- public summaries derived from `data/second-brain/events.jsonl`
- design docs under `docs/superpowers/specs/*gbrain*`
- no `data/second-brain/private-cases/`
- no `data/talent.db`
- no campaign raw details, profile URLs, contact details, cookies, or tokens

## Initial Recommendation

Proceed with the pilot, but keep GBrain optional. Do not integrate it deeper into JD delivery until the pilot demonstrates that it returns better historical calibration than current local fallback and does so with reliable source references.

The next decision gate is installation approval. If GBrain is already installed, run the smoke test in an isolated `HOME`. If it is missing, ask before installing Bun or GBrain globally.

## Local Smoke Result

- `bun --version`: `1.3.14`
- `gbrain --version`: `gbrain 0.42.40.0`
- Install mode: `curl -fsSL https://bun.sh/install | bash`, then `bun install -g github:garrytan/gbrain`
- Install note: Bun installed to `~/.bun/bin/bun` and added `~/.bun/bin` to `~/.zshrc`; GBrain installed globally through Bun.
- Bun install warning: one postinstall script was blocked by Bun; GBrain CLI still executed.
- Isolated smoke home: `artifacts/gbrain-pilot/smoke/home`
- `gbrain init --pglite`: failed without embedding provider and suggested `--no-embedding`, which confirms upstream now gates embedding setup.
- `gbrain init --pglite --no-embedding`: passed; created local PGLite brain under the isolated smoke home.
- Init detected `ANTHROPIC_API_KEY` and selected Anthropic models for expansion/chat, but embedding setup remained deferred.
- Schema migration: initialized schema version 1 to 115 with 110 migrations applied.
- `gbrain doctor --json`: parsed successfully; status was `warnings`.
- Doctor summary: 76 checks total, 69 `ok`, 7 `warn`.
- Doctor warnings: retrieval-reflex policy skill not installed, pgvector check unavailable, no embeddings yet, JSONB integrity check unavailable, missing ZeroEntropy key for configured embedding model, zero takes, and an available schema pack successor.
- `gbrain stats`: passed on empty brain; `Pages=0`, `Chunks=0`, `Embedded=0`, `Links=0`, `Tags=0`, `Timeline=0`.
- Search mode: GBrain tentatively set `conservative` because no OpenAI key was configured. The upstream installer explicitly requires operator confirmation before continuing with search mode changes.

Smoke-test conclusion: local GBrain can be installed and initialized in an isolated PGLite home without embedding keys, which is enough to proceed to a low-cost import/search pilot after the operator confirms search mode. The next gate is search mode selection; do not import Talent-Agent artifacts before that confirmation.
