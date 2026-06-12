# GBrain Second Brain Runbook

## Boundary

- Talent-Agent repo artifacts are the fact source.
- GBrain is a derived, rebuildable index/synthesis layer.
- JD delivery must not fail because GBrain is unavailable.
- Current adoption decision is `keep_optional_adapter`.
- Private case import requires explicit access-policy approval.

## Current Pilot Result

- GBrain version tested: `0.42.40.0`
- Local engine tested: PGLite with `--no-embedding`
- Search mode tested: `conservative`
- Import result: Markdown public case import worked.
- Query result: natural-language Chinese and English queries returned `No results` without embeddings.
- Decision: keep local fallback primary; do not make GBrain the JD calibration default until an embedding-enabled pilot proves better recall and citations.

## Local Setup

```bash
export PATH="$HOME/.bun/bin:$PATH"
gbrain --version
gbrain doctor --json
```

For isolated smoke tests:

```bash
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain init --pglite --no-embedding
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain config set search.mode conservative
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain doctor --json
```

## Source Export

Use only the safe source-tree exporter for GBrain pilots:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from scripts.second_brain_gbrain import export_source_tree
export_source_tree(repo_root=Path("."), out_dir=Path("artifacts/gbrain-pilot/brain"))
PY
```

The exporter includes:

- `docs/second-brain/cases/*.md`
- public events from `data/second-brain/events.jsonl`

The exporter excludes:

- `data/second-brain/private-cases/`
- private events
- `data/talent.db`
- raw platform captures, cookies, contact details, profile URLs, and tokens

## Import And Query

```bash
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain import "$(pwd)/artifacts/gbrain-pilot/brain" --no-embed
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain search "client tencent games multi modal algorithm"
HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain query "multi modal algorithm historical feedback"
```

Expected with no embeddings:

- exact slug/title search may work;
- natural-language query may return `No results`;
- this is not enough to replace local fallback.

## Troubleshooting

- Missing binary: keep using local fallback; adapter reports `gbrain_unavailable`.
- Missing embedding provider: initialize with `--no-embedding`, but do not expect good natural-language recall.
- Search mode prompt: use `conservative` for low-cost pilots unless the user explicitly approves another mode.
- Private data concern: stop and inspect the exported source tree before import.
- JSONL events not searchable: convert public event summaries to Markdown before expecting GBrain import to index them.

## Next Adoption Gate

Before making GBrain the preferred JD calibration path, run a second pilot with a dedicated embedding provider and prove:

- natural-language Chinese calibration queries retrieve relevant cases;
- outputs include useful citations/source references;
- gap analysis is better than local fallback;
- no private case/event data is imported.
