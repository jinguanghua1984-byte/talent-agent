# Boss Channel Browser Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-channel browser scraper extension that preserves the existing Maimai flow and adds a Boss list-capture, export, dry-run, and confirmed-ingest loop, with Boss detail capture limited to passive observation.

**Architecture:** Create a new `extensions/talent-channel-scraper` extension by migrating the existing Maimai extension into a channelized structure while leaving `extensions/maimai-scraper` intact. Add shared capture envelope/export utilities, then add Boss-only passive `geeks.json` capture, parser, low-risk page assist, and a local capture import CLI routed by `metadata.channel`.

**Tech Stack:** Chrome Manifest V3 extension JavaScript, IndexedDB, `chrome.storage.local`, Python 3, SQLite via `TalentDB`, pytest, Node `--check`.

---

## File Structure

Create or modify these files:

- Create: `extensions/talent-channel-scraper/manifest.json`  
  New multi-channel extension manifest with Maimai and Boss host permissions.
- Create: `extensions/talent-channel-scraper/background.js`  
  Service worker copied from Maimai first, then extended to route channel-specific capture/export messages.
- Create: `extensions/talent-channel-scraper/content.js`  
  Bridge between injected page scripts and extension runtime for both Maimai and Boss.
- Create: `extensions/talent-channel-scraper/inject.js`  
  Bootstrap injected into MAIN world; loads channel-specific logic from statically bundled scripts.
- Create: `extensions/talent-channel-scraper/idb.js`  
  IndexedDB helper copied from Maimai first; extended only if common capture stores need explicit channel keys.
- Create: `extensions/talent-channel-scraper/popup.html`
- Create: `extensions/talent-channel-scraper/popup.css`
- Create: `extensions/talent-channel-scraper/popup.js`  
  Popup copied from Maimai first, then extended with a channel label and Boss-safe controls.
- Create: `extensions/talent-channel-scraper/autopager.js`
- Create: `extensions/talent-channel-scraper/detail_batch.js`  
  Maimai existing behavior, unchanged except import paths or channel guards if needed.
- Create: `extensions/talent-channel-scraper/channels/common/capture_envelope.js`  
  Pure JS helpers for building a unified export envelope.
- Create: `extensions/talent-channel-scraper/channels/boss/parser.js`  
  Pure JS helpers for Boss `geeks.json` parsing and normalization.
- Create: `extensions/talent-channel-scraper/channels/boss/search_capture.js`  
  Boss MAIN-world passive response interception for `geeks.json`.
- Create: `extensions/talent-channel-scraper/channels/boss/page_assist.js`  
  Boss low-risk UI helper: search input, job filter reset, limited scroll.
- Create: `tests/test_talent_channel_scraper_extension.py`  
  Static and fixture-based extension contract tests.
- Create: `tests/fixtures/boss_geeks_response.json`  
  Minimal Boss `geeks.json` sample for parser tests.
- Create: `scripts/channel_capture_import.py`  
  Unified local import CLI for channel capture files.
- Create: `tests/test_channel_capture_import.py`  
  Dry-run/apply tests for Boss capture import.
- Modify: `tasks/todo.md`  
  Track implementation progress and final review.

Keep these files unchanged unless a task explicitly says otherwise:

- `extensions/maimai-scraper/*`
- `scripts/platform_match/adapters/boss.py`
- `scripts/platform_match/adapters/maimai.py`
- `scripts/talent_db.py`

---

### Task 1: Add Multi-Channel Extension Contract Tests

**Files:**
- Create: `tests/test_talent_channel_scraper_extension.py`
- Create: `tests/fixtures/boss_geeks_response.json`

- [ ] **Step 1: Write the failing extension contract tests**

Create `tests/test_talent_channel_scraper_extension.py`:

```python
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "extensions" / "talent-channel-scraper"
FIXTURES_DIR = ROOT / "tests" / "fixtures"


def read_extension_file(name: str) -> str:
    return (EXTENSION_DIR / name).read_text(encoding="utf-8")


def test_manifest_declares_multi_channel_extension():
    manifest = json.loads(read_extension_file("manifest.json"))

    assert manifest["manifest_version"] == 3
    assert manifest["name"] == "Talent Channel Scraper"
    assert "*://maimai.cn/*" in manifest["host_permissions"]
    assert "*://*.maimai.cn/*" in manifest["host_permissions"]
    assert "*://*.zhipin.com/*" in manifest["host_permissions"]


def test_manifest_loads_common_and_channel_scripts():
    manifest = json.loads(read_extension_file("manifest.json"))
    script_groups = [" ".join(item["js"]) for item in manifest["content_scripts"]]
    all_scripts = " ".join(script_groups)

    assert "inject.js" in all_scripts
    assert "content.js" in all_scripts
    assert "channels/boss/search_capture.js" in all_scripts
    assert "channels/boss/page_assist.js" in all_scripts


def test_common_capture_envelope_contract_exists():
    source = read_extension_file("channels/common/capture_envelope.js")

    for marker in [
        "buildCaptureEnvelope",
        "schema_version",
        "channel",
        "capture_level",
        "contacts",
        "details",
        "requests",
    ]:
        assert marker in source


def test_boss_parser_contract_exists():
    source = read_extension_file("channels/boss/parser.js")

    for marker in [
        "parseBossGeeksResponse",
        "normalizeBossGeekCard",
        "encryptGeekId",
        "geekCard",
        "data_level",
        "partial",
    ]:
        assert marker in source


def test_boss_search_capture_is_passive_only():
    source = read_extension_file("channels/boss/search_capture.js")

    assert "geeks.json" in source
    assert "window.fetch" in source
    assert "__TALENT_CHANNEL_BOSS_CAPTURE__" in source
    assert "fetch(" not in source.replace("window.fetch", "")
    assert "XMLHttpRequest.prototype.open" in source


def test_boss_page_assist_does_not_navigate_or_open_tabs():
    source = read_extension_file("channels/boss/page_assist.js")

    assert ".search-input" in source
    assert ".input-text" not in source
    assert "window.open" not in source
    assert ".location.href" not in source
    assert "/web/geek/" not in source


def test_boss_fixture_can_be_parsed_by_node_smoke():
    fixture = json.loads((FIXTURES_DIR / "boss_geeks_response.json").read_text(encoding="utf-8"))
    assert fixture["zpData"]["geeks"][0]["geekCard"]["encryptGeekId"] == "boss-geek-1"


def test_new_extension_javascript_syntax():
    files = [
        "background.js",
        "content.js",
        "inject.js",
        "popup.js",
        "autopager.js",
        "detail_batch.js",
        "idb.js",
        "channels/common/capture_envelope.js",
        "channels/boss/parser.js",
        "channels/boss/search_capture.js",
        "channels/boss/page_assist.js",
    ]
    for name in files:
        subprocess.run(
            ["node", "--check", str(EXTENSION_DIR / name)],
            check=True,
            cwd=ROOT,
        )
```

