# In-Dashboard User Manual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "使用手冊" page to the dashboard that renders Claude-authored
markdown chapters (`docs/manual/`) via a manifest table of contents, explaining
the system architecture and the meaning/rationale of each parameter.

**Architecture:** Content is markdown under `docs/manual/` (a `manual.json`
manifest is the TOC). The FastAPI server serves it via a small `/api/manual`
router. A new `frontend/view-manual.js` fetches the manifest, renders a chapter
sub-nav, and renders each chapter's markdown with `marked`. No build step (ESM
importmap, same as the rest of the frontend).

**Tech Stack:** Python/FastAPI (router + pytest), Preact + htm + `marked` (ESM
from esm.sh), markdown content.

**Spec source:** `docs/superpowers/specs/2026-06-25-user-manual-design.md`

## Global Constraints

Copied from the spec. Every task implicitly includes these.

- **Does NOT touch** trading-core (`src/okx_quant/strategies/`, `signals/`,
  `risk/`, `portfolio/`, `execution/`), the backtest engine, or any
  live/demo/shadow/deployment gate. This is a read-only docs/UI feature.
- **Language: zh-Hant** for all manual content and UI labels.
- **Drift control:** manual chapters explain meaning + rationale and **link** to
  the source of truth (`config/*.yaml`, `docs/FEATURE_MAP.md`,
  `docs/DOMAIN_RULES.md`, `docs/ai_collaboration.md`). Do **not** copy exact
  numeric limits/values into the manual — point at config instead.
- **No build step:** browser ESM via the `index.html` importmap, matching the
  existing frontend.
- **Ownership:** Task 1 (content) is **Claude's**; Tasks 2–4 (code) are
  **Codex's** (`frontend/`, `src/okx_quant/api/` are Codex areas).
- The manual is the "why" layer; it must not claim any strategy is validated or
  restate gate thresholds as authoritative — link the gate docs instead.

---

### Task 1: Manual content + manifest + smoke test (Claude)

Create the markdown chapters and the manifest TOC, plus a stdlib pytest that
keeps the manifest and files in sync. Four chapters are written in full; five are
visible stubs.

**Files:**
- Create: `docs/manual/manual.json`
- Create: `docs/manual/00-architecture.md` (written)
- Create: `docs/manual/10-backtest-validation.md` (written)
- Create: `docs/manual/20-strategies.md` (written)
- Create: `docs/manual/30-risk-limits.md` (written)
- Create: `docs/manual/40-data-pipeline.md` (stub)
- Create: `docs/manual/50-deployment-gates.md` (stub)
- Create: `docs/manual/60-frontend-views.md` (stub)
- Create: `docs/manual/70-config-files.md` (stub)
- Create: `docs/manual/80-glossary.md` (stub)
- Test: `tests/unit/test_manual_manifest.py`

**Interfaces:**
- Produces: `docs/manual/manual.json` with shape
  `{"title": str, "chapters": [{"slug": str, "title": str, "file": str, "status": "written"|"stub"}]}`.
  Tasks 2 and 3 rely on this exact shape.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_manual_manifest.py
import json
from pathlib import Path

MANUAL_DIR = Path(__file__).resolve().parents[2] / "docs" / "manual"


def test_manifest_is_valid_and_files_exist():
    manifest = json.loads((MANUAL_DIR / "manual.json").read_text(encoding="utf-8"))
    assert isinstance(manifest.get("title"), str) and manifest["title"]
    chapters = manifest.get("chapters")
    assert isinstance(chapters, list) and chapters
    slugs = set()
    for ch in chapters:
        for key in ("slug", "title", "file", "status"):
            assert ch.get(key), f"chapter missing {key}: {ch}"
        assert ch["status"] in {"written", "stub"}, ch["status"]
        assert ch["slug"] not in slugs, f"duplicate slug {ch['slug']}"
        slugs.add(ch["slug"])
        assert (MANUAL_DIR / ch["file"]).is_file(), f"missing file {ch['file']}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_manual_manifest.py -v`
Expected: FAIL — `FileNotFoundError` (no `docs/manual/manual.json` yet).

- [ ] **Step 3: Create the manifest**

