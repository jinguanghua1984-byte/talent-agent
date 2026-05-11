# Maimai Recommendation Detail Targets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `talent-library search/match` recommendation outputs become the input list for `maimai-scraper` batch detail capture without requiring users to pass the full browser-exported contact list.

**Architecture:** Add a local converter that reads recommendation JSON or explicit candidate IDs, resolves maimai `source_profiles` from `TalentDB`, and writes an extension-compatible JSON with top-level `contacts`. Keep `maimai-scraper` batch detail unchanged internally, but make its import path recognize common recommendation-list containers such as `top10`, `candidates`, `matches`, and `results`.

**Tech Stack:** Python 3.11+, SQLite `TalentDB`, pytest, Chrome Extension MV3 plain JavaScript.

---

## File Structure

Create:

- `scripts/maimai_detail_targets.py` — converts recommended candidates into `maimai-scraper` contact import JSON.
- `tests/test_maimai_detail_targets.py` — focused tests for recommendation-file and candidate-id conversion.

Modify:

- `extensions/maimai-scraper/background.js` — normalize imported recommendation-shaped JSON into contacts.
- `extensions/maimai-scraper/popup.js` — pass parsed JSON object to background so it can normalize `top10/candidates/matches/results`.
- `agents/workflows/talent-library/references/scenarios.md` — document the recommended flow.
- `tasks/todo.md` — track implementation and verification.

Do not modify:

- `data/talent.db`
- `data/output/*` except user-generated outputs from manual commands.
- Existing detail import semantics in `scripts/maimai_detail_import.py`.

---

### Task 1: Add Recommendation Target Export Tests

**Files:**
- Create: `tests/test_maimai_detail_targets.py`

- [ ] **Step 1: Write tests for recommendation JSON conversion**

Create tests that:

1. Build a temp `TalentDB` with maimai candidates.
2. Write a recommendation JSON with `top10`.
3. Call `export_targets(...)`.
4. Assert the output JSON has top-level `contacts`, each contact has `id`, `trackable_token`, `name`, `company`, `position`, and `candidate_id`.

- [ ] **Step 2: Write tests for explicit candidate IDs**

Create tests that:

1. Build temp DB with one maimai candidate and one non-maimai candidate.
2. Call `export_targets(candidate_ids=[...])`.
3. Assert only the maimai candidate is exported and missing entries are reported.

- [ ] **Step 3: Run failing tests**

Run:

```bash
python -m pytest tests/test_maimai_detail_targets.py -q
```

Expected: FAIL because `scripts.maimai_detail_targets` does not exist.

---

### Task 2: Implement `maimai_detail_targets.py`

**Files:**
- Create: `scripts/maimai_detail_targets.py`

- [ ] **Step 1: Implement URL parsing**

Parse `dstu` and `trackable_token` from `profile_url` values such as:

```text
https://maimai.cn/profile/detail?dstu=166812124&trackable_token=abc
```

- [ ] **Step 2: Implement recommendation extraction**

Support these JSON containers:

- top-level list
- `top10`
- `candidates`
- `matches`
- `results`
- `items`

- [ ] **Step 3: Resolve candidates from DB**

For each item, prefer:

1. `platform_id` or parsed `dstu`
2. `candidate_id` resolved through `source_profiles(platform='maimai')`
3. `profile_url` from recommendation item or DB source profile

Skip candidates without maimai source id.

- [ ] **Step 4: Write extension-compatible JSON**

Output:

```json
{
  "exportTime": "...",
  "metadata": {
    "export_type": "maimai_detail_targets",
    "source_type": "talent_recommendation",
    "total_input": 10,
    "total_contacts": 10,
    "missing": 0
  },
  "contacts": [],
  "totalContacts": 10,
  "missing": []
}
```

- [ ] **Step 5: Add CLI**

Commands:

```bash
python scripts/maimai_detail_targets.py from-file --input <recommendation.json> --db data/talent.db --out data/output/maimai-detail-targets.json
python scripts/maimai_detail_targets.py from-ids --ids 1,2,3 --db data/talent.db --out data/output/maimai-detail-targets.json
```

---

### Task 3: Make Extension Import Accept Recommendation Shapes

**Files:**
- Modify: `extensions/maimai-scraper/background.js`
- Modify: `extensions/maimai-scraper/popup.js`

- [ ] **Step 1: Normalize import payloads in background**

Accept:

- `contacts`
- `detailJobs`
- `top10`
- `candidates`
- `matches`
- `results`
- raw array

For each item, normalize:

- `id` from `id`, `platform_id`, `uid`, `dstu`, or `profile_url` query `dstu`
- `trackable_token` from item field or `profile_url` query
- `name`, `company`, `position`
- `candidate_id`

- [ ] **Step 2: Update popup file import**

Send the parsed JSON object to `importDetailContacts`; do not pre-strip to `contacts`, so background can normalize recommendation-shaped files.

- [ ] **Step 3: Verify extension contracts**

Run:

```bash
node --check extensions/maimai-scraper/background.js
node --check extensions/maimai-scraper/popup.js
python -m pytest tests/test_maimai_scraper_extension.py -q
```

Expected: PASS.
---

### Task 4: Document Recommended Business Flow

**Files:**
- Modify: `agents/workflows/talent-library/references/scenarios.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Add workflow docs**

Document:

1. Run `talent-library search/match`.
2. Export recommended candidates to maimai detail targets:

```bash
python scripts/maimai_detail_targets.py from-file --input data/output/<match>.json --db data/talent.db --out data/output/maimai-detail-targets.json
```

3. Import that JSON in `maimai-scraper` “批量详情”.
4. Run batch detail.
5. Export capture JSON.
6. Import details using `maimai_detail_import.py dry-run/apply`.

- [ ] **Step 2: Update task record**

Append task checklist and verification notes to `tasks/todo.md`.

---

### Task 5: Full Verification

**Files:**
- No source changes unless tests fail.

- [ ] **Step 1: Focused tests**

Run:

```bash
python -m pytest tests/test_maimai_detail_targets.py tests/test_maimai_scraper_extension.py -q
```

Expected: PASS.

- [ ] **Step 2: Existing detail tests**

Run:

```bash
python -m pytest tests/test_maimai_detail_import.py scripts/test_maimai.py -q
```

Expected: PASS.

- [ ] **Step 3: Full test suite**

Run:

```bash
python -m pytest tests scripts -q
```

Expected: PASS.

- [ ] **Step 4: Extension syntax**

Run:

```bash
node --check extensions/maimai-scraper/background.js
node --check extensions/maimai-scraper/popup.js
```

Expected: PASS.