Create `tests/fixtures/boss_geeks_response.json`:

```json
{
  "code": 0,
  "message": "Success",
  "zpData": {
    "totalCount": 1,
    "hasMore": false,
    "geeks": [
      {
        "geekCard": {
          "name": "王*",
          "gender": 1,
          "city": "北京",
          "workYear": "5年",
          "salary": "30-50K",
          "highestDegreeName": "本科",
          "ageDesc": "29岁",
          "activeDesc": "刚刚活跃",
          "geekWork": {
            "name": "未来科技·AI平台·产品经理"
          },
          "geekEdu": {
            "name": "中国·清华大学·计算机科学"
          },
          "labelMatchList": [
            {"markWord": "AI产品"},
            {"markWord": "平台产品"}
          ],
          "workList": [
            {"name": "未来科技·产品经理", "dateRange": "2021-2026"}
          ],
          "encryptGeekId": "boss-geek-1",
          "securityId": "boss-security-1"
        }
      }
    ]
  }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_talent_channel_scraper_extension.py -q
```

Expected: FAIL because `extensions/talent-channel-scraper` and channel files do not exist.

- [ ] **Step 3: Commit failing tests**

```powershell
git add tests/test_talent_channel_scraper_extension.py tests/fixtures/boss_geeks_response.json
git commit -m "test: add talent channel extension contracts"
```

---

### Task 2: Scaffold `talent-channel-scraper` Without Changing Maimai

**Files:**
- Create: `extensions/talent-channel-scraper/*`
- Modify: `extensions/talent-channel-scraper/manifest.json`

- [ ] **Step 1: Copy existing Maimai extension into the new directory**

Run:

```powershell
Copy-Item -Path extensions\maimai-scraper -Destination extensions\talent-channel-scraper -Recurse
```

Expected: `extensions/talent-channel-scraper/manifest.json` exists.

- [ ] **Step 2: Update manifest name, version, description, host permissions, and content scripts**

Edit `extensions/talent-channel-scraper/manifest.json` to this complete content:

```json
{
  "manifest_version": 3,
  "name": "Talent Channel Scraper",
  "version": "0.1",
  "description": "多渠道人才搜索抓取工具：保留脉脉列表/详情能力，新增 Boss 列表被动捕获能力",
  "permissions": ["storage", "scripting", "downloads"],
  "host_permissions": [
    "*://maimai.cn/*",
    "*://*.maimai.cn/*",
    "*://*.zhipin.com/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_popup": "popup.html",
    "default_title": "Talent Channel Scraper"
  },
  "content_scripts": [
    {
      "matches": ["*://maimai.cn/*", "*://*.maimai.cn/*", "*://*.zhipin.com/*"],
      "js": [
        "channels/common/capture_envelope.js",
        "channels/boss/parser.js",
        "channels/boss/search_capture.js",
        "channels/boss/page_assist.js",
        "inject.js"
      ],
      "run_at": "document_start",
      "world": "MAIN"
    },
    {
      "matches": ["*://maimai.cn/*", "*://*.maimai.cn/*", "*://*.zhipin.com/*"],
      "js": ["content.js"],
      "run_at": "document_start"
    }
  ]
}
```

- [ ] **Step 3: Create placeholder channel directories with real minimal files**

Create `extensions/talent-channel-scraper/channels/common/capture_envelope.js`:

```javascript
(function () {
  "use strict";

  function buildCaptureEnvelope(input) {
    input = input || {};
    var metadata = input.metadata || {};
    var channel = metadata.channel || input.channel || "unknown";
    var contacts = input.contacts || [];
    var details = input.details || [];
    var requests = input.requests || [];

    return {
      exportTime: input.exportTime || new Date().toISOString(),
      metadata: Object.assign(
        {
          schema_version: 1,
          channel: channel,
          export_type: "full",
          capture_level: details.length > 0 ? "partial_detail" : "list",
          total_contacts: contacts.length,
          total_details: details.length,
          total_requests: requests.length,
        },
        metadata
      ),
      contacts: contacts,
      details: details,
      detailJobs: input.detailJobs || [],
      requests: requests,
      logs: input.logs || [],
    };
  }

  window.TalentCaptureEnvelope = {
    buildCaptureEnvelope: buildCaptureEnvelope,
  };
})();
```

Create `extensions/talent-channel-scraper/channels/boss/parser.js`:

```javascript
(function () {
  "use strict";

  function splitBossName(value) {
    var parts = String(value || "").split("·").filter(Boolean);
    if (parts.length >= 2) {
      return { company: parts[0], title: parts[parts.length - 1] };
    }
    if (parts.length === 1) {
      return { company: parts[0], title: "" };
    }
    return { company: "", title: "" };
  }

  function parseNumber(value) {
    var match = String(value || "").match(/(\d+)/);
    return match ? Number(match[1]) : null;
  }

  function normalizeBossGeekCard(card, captureMeta) {
    card = card || {};
    captureMeta = captureMeta || {};
    var work = splitBossName(card.geekWork && card.geekWork.name);
    var platformId = card.encryptGeekId ? String(card.encryptGeekId) : "";
    var tags = (card.labelMatchList || [])
      .map(function (item) { return item && item.markWord; })
      .filter(Boolean);

    return {
      channel: "boss",
      platform_id: platformId,
      profile_url: platformId ? "https://www.zhipin.com/web/geek/" + platformId : "",
      name: card.name || "",
      gender: card.gender === 1 ? "男" : card.gender === 2 ? "女" : null,
      city: card.city || "",
      current_company: work.company,
      current_title: work.title,
      education: card.highestDegreeName || "",
      work_years: parseNumber(card.workYear),
      age: parseNumber(card.ageDesc),
      expected_salary: card.salary || "",
      active_state: card.activeDesc || "",
      skill_tags: tags,
      data_level: "partial",
      raw_profile: Object.assign({}, card, { _capture: captureMeta }),
    };
  }

  function parseBossGeeksResponse(body, captureMeta) {
    var data = body && body.zpData ? body.zpData : {};
    var geeks = Array.isArray(data.geeks) ? data.geeks : [];
    var seen = {};
    var contacts = [];

    geeks.forEach(function (item) {
      var card = item && item.geekCard;
      if (!card || !card.encryptGeekId) return;
      var key = String(card.encryptGeekId);
      if (seen[key]) return;
      seen[key] = true;
      contacts.push(normalizeBossGeekCard(card, captureMeta));
    });

    return {
      contacts: contacts,
      total: Number(data.totalCount || contacts.length || 0),
      has_more: Boolean(data.hasMore),
    };
  }

  window.BossChannelParser = {
    normalizeBossGeekCard: normalizeBossGeekCard,
    parseBossGeeksResponse: parseBossGeeksResponse,
  };
})();
```

Create `extensions/talent-channel-scraper/channels/boss/search_capture.js`:

```javascript
(function () {
  "use strict";

  var originalFetch = window.fetch;
  var originalOpen = XMLHttpRequest.prototype.open;
  var originalSend = XMLHttpRequest.prototype.send;

  function isBossSearchUrl(url) {
    url = String(url || "");
    return url.indexOf("geeks.json") !== -1 && url.indexOf("t.zhipin.com") === -1;
  }

  function emitBossCapture(url, body) {
    if (!window.BossChannelParser || !window.BossChannelParser.parseBossGeeksResponse) return;
    var parsed = window.BossChannelParser.parseBossGeeksResponse(body, {
      url: String(url || ""),
      captured_at: new Date().toISOString(),
    });
    window.postMessage(
      {
        type: "__TALENT_CHANNEL_BOSS_CAPTURE__",
        channel: "boss",
        url: String(url || ""),
        contacts: parsed.contacts,
        total: parsed.total,
        has_more: parsed.has_more,
      },
      "*"
    );
  }

  window.fetch = function () {
    var url = arguments[0] && arguments[0].url ? arguments[0].url : arguments[0];
    return originalFetch.apply(this, arguments).then(function (response) {
      if (isBossSearchUrl(url)) {
        response.clone().json().then(function (body) {
          emitBossCapture(url, body);
        }).catch(function () {});
      }
      return response;
    });
  };

  XMLHttpRequest.prototype.open = function (method, url) {
    this.__talentBossUrl = url;
    return originalOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function () {
    var xhr = this;
    xhr.addEventListener("load", function () {
      if (!isBossSearchUrl(xhr.__talentBossUrl)) return;
      try {
        emitBossCapture(xhr.__talentBossUrl, JSON.parse(xhr.responseText || "{}"));
      } catch (err) {
        window.postMessage(
          {
            type: "__TALENT_CHANNEL_BOSS_CAPTURE_ERROR__",
            channel: "boss",
            url: String(xhr.__talentBossUrl || ""),
            error: String(err && err.message ? err.message : err),
          },
          "*"
        );
      }
    });
    return originalSend.apply(this, arguments);
  };
})();
```

Create `extensions/talent-channel-scraper/channels/boss/page_assist.js`:

```javascript
(function () {
  "use strict";

  function isBossPage() {
    return location.hostname.indexOf("zhipin.com") !== -1;
  }

  function findSearchInput() {
    return document.querySelector(".search-input");
  }

  function requestBossSafeSearch(input) {
    if (!isBossPage()) {
      return { ok: false, error: "not_boss_page" };
    }
    var query = input && input.query ? String(input.query) : "";
    var el = findSearchInput();
    if (!el) {
      return { ok: false, error: "search_input_not_found" };
    }
    el.focus();
    document.execCommand("selectAll");
    document.execCommand("insertText", false, query);
    var icon = document.querySelector(".icon-search");
    if (icon) {
      icon.click();
    } else {
      el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    }
    return { ok: true };
  }

  window.BossPageAssist = {
    requestBossSafeSearch: requestBossSafeSearch,
  };
})();
```

- [ ] **Step 4: Run contract tests**

Run:

```powershell
python -m pytest tests/test_talent_channel_scraper_extension.py -q
```

Expected: PASS.

- [ ] **Step 5: Run old Maimai extension tests**

Run:

```powershell
python -m pytest tests/test_maimai_scraper_extension.py -q
```

Expected: PASS, proving the old extension directory still works.

- [ ] **Step 6: Commit scaffold**

```powershell
git add extensions/talent-channel-scraper tests/test_talent_channel_scraper_extension.py
git commit -m "feat: scaffold talent channel scraper extension"
```

---

### Task 3: Add Boss Capture Storage and Unified Export

**Files:**
- Modify: `extensions/talent-channel-scraper/content.js`
- Modify: `extensions/talent-channel-scraper/background.js`
- Modify: `extensions/talent-channel-scraper/popup.js`
- Test: `tests/test_talent_channel_scraper_extension.py`

- [ ] **Step 1: Add failing tests for Boss capture message handling and export envelope**

Append to `tests/test_talent_channel_scraper_extension.py`:

```python
def test_content_forwards_boss_capture_messages():
    content = read_extension_file("content.js")

    assert "__TALENT_CHANNEL_BOSS_CAPTURE__" in content
    assert "bossCapture" in content


def test_background_persists_boss_contacts_and_exports_channel_envelope():
    background = read_extension_file("background.js")

    for marker in [
        "bossCapture",
        "bossContacts",
        "BossChannelParser",
        "TalentCaptureEnvelope",
        "metadata",
        "channel: \"boss\"",
        "capture_level",
    ]:
        assert marker in background


def test_popup_mentions_boss_channel_status():
    popup = read_extension_file("popup.js")

    assert "Boss" in popup
    assert "bossContacts" in popup
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_talent_channel_scraper_extension.py -q
```

Expected: FAIL because `content.js`, `background.js`, and `popup.js` do not yet mention Boss capture storage.

- [ ] **Step 3: Forward Boss capture messages from content to background**

In `extensions/talent-channel-scraper/content.js`, add this branch near the existing `window.addEventListener("message", ...)` handling:

```javascript
if (event.data && event.data.type === "__TALENT_CHANNEL_BOSS_CAPTURE__") {
  safeSendMessage({
    type: "bossCapture",
    channel: "boss",
    url: event.data.url || "",
    contacts: event.data.contacts || [],
    total: event.data.total || 0,
    hasMore: Boolean(event.data.has_more),
  });
}

if (event.data && event.data.type === "__TALENT_CHANNEL_BOSS_CAPTURE_ERROR__") {
  safeSendMessage({
    type: "bossCaptureError",
    channel: "boss",
    url: event.data.url || "",
    error: event.data.error || "unknown_error",
  });
}
```

- [ ] **Step 4: Persist Boss contacts in background**

In `extensions/talent-channel-scraper/background.js`, add helper functions before `chrome.runtime.onMessage.addListener`:

```javascript
function mergeByPlatformId(existing, incoming) {
  var byId = {};
  (existing || []).forEach(function (item) {
    var key = item && item.platform_id ? String(item.platform_id) : "";
    if (key) byId[key] = item;
  });
  (incoming || []).forEach(function (item) {
    var key = item && item.platform_id ? String(item.platform_id) : "";
    if (key) byId[key] = item;
  });
  return Object.keys(byId).map(function (key) { return byId[key]; });
}

function appendBossLog(level, message, meta) {
  return new Promise(function (resolve) {
    chrome.storage.local.get({ bossLogs: [] }, function (r) {
      var logs = r.bossLogs || [];
      logs.push({
        ts: new Date().toISOString(),
        level: level || "info",
        message: message || "",
        meta: meta || null,
      });
      chrome.storage.local.set({ bossLogs: logs.slice(-120) }, resolve);
    });
  });
}
```

Add these message branches:

```javascript
if (msg.type === "bossCapture") {
  chrome.storage.local.get({ bossContacts: [], bossRequests: [] }, function (r) {
    var contacts = mergeByPlatformId(r.bossContacts || [], msg.contacts || []);
    var requests = r.bossRequests || [];
    requests.push({
      ts: new Date().toISOString(),
      channel: "boss",
      url: msg.url || "",
      total: msg.total || 0,
      hasMore: Boolean(msg.hasMore),
      contactCount: (msg.contacts || []).length,
    });
    chrome.storage.local.set(
      {
        bossContacts: contacts,
        bossRequests: requests.slice(-300),
      },
      function () {
        appendBossLog("info", "Boss 捕获候选人 " + (msg.contacts || []).length + " 条", {
          total: msg.total || 0,
          url: msg.url || "",
        }).then(function () {
          sendResponse({ ok: true, contacts: contacts.length });
        });
      }
    );
  });
  return true;
}

if (msg.type === "bossCaptureError") {
  appendBossLog("error", "Boss 捕获失败: " + (msg.error || "unknown_error"), {
    url: msg.url || "",
  }).then(function () {
    sendResponse({ ok: false, error: msg.error || "unknown_error" });
  });
  return true;
}
```

- [ ] **Step 5: Include Boss data in `exportFullJson`**

In the existing `exportFullJson` branch in `background.js`, include `bossContacts`, `bossRequests`, and `bossLogs` in the storage reads. Build the Boss envelope when Boss data exists and Maimai detail export is not the active mode:

```javascript
var hasBossContacts = (r.bossContacts || []).length > 0;
if (hasBossContacts && window.TalentCaptureEnvelope) {
  exportData = window.TalentCaptureEnvelope.buildCaptureEnvelope({
    metadata: {
      channel: "boss",
      export_type: "full",
      capture_level: (r.bossDetails || []).length > 0 ? "partial_detail" : "list",
    },
    contacts: r.bossContacts || [],
    details: r.bossDetails || [],
    requests: r.bossRequests || [],
    logs: r.bossLogs || [],
  });
}
```