```json
{
  "title": "使用手冊",
  "chapters": [
    { "slug": "architecture", "title": "系統架構總覽", "file": "00-architecture.md", "status": "written" },
    { "slug": "backtest-validation", "title": "回測與驗證 gate", "file": "10-backtest-validation.md", "status": "written" },
    { "slug": "strategies", "title": "策略與其參數", "file": "20-strategies.md", "status": "written" },
    { "slug": "risk-limits", "title": "風控限制", "file": "30-risk-limits.md", "status": "written" },
    { "slug": "data-pipeline", "title": "資料管線", "file": "40-data-pipeline.md", "status": "stub" },
    { "slug": "deployment-gates", "title": "部署階段 gate", "file": "50-deployment-gates.md", "status": "stub" },
    { "slug": "frontend-views", "title": "前端各頁說明", "file": "60-frontend-views.md", "status": "stub" },
    { "slug": "config-files", "title": "設定檔總覽", "file": "70-config-files.md", "status": "stub" },
    { "slug": "glossary", "title": "名詞對照", "file": "80-glossary.md", "status": "stub" }
  ]
}
```

- [ ] **Step 4: Write the four written chapters**

Each chapter follows **意義 → 設計理由 → 真值來源**, links source docs, and does
NOT hardcode config numbers. Required coverage per chapter (Claude authors the
prose; this is the content checklist, not placeholder text):

- `00-architecture.md`: EventBus → SignalGenerator → PortfolioManager →
  ExecutionHandler event flow; the `src/okx_quant/` module map; canonical vs
  market data layers; why maker-only / post-only. Link `README.md`,
  `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`.
- `10-backtest-validation.md`: replay engine, walk-forward, CPCV, DSR/PSR, honest
  family-cumulative `n_trials`, idealized-fill exclusion, differential validation,
  ct_val provenance — meaning + why each exists. Defer exact thresholds to
  `docs/ai_collaboration.md` (回測正確性 Gate / 部署 Gate) via links.
- `20-strategies.md`: one section per **enabled** strategy (`funding_carry`,
  `ma_crossover`, `ema_crossover`, `macd_crossover`) with its economic idea and a
  `參數 | 意義 | 設計理由 | 真值來源` table; value source =
  `config/strategies.yaml`. Note other strategies exist but are `enabled: false`.
  Link `research/strategy_synthesis.md`.
- `30-risk-limits.md`: `max_order_notional_usd`, `max_pos_pct_equity`,
  `max_leverage`, `max_daily_loss_pct`, `soft_drawdown_pct`, `hard_drawdown_pct`,
  `stale_quote_pct`, circuit breakers — meaning + why this kind of level; value
  source = `config/risk.yaml`. Link `docs/DOMAIN_RULES.md`.

- [ ] **Step 5: Write the five stub chapters**

Each stub file is a heading + one line. Example for `40-data-pipeline.md`:

```markdown
# 資料管線

本章待補。目前可先參考 [docs/DATA_FLOW.md](../DATA_FLOW.md) 與
[README.md 的 Architecture/Database 段落](../../README.md#database-layer)。
```

Write the analogous stub for `50-deployment-gates.md` (→ `docs/ai_collaboration.md`
部署 Gate), `60-frontend-views.md` (→ `README.md#frontend-dashboard`),
`70-config-files.md` (→ `config/settings.yaml`, `config/strategies.yaml`,
`config/risk.yaml`), `80-glossary.md` (→ the dashboard's existing Metrics
Glossary view).

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest tests/unit/test_manual_manifest.py -v`
Expected: PASS (manifest valid, all 9 files exist).

- [ ] **Step 7: Commit**

```bash
git add docs/manual/ tests/unit/test_manual_manifest.py
git commit -m "docs(manual): user-manual content + manifest + smoke test

