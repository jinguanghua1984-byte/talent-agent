# 脉脉 popup 本地任务包自动化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把详情自动化从 `automation.html`/CDP 入口改为“本地 CLI 准备任务包 + 用户在人才银行页 popup 点击加载/启动”的低风险闭环，保持已验证成功的 `popup.html` sender 和人才银行页 visible 上下文。

**Architecture:** 本地 Python 只负责服务待抓取联系人 JSON，不触碰浏览器页面；扩展 popup 从 `http://127.0.0.1:8765/detail-plan.json` 读取任务包，并由用户点击触发导入和启动。真实详情请求仍走现有 `startDetailBatch -> content.js detailFetch -> inject.js` 链路，且继续由 safe 模式限速/熔断。

**Tech Stack:** Chrome Extension Manifest V3, plain JavaScript popup UI, Python `http.server`, pytest 静态契约测试。

---

## Design Decision

1. 不再把 `automation.html` 作为真实详情入口，因为 probe 已证明它会让人才银行页从 active/visible 变成 inactive/hidden。
2. 不用 CDP 调用 `startDetailBatch`，避免 sender 变成 automation/Runtime.evaluate。
3. 保留用户点击 popup 的触发点：已验证手动成功路径 sender 为 `popup.html`。
4. 本地自动化只做：生成任务包、启动 localhost 只读服务、监听导出文件、运行 dry-run。
5. 平台侧任意安全信号出现时停止：登录页、验证码、429/403、content script 缺失、详情失败连续异常。

## File Structure

Modify:

- `extensions/maimai-scraper/manifest.json` — 增加 localhost host permission，允许 popup 读取本地任务包。
- `extensions/maimai-scraper/popup.html` — 在批量详情 tab 中新增本地任务包 URL、加载、加载并启动按钮和状态区。
- `extensions/maimai-scraper/popup.js` — 新增 fetch 本地任务包、导入、可选启动、active tab 预检和状态提示。
- `extensions/maimai-scraper/popup.css` — 新增本地任务包面板样式。
- `tests/test_maimai_scraper_extension.py` — 新增 popup 本地任务包契约测试。
- `tasks/todo.md` — 记录实施和验证结果。

Create:

- `scripts/maimai_detail_plan_server.py` — 只读 localhost JSON server，默认服务 `/detail-plan.json` 和 `/health`。
- `tests/test_maimai_detail_plan_server.py` — 覆盖服务端加载计划、健康检查和 CLI 参数。

## Task 1: Popup Local Plan Contract

**Files:**
- Modify: `tests/test_maimai_scraper_extension.py`

- [ ] **Step 1: Write failing test**

Add assertions:

```python
def test_popup_supports_local_detail_plan_loader():
    manifest = json.loads(read_extension_file("manifest.json"))
    popup_html = read_extension_file("popup.html")
    popup_js = read_extension_file("popup.js")

    assert "http://127.0.0.1/*" in manifest["host_permissions"]
    assert "detail-local-plan-url" in popup_html
    assert "btn-load-local-detail-plan" in popup_html
    assert "btn-load-start-local-detail-plan" in popup_html
    assert "function loadLocalDetailPlan" in popup_js
    assert "fetch(localPlanUrl" in popup_js
    assert '{ type: "importDetailContacts", contacts: planPayload }' in popup_js
    assert '{ type: "startDetailBatch"' in popup_js
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py::test_popup_supports_local_detail_plan_loader -q
```

Expected: FAIL because local plan loader does not exist.

## Task 2: Popup Local Plan Implementation

**Files:**
- Modify: `extensions/maimai-scraper/manifest.json`
- Modify: `extensions/maimai-scraper/popup.html`
- Modify: `extensions/maimai-scraper/popup.js`
- Modify: `extensions/maimai-scraper/popup.css`

- [ ] **Step 1: Add manifest host permissions**

Add:

```json
"http://127.0.0.1/*",
"http://localhost/*"
```

- [ ] **Step 2: Add popup controls**

Add inside `#tab-detail` before the file import group:

```html
<div class="local-plan-section">
  <div class="form-group">
    <label>本地任务包 URL</label>
    <input type="text" id="detail-local-plan-url" value="http://127.0.0.1:8765/detail-plan.json" />
  </div>
  <div class="btn-row">
    <button id="btn-load-local-detail-plan">加载任务包</button>
    <button id="btn-load-start-local-detail-plan" class="primary">加载并开始</button>
  </div>
  <div class="progress-text" id="detail-local-plan-status">本地任务包由 CLI 提供；真实详情仍需用户在 popup 点击触发。</div>
</div>
```