Keep the existing Maimai export behavior for Maimai pages and Maimai detail jobs.

- [ ] **Step 6: Show Boss status in popup**

In `extensions/talent-channel-scraper/popup.js`, extend the existing summary rendering with:

```javascript
chrome.storage.local.get({ bossContacts: [], bossRequests: [], bossLogs: [] }, function (r) {
  if ((r.bossContacts || []).length > 0) {
    setCaptureBadge("Boss " + r.bossContacts.length + " 人");
  }
});
```

If `setCaptureBadge` is not global in the copied popup, add a small local wrapper near the status badge setup:

```javascript
function setBossStatusText(text) {
  var statusBadge = document.getElementById("status-badge");
  if (statusBadge) statusBadge.textContent = text;
}
```

Then use `setBossStatusText(...)`.

- [ ] **Step 7: Run focused tests**

Run:

```powershell
python -m pytest tests/test_talent_channel_scraper_extension.py -q
node --check extensions/talent-channel-scraper/background.js
node --check extensions/talent-channel-scraper/content.js
node --check extensions/talent-channel-scraper/popup.js
```

Expected: PASS.

- [ ] **Step 8: Commit capture storage and export**

```powershell
git add extensions/talent-channel-scraper tests/test_talent_channel_scraper_extension.py
git commit -m "feat: capture and export boss list results"
```

---

### Task 4: Implement Unified Capture Import CLI for Boss

**Files:**
- Create: `scripts/channel_capture_import.py`
- Create: `tests/test_channel_capture_import.py`

- [ ] **Step 1: Write failing import tests**

Create `tests/test_channel_capture_import.py`:

```python
import json
from pathlib import Path

from scripts.channel_capture_import import apply_capture, dry_run_capture
from scripts.talent_db import TalentDB
from scripts.talent_models import CandidateFilter


CONFIRM = "确认写入boss列表"


def _write_boss_capture(path: Path) -> None:
    payload = {
        "exportTime": "2026-05-12T00:00:00.000Z",
        "metadata": {
            "schema_version": 1,
            "channel": "boss",
            "export_type": "full",
            "capture_level": "list",
        },
        "contacts": [
            {
                "channel": "boss",
                "platform_id": "boss-geek-1",
                "profile_url": "https://www.zhipin.com/web/geek/boss-geek-1",
                "name": "王*",
                "city": "北京",
                "current_company": "未来科技",
                "current_title": "产品经理",
                "education": "本科",
                "work_years": 5,
                "expected_salary": "30-50K",
                "skill_tags": ["AI产品"],
                "data_level": "partial",
                "raw_profile": {
                    "encryptGeekId": "boss-geek-1",
                    "securityId": "boss-security-1"
                },
            }
        ],
        "details": [],
        "detailJobs": [],
        "requests": [],
        "logs": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_boss_dry_run_does_not_modify_db(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    TalentDB(db_path).close()
    capture_path = tmp_path / "boss-capture.json"
    report_path = tmp_path / "dry-run.md"
    _write_boss_capture(capture_path)

    result = dry_run_capture(capture_path, db_path, report_path)

    assert result["channel"] == "boss"
    assert result["created"] == 1
    assert result["merged"] == 0
    assert result["pending"] == 0
    assert result["errors"] == 0
    assert report_path.exists()

    db = TalentDB(db_path)
    try:
        assert db.count() == 0
    finally:
        db.close()


def test_boss_apply_requires_confirmation(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    TalentDB(db_path).close()
    capture_path = tmp_path / "boss-capture.json"
    _write_boss_capture(capture_path)

    try:
        apply_capture(capture_path, db_path, confirm="yes")
    except ValueError as exc:
        assert CONFIRM in str(exc)
    else:
        raise AssertionError("apply_capture should require explicit confirmation")


def test_boss_apply_writes_source_profile_and_partial_level(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    capture_path = tmp_path / "boss-capture.json"
    report_path = tmp_path / "apply.md"
    _write_boss_capture(capture_path)

    result = apply_capture(
        capture_path,
        db_path,
        report_path=report_path,
        confirm=CONFIRM,
    )

    assert result["written"] == 1

    db = TalentDB(db_path)
    try:
        assert db.count() == 1
        page = db.search(CandidateFilter(platforms=["boss"]))
        candidate = page.items[0]
        assert candidate.name == "王*"
        assert candidate.data_level == "partial"
        sources = db.get_sources(candidate.id)
        assert sources[0].platform == "boss"
        assert sources[0].platform_id == "boss-geek-1"
        assert sources[0].raw_profile["raw_profile"]["securityId"] == "boss-security-1"
    finally:
        db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_channel_capture_import.py -q
```

Expected: FAIL because `scripts/channel_capture_import.py` does not exist.

- [ ] **Step 3: Implement capture import CLI**

Create `scripts/channel_capture_import.py`:

```python
"""多渠道浏览器抓取结果导入工具。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.talent_db import TalentDB


BOSS_CONFIRM_TEXT = "确认写入boss列表"


@dataclass(frozen=True)
class CaptureContact:
    channel: str
    platform_id: str
    payload: dict[str, Any]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("capture file must be a JSON object")
    return data


def _contacts_from_capture(capture: dict[str, Any]) -> tuple[str, list[CaptureContact]]:
    metadata = capture.get("metadata") or {}
    channel = str(metadata.get("channel") or "").strip()
    if channel != "boss":
        raise ValueError(f"unsupported channel for this importer: {channel}")
    contacts = []
    for item in capture.get("contacts") or []:
        if not isinstance(item, dict):
            continue
        platform_id = str(item.get("platform_id") or item.get("encryptGeekId") or "")
        if not platform_id:
            continue
        contacts.append(CaptureContact(channel=channel, platform_id=platform_id, payload=item))
    return channel, contacts


def _mapped_boss_contact(contact: CaptureContact) -> dict[str, Any]:
    payload = dict(contact.payload)
    raw_profile = payload.get("raw_profile") if isinstance(payload.get("raw_profile"), dict) else {}
    mapped = {
        "name": payload.get("name") or raw_profile.get("name") or "",
        "gender": payload.get("gender"),
        "age": payload.get("age"),
        "city": payload.get("city"),
        "work_years": payload.get("work_years"),
        "education": payload.get("education"),
        "current_company": payload.get("current_company"),
        "current_title": payload.get("current_title"),
        "expected_salary": payload.get("expected_salary"),
        "expected_city": payload.get("expected_city"),
        "expected_title": payload.get("expected_title"),
        "hunting_status": payload.get("hunting_status"),
        "skill_tags": payload.get("skill_tags") or [],
        "data_level": "partial",
        "platform_id": contact.platform_id,
        "profile_url": payload.get("profile_url") or "",
        "raw_profile": {
            "channel_capture": payload,
            "raw_profile": raw_profile or payload,
        },
    }
    if not mapped["name"]:
        raise ValueError(f"boss contact has no name: {contact.platform_id}")
    return mapped


def _default_report_path(kind: str) -> Path:
    return Path("data") / "output" / f"talent-{kind}-{date.today().isoformat()}-boss-capture.md"


def _write_report(path: Path, title: str, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"- 渠道：{result['channel']}",
        f"- 输入人数：{result['input']}",
        f"- 预计新增：{result['created']}",
        f"- 预计合并：{result['merged']}",
        f"- 待确认：{result['pending']}",
        f"- 错误：{result['errors']}",
        "",
        "## 明细",
        "",
    ]
    for item in result.get("items", []):
        lines.append(f"- {item['name']} `{item['platform_id']}` -> {item['action']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def dry_run_capture(capture_file: str | Path, db_path: str | Path, report_path: str | Path | None = None) -> dict[str, Any]:
    capture = _load_json(Path(capture_file))
    channel, contacts = _contacts_from_capture(capture)
    db = TalentDB(db_path)
    result = {
        "channel": channel,
        "input": len(contacts),
        "created": 0,
        "merged": 0,
        "pending": 0,
        "errors": 0,
        "items": [],
    }
    try:
        for contact in contacts:
            try:
                mapped = _mapped_boss_contact(contact)
                existing_id = db._candidate_id_for_source(mapped, channel)
                action = "merged" if existing_id is not None else "created"
                result[action] += 1
                result["items"].append({
                    "name": mapped["name"],
                    "platform_id": contact.platform_id,
                    "action": action,
                })
            except Exception as exc:  # noqa: BLE001
                result["errors"] += 1
                result["items"].append({
                    "name": contact.payload.get("name") or "",
                    "platform_id": contact.platform_id,
                    "action": f"error: {exc}",
                })
    finally:
        db.close()

    _write_report(Path(report_path) if report_path else _default_report_path("dry-run"), "Boss 抓取结果 dry-run", result)
    return result


def apply_capture(
    capture_file: str | Path,
    db_path: str | Path,
    report_path: str | Path | None = None,
    confirm: str = "",
) -> dict[str, Any]:
    if confirm != BOSS_CONFIRM_TEXT:
        raise ValueError(f"正式写入必须传入确认文本：{BOSS_CONFIRM_TEXT}")

    capture = _load_json(Path(capture_file))
    channel, contacts = _contacts_from_capture(capture)
    db = TalentDB(db_path)
    result = dry_run_capture(capture_file, db_path, report_path or _default_report_path("apply"))
    written = 0
    try:
        for contact in contacts:
            mapped = _mapped_boss_contact(contact)
            db.ingest(mapped, channel)
            written += 1
    finally:
        db.close()
    result["written"] = written
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入多渠道浏览器抓取结果")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("dry-run", "apply"):
        sub = subparsers.add_parser(name)
        sub.add_argument("capture_file")
        sub.add_argument("--db", default="data/talent.db")
        sub.add_argument("--report")
        if name == "apply":
            sub.add_argument("--confirm", default="")

    args = parser.parse_args(argv)
    if args.command == "dry-run":
        dry_run_capture(args.capture_file, args.db, args.report)
        return 0
    if args.command == "apply":
        apply_capture(args.capture_file, args.db, args.report, args.confirm)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run import tests**

Run:

```powershell
python -m pytest tests/test_channel_capture_import.py -q
python -m py_compile scripts/channel_capture_import.py
```

Expected: PASS.

- [ ] **Step 5: Run related database tests**

Run:

```powershell
python -m pytest tests/test_talent_db.py tests/test_talent_models.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit import CLI**

```powershell
git add scripts/channel_capture_import.py tests/test_channel_capture_import.py
git commit -m "feat: import boss channel captures"
```

---

### Task 5: Add Boss Safe Search Assist and Passive Detail Markers

**Files:**
- Modify: `extensions/talent-channel-scraper/channels/boss/page_assist.js`
- Modify: `extensions/talent-channel-scraper/content.js`
- Modify: `extensions/talent-channel-scraper/background.js`
- Modify: `extensions/talent-channel-scraper/popup.html`
- Modify: `extensions/talent-channel-scraper/popup.js`
- Test: `tests/test_talent_channel_scraper_extension.py`

- [ ] **Step 1: Add failing tests for safe assist messages**

Append to `tests/test_talent_channel_scraper_extension.py`:

```python
def test_boss_safe_search_messages_are_wired():
    popup_html = read_extension_file("popup.html")
    popup_js = read_extension_file("popup.js")
    content = read_extension_file("content.js")
    background = read_extension_file("background.js")

    assert "btn-boss-safe-search" in popup_html
    assert "bossSafeSearch" in popup_js
    assert "bossSafeSearch" in background
    assert "__TALENT_CHANNEL_BOSS_SAFE_SEARCH__" in content


def test_boss_passive_detail_markers_exist():
    capture = read_extension_file("channels/boss/search_capture.js")
    background = read_extension_file("background.js")

    assert "passive_detail_capture" in capture
    assert "bossDetails" in background
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_talent_channel_scraper_extension.py -q
```

Expected: FAIL because safe search UI and passive detail markers are not wired.

- [ ] **Step 3: Add popup controls**

In `extensions/talent-channel-scraper/popup.html`, add a Boss section near the existing action buttons:

```html
<section class="panel" id="boss-panel">
  <h2>Boss</h2>
  <input id="boss-query" type="text" placeholder="关键词" />
  <button id="btn-boss-safe-search" type="button">Boss 安全搜索</button>
  <p id="boss-status">Boss 列表捕获会被动监听搜索结果。</p>
</section>
```

In `extensions/talent-channel-scraper/popup.js`, add:

```javascript
var bossButton = document.getElementById("btn-boss-safe-search");
if (bossButton) {
  bossButton.addEventListener("click", function () {
    var input = document.getElementById("boss-query");
    var query = input ? input.value : "";
    chrome.runtime.sendMessage({ type: "bossSafeSearch", query: query }, function (resp) {
      var status = document.getElementById("boss-status");
      if (!status) return;
      if (chrome.runtime.lastError) {
        status.textContent = chrome.runtime.lastError.message;
        return;
      }
      status.textContent = resp && resp.ok ? "Boss 搜索已触发" : "Boss 搜索未触发";
    });
  });
}
```

- [ ] **Step 4: Wire background to active Boss tab**

In `extensions/talent-channel-scraper/background.js`, add:

```javascript
function activeBossTab() {
  return new Promise(function (resolve, reject) {
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      var tab = tabs && tabs[0];
      if (!tab || !tab.url || tab.url.indexOf("zhipin.com") === -1) {
        reject(new Error("请先打开 Boss 搜索页"));
        return;
      }
      resolve(tab);
    });
  });
}
```

Add message branch:

```javascript
if (msg.type === "bossSafeSearch") {
  activeBossTab()
    .then(function (tab) {
      chrome.tabs.sendMessage(tab.id, { type: "bossSafeSearch", query: msg.query || "" }, function (resp) {
        if (chrome.runtime.lastError) {
          sendResponse({ ok: false, error: chrome.runtime.lastError.message });
          return;
        }
        sendResponse(resp || { ok: false, error: "no_response" });
      });
    })
    .catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
  return true;
}
```

- [ ] **Step 5: Bridge content message to MAIN world**

In `extensions/talent-channel-scraper/content.js`, add to `chrome.runtime.onMessage`:

```javascript
if (msg.type === "bossSafeSearch") {
  window.postMessage(
    {
      type: "__TALENT_CHANNEL_BOSS_SAFE_SEARCH__",
      query: msg.query || "",
    },
    "*"
  );
  sendResponse({ ok: true });
  return true;
}
```

Add to the `window.addEventListener("message", ...)` handler:

```javascript
if (event.data && event.data.type === "__TALENT_CHANNEL_BOSS_SAFE_SEARCH_RESULT__") {
  safeSendMessage({
    type: "bossSafeSearchResult",
    ok: Boolean(event.data.ok),
    error: event.data.error || "",
  });
}
```

- [ ] **Step 6: Handle safe search in MAIN world**

In `extensions/talent-channel-scraper/channels/boss/page_assist.js`, add:

```javascript
window.addEventListener("message", function (event) {
  if (!event.data || event.data.type !== "__TALENT_CHANNEL_BOSS_SAFE_SEARCH__") return;
  var result = requestBossSafeSearch({ query: event.data.query || "" });
  window.postMessage(
    {
      type: "__TALENT_CHANNEL_BOSS_SAFE_SEARCH_RESULT__",
      ok: Boolean(result.ok),
      error: result.error || "",
    },
    "*"
  );
});
```

- [ ] **Step 7: Add passive detail markers in Boss capture**

In `extensions/talent-channel-scraper/channels/boss/search_capture.js`, update URL classification:

```javascript
function isBossPassiveDetailUrl(url) {
  url = String(url || "");
  return url.indexOf("geek") !== -1 && url.indexOf("geeks.json") === -1;
}
```

When a JSON response matches this predicate, emit:

```javascript
window.postMessage(
  {
    type: "__TALENT_CHANNEL_BOSS_PASSIVE_DETAIL__",
    channel: "boss",
    mode: "passive_detail_capture",
    url: String(url || ""),
    data: body,
  },
  "*"
);
```

In `content.js`, forward it as `bossPassiveDetail`. In `background.js`, persist to `bossDetails` with `mode: "passive_detail_capture"`.

- [ ] **Step 8: Run tests and syntax checks**

Run:

```powershell
python -m pytest tests/test_talent_channel_scraper_extension.py -q
node --check extensions/talent-channel-scraper/channels/boss/page_assist.js
node --check extensions/talent-channel-scraper/channels/boss/search_capture.js
node --check extensions/talent-channel-scraper/content.js
node --check extensions/talent-channel-scraper/background.js
node --check extensions/talent-channel-scraper/popup.js
```

Expected: PASS.

- [ ] **Step 9: Commit Boss page assist**

```powershell
git add extensions/talent-channel-scraper tests/test_talent_channel_scraper_extension.py
git commit -m "feat: add boss safe search assist"
```

---

### Task 6: Document Workflow and Update Task Tracking