AI-Origin: Claude"
```

---

### Task 2: `/api/manual` router (Codex)

Serve the manifest and per-chapter markdown. Only files declared in the manifest
are served (no path traversal).

**Files:**
- Create: `src/okx_quant/api/routes_manual.py`
- Modify: `src/okx_quant/api/server.py` (register the router before the static mount)
- Test: `tests/unit/test_routes_manual.py`

**Interfaces:**
- Consumes: `docs/manual/manual.json` shape from Task 1.
- Produces: `make_manual_router(manual_dir: Path) -> APIRouter` with
  `GET /api/manual` → manifest JSON and `GET /api/manual/{slug}` → chapter
  markdown as `text/plain`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_routes_manual.py
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from okx_quant.api.routes_manual import make_manual_router


def _client(tmp_path: Path) -> TestClient:
    (tmp_path / "manual.json").write_text(json.dumps({
        "title": "使用手冊",
        "chapters": [
            {"slug": "architecture", "title": "系統架構總覽",
             "file": "00-architecture.md", "status": "written"},
        ],
    }), encoding="utf-8")
    (tmp_path / "00-architecture.md").write_text("# 系統架構總覽\n\nhello", encoding="utf-8")
    app = FastAPI()
    app.include_router(make_manual_router(tmp_path), prefix="/api/manual")
    return TestClient(app)


def test_manifest_returned(tmp_path):
    r = _client(tmp_path).get("/api/manual")
    assert r.status_code == 200
    assert r.json()["chapters"][0]["slug"] == "architecture"


def test_chapter_markdown_returned(tmp_path):
    r = _client(tmp_path).get("/api/manual/architecture")
    assert r.status_code == 200
    assert "系統架構總覽" in r.text


def test_unknown_chapter_404(tmp_path):
    r = _client(tmp_path).get("/api/manual/nope")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_routes_manual.py -v`
Expected: FAIL — `ModuleNotFoundError: okx_quant.api.routes_manual`.

- [ ] **Step 3: Write the router**

```python
# src/okx_quant/api/routes_manual.py
"""Serve the in-dashboard user manual: manifest + per-chapter markdown."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse


def make_manual_router(manual_dir: Path) -> APIRouter:
    router = APIRouter()

    def _manifest() -> dict:
        path = manual_dir / "manual.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="manual manifest not found")
        return json.loads(path.read_text(encoding="utf-8"))

    @router.get("")
    def get_manifest() -> dict:
        return _manifest()

    @router.get("/{slug}", response_class=PlainTextResponse)
    def get_chapter(slug: str) -> str:
        chapter = next(
            (c for c in _manifest().get("chapters", []) if c.get("slug") == slug),
            None,
        )
        if chapter is None:
            raise HTTPException(status_code=404, detail="unknown chapter")
        # Only serve files declared in the manifest — no path traversal.
        file_path = manual_dir / chapter["file"]
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="chapter file missing")
        return file_path.read_text(encoding="utf-8")

    return router
```

- [ ] **Step 4: Register the router in `server.py`**

Add the import near the other route imports (after line 25):

```python
from okx_quant.api.routes_manual import make_manual_router
```

Inside `create_app`, before the `# Static files last` mount (currently line 140),
add (public, no auth — same trust level as the static docs):

```python
    app.include_router(
        make_manual_router(frontend_dir.parent / "docs" / "manual"),
        prefix="/api/manual",
        tags=["manual"],
    )
```