- [ ] **Step 3: Add popup JS**

Implement:

```javascript
function loadLocalDetailPlan(shouldStart) {
  var localPlanUrl = detailLocalPlanUrlEl.value.trim() || "http://127.0.0.1:8765/detail-plan.json";
  detailLocalPlanStatusEl.textContent = "读取本地任务包...";
  fetch(localPlanUrl, { cache: "no-store" })
    .then(function (resp) {
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      return resp.json();
    })
    .then(function (planPayload) {
      return importLocalDetailPlan(planPayload, shouldStart);
    })
    .catch(function (err) {
      detailLocalPlanStatusEl.textContent = "任务包读取失败: " + err.message;
    });
}
```

Use existing background messages only: `importDetailContacts` and `startDetailBatch`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py::test_popup_supports_local_detail_plan_loader -q
node --check extensions/maimai-scraper/popup.js
```

Expected: PASS.

## Task 3: Local Detail Plan Server

**Files:**
- Create: `scripts/maimai_detail_plan_server.py`
- Create: `tests/test_maimai_detail_plan_server.py`

- [ ] **Step 1: Write failing tests**

Cover:

```python
from scripts.maimai_detail_plan_server import build_plan_payload, make_handler

def test_build_plan_payload_serves_contacts_shape(tmp_path):
    plan = tmp_path / "targets.json"
    plan.write_text('{"contacts":[{"id":"1","trackable_token":"t"}],"totalContacts":1}', encoding="utf-8")
    payload = build_plan_payload(plan)
    assert payload["contacts"][0]["id"] == "1"

def test_build_plan_payload_rejects_missing_contacts(tmp_path):
    plan = tmp_path / "bad.json"
    plan.write_text('{"items":[]}', encoding="utf-8")
    try:
      build_plan_payload(plan)
    except ValueError as exc:
      assert "contacts" in str(exc)
    else:
      raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_maimai_detail_plan_server.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement server**

Expose:

```python
def build_plan_payload(plan_path: Path) -> dict[str, Any]:
    ...

def make_handler(plan_path: Path) -> type[BaseHTTPRequestHandler]:
    ...
```

CLI:

```bash
python scripts/maimai_detail_plan_server.py --plan data/output/raw/maimai-ai-infra-detail-gate-targets-2026-05-13.json --port 8765
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest tests/test_maimai_detail_plan_server.py -q
python -m py_compile scripts/maimai_detail_plan_server.py
```

Expected: PASS.

## Task 4: Verification

**Files:**
- Modify: `tasks/todo.md`

- [ ] **Step 1: Run focused tests**

```bash
python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_detail_plan_server.py -q
```

- [ ] **Step 2: Run syntax checks**

```bash
node --check extensions/maimai-scraper/popup.js
python -m py_compile scripts/maimai_detail_plan_server.py
git diff --check
```

- [ ] **Step 3: Run full tests**

```bash
python -m pytest tests scripts -q
```

## Task 5: Human-in-the-loop Execution

**Files:**
- Runtime only; no code edits.

- [ ] **Step 1: Start local plan server**

```bash
python scripts/maimai_detail_plan_server.py --plan data/output/raw/maimai-ai-infra-detail-gate-targets-2026-05-13.json --port 8765
```

- [ ] **Step 2: Ask user to reload extension**

User action:

1. Open `edge://extensions/`
2. Reload `Maimai Talent Scraper`
3. Refresh or reopen talent bank page manually
4. Keep talent bank page active

- [ ] **Step 3: User starts from popup**

User action:

1. Open extension popup on talent bank page
2. Go to 批量详情
3. Click `加载任务包`
4. Confirm count
5. Click `开始详情`, or click `加载并开始` for one-click run

- [ ] **Step 4: User exports result**

After completed, user clicks `导出 JSON` and provides the downloaded file path.

- [ ] **Step 5: Local dry-run**

Run:

```bash
python scripts/maimai_detail_import.py dry-run --capture-file "<downloaded-json>" --db data/talent.db --out data/output/maimai-ai-infra-popup-local-plan-dry-run-2026-05-13.md
```

Expected: `failed_jobs=0`, then decide whether to apply separately.

## Self-Review

- Spec coverage: sender/active/visible root-cause findings are handled by removing `automation.html` from real detail execution and keeping popup user-triggered start.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: popup message names reuse existing `importDetailContacts` and `startDetailBatch`; server returns existing `contacts` shape.