**Files:**
- Modify: `agents/workflows/talent-library/references/scenarios.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Add workflow documentation**

Append this section to `agents/workflows/talent-library/references/scenarios.md`:

```markdown
### Boss 列表抓取导入

适用场景：用户已经在真实 Chrome 中登录 Boss，并希望把搜索页候选人列表导入本地人才库。

流程：

1. 打开 Boss `/web/chat/search` 页面并手动设置城市、学历、经验、薪资等筛选条件。
2. 使用 `talent-channel-scraper` 插件被动捕获 `geeks.json` 搜索结果。
3. 如需自动输入关键词，只使用插件的 Boss 安全搜索，不主动访问详情页。
4. 导出完整 JSON，确认 `metadata.channel = "boss"`。
5. 运行 dry-run：

   ```bash
   python scripts/channel_capture_import.py dry-run path/to/boss-capture.json --db data/talent.db
   ```

6. 核对报告中的新增、合并、待确认和错误。
7. 确认后写入：

   ```bash
   python scripts/channel_capture_import.py apply path/to/boss-capture.json --db data/talent.db --confirm "确认写入boss列表"
   ```

8. 写入后按 `platforms=["boss"]` 过滤验证来源记录。

限制：

- Boss 第一版只承诺列表级 `partial` 数据。
- 插件不主动请求 Boss API，不自动打开 Boss 详情页，不新开 tab 探测登录态。
- 用户手动点击详情产生的自然请求只作为被动实验记录，默认不写入 `candidate_details`。
```

- [ ] **Step 2: Update `tasks/todo.md` implementation section**

Append:

```markdown
## Boss 渠道浏览器插件扩展实施（2026-05-12）

- [ ] Task 1：新增多渠道扩展契约测试
- [ ] Task 2：新建 `talent-channel-scraper` 并保持脉脉旧插件不变
- [ ] Task 3：实现 Boss 列表捕获、存储和统一导出
- [ ] Task 4：实现 Boss capture dry-run/apply 导入 CLI
- [ ] Task 5：实现 Boss 安全搜索辅助和详情被动捕获实验区
- [ ] Task 6：更新 workflow 文档并执行全量验证
```

- [ ] **Step 3: Run documentation grep checks**

Run:

```powershell
rg -n "Boss 列表抓取导入|channel_capture_import|确认写入boss列表" agents\workflows\talent-library\references\scenarios.md tasks\todo.md
```

Expected: all three strings appear.

- [ ] **Step 4: Commit documentation**

```powershell
git add agents/workflows/talent-library/references/scenarios.md tasks/todo.md
git commit -m "docs: document boss channel capture workflow"
```

---

### Task 7: Final Verification and Review

**Files:**
- No implementation files unless verification finds a bug.
- Modify: `tasks/todo.md` final Review section.

- [ ] **Step 1: Run focused extension tests**

Run:

```powershell
python -m pytest tests/test_talent_channel_scraper_extension.py tests/test_maimai_scraper_extension.py -q
```

Expected: PASS.

- [ ] **Step 2: Run focused import and adapter tests**

Run:

```powershell
python -m pytest tests/test_channel_capture_import.py scripts/test_boss.py tests/test_maimai_detail_import.py -q
```

Expected: PASS.

- [ ] **Step 3: Run all JavaScript syntax checks**

Run:

```powershell
node --check extensions/talent-channel-scraper/background.js
node --check extensions/talent-channel-scraper/content.js
node --check extensions/talent-channel-scraper/inject.js
node --check extensions/talent-channel-scraper/popup.js
node --check extensions/talent-channel-scraper/autopager.js
node --check extensions/talent-channel-scraper/detail_batch.js
node --check extensions/talent-channel-scraper/idb.js
node --check extensions/talent-channel-scraper/channels/common/capture_envelope.js
node --check extensions/talent-channel-scraper/channels/boss/parser.js
node --check extensions/talent-channel-scraper/channels/boss/search_capture.js
node --check extensions/talent-channel-scraper/channels/boss/page_assist.js
```

Expected: PASS for every file.

- [ ] **Step 4: Run full regression**

Run:

```powershell
python -m pytest tests scripts -q
```

Expected: PASS. Existing warning count is acceptable only if it matches the current baseline and is not introduced by this work.

- [ ] **Step 5: Check diff hygiene**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors. `git status --short` should list only intentional files before the final commit.

- [ ] **Step 6: Update final Review in `tasks/todo.md`**

Append:

```markdown
## Review

- Boss 列表抓取：`talent-channel-scraper` 可被动捕获 `geeks.json` 并导出统一 envelope。
- 入库闭环：`channel_capture_import.py` 支持 Boss dry-run、确认写入和写后来源验证。
- 风控边界：未实现 Boss 主动 API 请求、自动详情页导航或新开页面探测登录态。
- 脉脉回归：旧 `maimai-scraper` 目录保持不变，相关测试通过。
- 验证：记录本轮实际执行的 pytest、node --check、diff check 结果。
```

- [ ] **Step 7: Commit final review**

```powershell
git add tasks/todo.md
git commit -m "docs: record boss channel verification"
```

---

## Self-Review Notes

Spec coverage:

- Multi-channel plugin path is covered by Tasks 1-3.
- Boss list capture is covered by Tasks 1, 3, and 5.
- Unified envelope is covered by Tasks 2 and 3.
- Boss import dry-run/apply is covered by Task 4.
- Boss passive detail experiment is covered by Task 5.
- Maimai non-regression is covered by Tasks 2 and 7.
- Documentation and task tracking are covered by Task 6.

Execution rule:

- Implement tasks in order.
- Commit after each task.
- If a task uncovers a contradiction with the design, stop and revise the plan before continuing.