(`frontend_dir` is `_PROJECT_ROOT / "frontend"` per `engine.py:416`, so
`frontend_dir.parent / "docs" / "manual"` is the repo's `docs/manual/`.)

- [ ] **Step 5: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_routes_manual.py -v`
Expected: PASS (3 tests). If `fastapi.testclient` is missing, install dev deps:
`pip install -e ".[dev]"`.

- [ ] **Step 6: Commit**

```bash
git add src/okx_quant/api/routes_manual.py src/okx_quant/api/server.py tests/unit/test_routes_manual.py
git commit -m "feat(api): /api/manual router serving user-manual markdown

AI-Origin: Codex"
```

---

### Task 3: `view-manual.js` + `index.html` wiring (Codex)

Render the manual: fetch the manifest, show a chapter sub-nav, render each
chapter's markdown with `marked`. Stub chapters show a placeholder.

**Files:**
- Create: `frontend/view-manual.js`
- Modify: `frontend/index.html` (add `marked` to the importmap + the script tag)

**Interfaces:**
- Consumes: `GET /api/manual` and `GET /api/manual/{slug}` from Task 2.
- Produces: `window.ManualView` (a Preact component), consumed by Task 4's `app.js`.

- [ ] **Step 1: Write `frontend/view-manual.js`**

```js
import { h } from 'preact';
import { html } from 'htm/preact';
import { useState, useEffect } from 'preact/hooks';
import { marked } from 'marked';

function ManualView() {
  const [chapters, setChapters] = useState([]);
  const [active, setActive] = useState(null);
  const [content, setContent] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/manual")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((m) => {
        const chs = m.chapters || [];
        setChapters(chs);
        if (chs.length) setActive(chs[0]);
      })
      .catch(() => setError("無法載入手冊目錄 (manual.json)"));
  }, []);

  useEffect(() => {
    if (!active) return;
    setError(null);
    if (active.status === "stub") { setContent(""); return; }
    fetch(`/api/manual/${active.slug}`)
      .then((r) => (r.ok ? r.text() : Promise.reject(r.status)))
      .then((md) => setContent(marked.parse(md)))
      .catch(() => setError(`無法載入章節內容：${active.file}`));
  }, [active]);

  return html`
    <div class="row" style=${{ gap: "var(--gap-lg)", alignItems: "flex-start" }}>
      <aside class="card" style=${{ minWidth: 200, maxWidth: 240 }}>
        <div class="card-title" style=${{ marginBottom: 8 }}>章節</div>
        ${chapters.map((c) => html`
          <div
            key=${c.slug}
            class="nav-item"
            aria-current=${active && active.slug === c.slug ? "page" : undefined}
            onClick=${() => setActive(c)}
          >
            <span>${c.title}</span>
            ${c.status === "stub" && html`<span class="chip" style=${{ marginLeft: "auto" }}>待補</span>`}
          </div>
        `)}
      </aside>
      <div class="card" style=${{ flex: 1 }}>
        ${error && html`<div style=${{ color: "var(--loss)" }}>${error}</div>`}
        ${!error && active && active.status === "stub" && html`
          <div class="col" style=${{ gap: 8 }}>
            <div class="card-title">${active.title}</div>
            <div style=${{ color: "var(--text-muted)" }}>本章待補。請先參考 source docs。</div>
          </div>
        `}
        ${!error && active && active.status !== "stub" && html`
          <div class="manual-content" dangerouslySetInnerHTML=${{ __html: content }}></div>
        `}
      </div>
    </div>
  `;
}

window.ManualView = ManualView;
```

`// ponytail: 第一方可信 markdown，免 sanitizer；若日後接受外部投稿再加。`

- [ ] **Step 2: Add `marked` to the importmap in `index.html`**

In the `<script type="importmap">` block (currently lines 12–20), add a `marked`
entry:

```json
{
  "imports": {
    "preact": "https://esm.sh/preact@10.24.3",
    "preact/hooks": "https://esm.sh/preact@10.24.3/hooks",
    "htm/preact": "https://esm.sh/htm@3.1.1/preact",
    "marked": "https://esm.sh/marked@13"
  }
}
```

- [ ] **Step 3: Add the script tag in `index.html`**

Add before `<script type="module" src="app.js"></script>` (currently line 34):

```html
<script type="module" src="view-manual.js"></script>
```

- [ ] **Step 4: Static check**

Run: `python -m pytest tests/unit/test_manual_manifest.py tests/unit/test_routes_manual.py -v`
Expected: PASS (no regression). Confirm `index.html` now contains both `marked`
and `view-manual.js` (e.g. `rg "marked|view-manual" frontend/index.html`).

- [ ] **Step 5: Commit**

```bash
git add frontend/view-manual.js frontend/index.html
git commit -m "feat(frontend): ManualView renders user-manual markdown

AI-Origin: Codex"
```

---

### Task 4: Register the Manual view in `app.js` + docs (Codex)

Wire the view into the dashboard nav and update the UI/feature docs.

**Files:**
- Modify: `frontend/app.js` (NAV, titleMap, NavGlyph, render line)
- Modify: `docs/UI_MAP.md` (new view row)
- Modify: `docs/FEATURE_MAP.md` (manual feature ownership: `docs/manual/`,
  `frontend/view-manual.js`, `src/okx_quant/api/routes_manual.py`)

**Interfaces:**
- Consumes: `window.ManualView` from Task 3.

- [ ] **Step 1: Add the NAV entry**

In `app.js`, append to the `NAV` array (currently ends line 171):

```javascript
    { id: "manual", label: "使用手冊", group: "Help", glyph: "manual" },
```

- [ ] **Step 2: Add the titleMap entry**

In the `titleMap` object (currently ends ~line 183), add:

```javascript
    manual: ["使用手冊", "系統架構與參數設計說明"],
```

- [ ] **Step 3: Add the nav glyph**

In `NavGlyph`'s `switch`, before `default:` (line 31), add a book glyph:

```javascript
    case "manual": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><path d="M3 2.5h7a1.5 1.5 0 0 1 1.5 1.5v10H4.5A1.5 1.5 0 0 1 3 13z"/><path d="M6 5.5h4M6 8h4"/></svg>`;
```

- [ ] **Step 4: Add the render line**

In `app-main` (after the metrics line, currently line 268), add:

```javascript
        ${view === "manual" && html`<${window.ManualView} />`}
```

- [ ] **Step 5: Update docs**

Add a row for the Manual view to `docs/UI_MAP.md` and a feature entry to
`docs/FEATURE_MAP.md` listing the owning files (`docs/manual/`,
`frontend/view-manual.js`, `src/okx_quant/api/routes_manual.py`,
`app.js` nav). No Change Manifest required (API-route / frontend changes are
`manifest=False` in `docs/DOC_IMPACT_MATRIX.md`).

- [ ] **Step 6: Checks**

Run: `python -m pytest tests/unit/test_manual_manifest.py tests/unit/test_routes_manual.py -v`
Run: `python scripts/docs/check_doc_impact.py` (advisory; confirm the manual
changes show paired UI_MAP/FEATURE_MAP doc updates).

Manual browser smoke (when an env is available): start the dashboard
(`python -m okx_quant.engine` with `config/settings.yaml` `system.mode: demo`),
open `http://localhost:8080`, click **使用手冊** in the Help nav group, and
confirm: chapter list renders, 系統架構總覽 renders as formatted markdown, and a
待補 stub shows the placeholder. If no demo env is available, report it skipped —
the manifest + router tests gate the data path.

- [ ] **Step 7: Commit**

```bash
git add frontend/app.js docs/UI_MAP.md docs/FEATURE_MAP.md
git commit -m "feat(frontend): register 使用手冊 view in dashboard nav

AI-Origin: Codex"
```

---

## Self-Review

**Spec coverage:**
- Locked decision 1 (in-dashboard page) → Tasks 3–4. ✓
- Locked decision 2 (phased: skeleton + key chapters) → Task 1 (4 written + 5
  stubs, all in manifest). ✓
- Locked decision 3 (markdown in `docs/manual/` rendered by view) → Task 1
  content + Task 2 serving + Task 3 render. ✓
- Locked decision 4 (zh-Hant) → Global Constraints + content tasks. ✓
- Locked decision 5 (drift control via links) → Global Constraints + Task 1
  content checklist. ✓
- Serving (the spec's open choice) → resolved to a `/api/manual` router (Task 2),
  not a static mount. ✓
- Testing (manifest smoke, router, render, stub placeholder) → Task 1 test, Task
  2 tests, Task 4 browser smoke. ✓
- Ownership split (Claude content, Codex code) → Task 1 vs Tasks 2–4. ✓

**Placeholder scan:** Task 1 prose is authored by Claude against an explicit
per-chapter content checklist (not "write docs"). All code steps show full code.
No TBD/TODO. ✓

**Type consistency:** `manual.json` shape (`title`, `chapters[].{slug,title,file,
status}`), `make_manual_router(manual_dir)`, `/api/manual` + `/api/manual/{slug}`,
and `window.ManualView` are used identically across Tasks 1–4. ✓

## Notes for the executor

- Task 1 is **Claude's** (content). Tasks 2–4 are **Codex's** (code). If Claude
  has already authored `docs/manual/`, Codex starts at Task 2 and reuses the
  existing manifest/tests.
- The frontend has no JS test runner; Tasks 3–4 are gated by the Python
  manifest + router tests plus a manual browser smoke. This is expected, not a
  coverage gap to paper over.
- No trading-core, strategy, risk, or gate logic is touched by any task.
