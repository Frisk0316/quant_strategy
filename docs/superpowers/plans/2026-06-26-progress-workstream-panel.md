---
status: current
type: plan
owner: human
created: 2026-06-26
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Progress Panel → Workstream Milestone View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the git-centric Progress panel with a curated workstream milestone-stepper view sourced from a hand-maintained `config/workstreams.yaml`.

**Architecture:** `/api/progress` stops shelling out to git entirely; `routes_progress.py` becomes a pure YAML reader that loads `config/workstreams.yaml`, validates each entry at the trust boundary, and tags every milestone `done`/`current`/`pending`. The frontend `view-progress.js` renders one card per workstream with a horizontal milestone stepper. Git timeline and `STATUS.md` branch cards are deleted.

**Tech Stack:** FastAPI + PyYAML (`pyyaml>=6.0`, already a dependency) for the backend; Preact + htm (no build step, served static) for the frontend.

**Source spec:** `docs/superpowers/specs/2026-06-26-progress-workstream-panel-design.md`

**AI-Origin:** Implemented by Codex. Commit with an `AI-Origin: Codex` trailer.

## Global Constraints

- PERMITTED files only: `config/workstreams.yaml`, `src/okx_quant/api/routes_progress.py`, `frontend/view-progress.js`, `tests/unit/test_routes_progress.py`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `AGENTS.md`, `CLAUDE.md`.
- FORBIDDEN: `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`; any `config/*.yaml` except the new `workstreams.yaml`; other API route files; `scripts/run_server.py`; any `results/` artifact; any demo/shadow/live/config gate.
- Do not touch `STATUS.md` content — it stays as a human branch board, just no longer feeds the panel.
- Reuse the existing YAML pattern: `yaml.safe_load(path.read_text(encoding="utf-8"))`.
- The panel is read-only; no DB, network, or write path is added.
- `status` enum is exactly `active | blocked | done | shelved`. Milestone `state` enum is exactly `done | current | pending`.

---

## File Structure

- `src/okx_quant/api/routes_progress.py` — sole backend responsibility: load + validate `workstreams.yaml`, shape the `/api/progress` payload. All git/STATUS.md helpers removed.
- `config/workstreams.yaml` — the hand-maintained source of truth (data, not code).
- `frontend/view-progress.js` — sole responsibility: render the workstream cards + stepper. All timeline/branch components removed.
- `tests/unit/test_routes_progress.py` — unit tests for the loader, validation, and route shape.

---

### Task 1: Backend — replace `routes_progress.py` with the workstream loader

**Files:**
- Modify (full rewrite): `src/okx_quant/api/routes_progress.py`
- Test: `tests/unit/test_routes_progress.py`

**Interfaces:**
- Produces:
  - `_milestone_states(milestones: list[str], current: str, status: str) -> list[dict[str, str]]` — each `{"name": str, "state": "done"|"current"|"pending"}`.
  - `_normalize_workstream(raw: dict) -> dict` — one card dict with keys `name, status, state, next, links, updated, milestones, error`.
  - `_load_workstreams(repo_dir: Path) -> tuple[list[dict], str | None]` — `(cards, file_error)`.
  - `build_progress_payload(repo_dir: Path) -> dict` — `{"generated_at": str, "workstreams": list[dict], "error": str | None}`.
  - `make_progress_router(repo_dir: Path | None = None) -> APIRouter` — unchanged signature; route still mounted at `""` under prefix `/api/progress`.

- [ ] **Step 1: Rewrite the test file with the failing tests**

Replace the entire contents of `tests/unit/test_routes_progress.py` with:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from okx_quant.api.routes_progress import (
    _load_workstreams,
    build_progress_payload,
    make_progress_router,
)


def _write(tmp_path: Path, text: str) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir(exist_ok=True)
    (cfg / "workstreams.yaml").write_text(text, encoding="utf-8")


def test_load_workstreams_splits_milestones(tmp_path: Path):
    _write(tmp_path, """
workstreams:
  - name: XS momentum
    status: blocked
    milestones: [spec, impl, backtest, wf_cpcv, demo, live]
    current: wf_cpcv
    state: "PSR 0.82 < 0.95"
    next: "rerun after sizing fix"
    links: [docs/x.md]
    updated: 2026-06-26
""")
    cards, err = _load_workstreams(tmp_path)
    assert err is None
    assert len(cards) == 1
    card = cards[0]
    assert card["error"] is None
    assert card["status"] == "blocked"
    assert card["links"] == ["docs/x.md"]
    states = {m["name"]: m["state"] for m in card["milestones"]}
    assert states == {
        "spec": "done", "impl": "done", "backtest": "done",
        "wf_cpcv": "current", "demo": "pending", "live": "pending",
    }


def test_status_done_marks_all_done(tmp_path: Path):
    _write(tmp_path, """
workstreams:
  - name: Manual
    status: done
    milestones: [draft, write, verify]
    current: verify
""")
    cards, _ = _load_workstreams(tmp_path)
    assert all(m["state"] == "done" for m in cards[0]["milestones"])


def test_current_not_in_milestones_is_card_error(tmp_path: Path):
    _write(tmp_path, """
workstreams:
  - name: Bad
    milestones: [a, b]
    current: zzz
""")
    cards, err = _load_workstreams(tmp_path)
    assert err is None
    assert cards[0]["error"]
    assert cards[0]["milestones"] == []


def test_missing_current_is_card_error_when_not_done(tmp_path: Path):
    _write(tmp_path, """
workstreams:
  - name: NoCurrent
    milestones: [a, b]
""")
    cards, _ = _load_workstreams(tmp_path)
    assert cards[0]["error"]


def test_malformed_yaml_returns_payload_error(tmp_path: Path):
    _write(tmp_path, "workstreams: [unclosed\n")
    cards, err = _load_workstreams(tmp_path)
    assert cards == []
    assert err and "parse error" in err


def test_missing_file_is_empty_not_error(tmp_path: Path):
    cards, err = _load_workstreams(tmp_path)
    assert cards == []
    assert err is None


def test_progress_route_returns_200_with_workstreams_shape(tmp_path: Path):
    app = FastAPI()
    app.include_router(make_progress_router(tmp_path), prefix="/api/progress")
    resp = TestClient(app).get("/api/progress")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["workstreams"] == []
    assert payload["error"] is None
    assert "timeline" not in payload
    assert "branches" not in payload
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_routes_progress.py -q`
Expected: FAIL / ERROR — `_load_workstreams` does not exist yet, and the old `classify_actor`/`parse_status_md` imports are gone.

- [ ] **Step 3: Rewrite `routes_progress.py`**

Replace the entire contents of `src/okx_quant/api/routes_progress.py` with:

```python
"""Read-only workstream progress dashboard API.

Reads config/workstreams.yaml (hand-maintained) and reports each workstream's
milestone progress. No git, no DB, no network — the endpoint never spawns a
subprocess.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter

_VALID_STATUS = {"active", "blocked", "done", "shelved"}


def _milestone_states(milestones: list[str], current: str, status: str) -> list[dict[str, str]]:
    """Tag each milestone done/current/pending.

    Milestones before `current` are done, `current` is in progress, the rest are
    pending. status == "done" marks every milestone done.
    """
    out: list[dict[str, str]] = []
    seen_current = False
    for name in milestones:
        if status == "done":
            state = "done"
        elif name == current:
            state = "current"
            seen_current = True
        elif seen_current:
            state = "pending"
        else:
            state = "done"
        out.append({"name": str(name), "state": state})
    return out


def _normalize_workstream(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate one entry; on bad input return a card carrying a non-null `error`."""
    name = raw.get("name")
    milestones = raw.get("milestones")
    status = raw.get("status", "active")
    current = raw.get("current")

    card: dict[str, Any] = {
        "name": str(name) if name else "(unnamed)",
        "status": status,
        "state": raw.get("state", ""),
        "next": raw.get("next", ""),
        "links": [str(x) for x in (raw.get("links") or [])],
        "updated": raw.get("updated"),
        "milestones": [],
        "error": None,
    }

    if not name:
        card["error"] = "missing 'name'"
        return card
    if not isinstance(milestones, list) or not milestones:
        card["error"] = "missing or empty 'milestones'"
        return card
    if status not in _VALID_STATUS:
        card["error"] = f"invalid status '{status}' (expected {sorted(_VALID_STATUS)})"
        return card
    if status != "done":
        if current is None:
            card["error"] = "missing 'current'"
            return card
        if current not in milestones:
            card["error"] = f"'current' ({current!r}) not in milestones"
            return card

    card["milestones"] = _milestone_states([str(m) for m in milestones], str(current), status)
    return card


def _load_workstreams(repo_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Read config/workstreams.yaml. Returns (cards, file_error).

    Missing file -> ([], None) so the panel shows an empty state, not an error.
    Malformed YAML -> ([], "parse error: ...") surfaced as a payload-level error.
    """
    path = repo_dir / "config" / "workstreams.yaml"
    if not path.is_file():
        return [], None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [], f"workstreams.yaml parse error: {exc}"
    entries = data.get("workstreams") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return [], None
    return [_normalize_workstream(e if isinstance(e, dict) else {}) for e in entries], None


def build_progress_payload(repo_dir: Path) -> dict[str, Any]:
    workstreams, error = _load_workstreams(repo_dir)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workstreams": workstreams,
        "error": error,
    }


def make_progress_router(repo_dir: Path | None = None) -> APIRouter:
    router = APIRouter()
    root = (repo_dir or Path(__file__).resolve().parents[3]).resolve()

    @router.get("")
    def progress() -> dict[str, Any]:
        return build_progress_payload(root)

    return router
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/test_routes_progress.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/okx_quant/api/routes_progress.py tests/unit/test_routes_progress.py
git commit -m "feat(progress): workstream loader replaces git timeline backend

AI-Origin: Codex"
```

---

### Task 2: Seed `config/workstreams.yaml`

**Files:**
- Create: `config/workstreams.yaml`
- Test: `tests/unit/test_routes_progress.py` (add one test for the shipped file)

**Interfaces:**
- Consumes: `_load_workstreams` from Task 1.

- [ ] **Step 1: Add a failing test that the shipped file is valid**

Append to `tests/unit/test_routes_progress.py`:

```python
def test_shipped_workstreams_yaml_is_valid():
    repo_root = Path(__file__).resolve().parents[2]
    cards, err = _load_workstreams(repo_root)
    assert err is None, err
    assert cards, "expected seeded workstreams"
    bad = [c["name"] for c in cards if c["error"]]
    assert not bad, f"cards with errors: {bad}"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/unit/test_routes_progress.py::test_shipped_workstreams_yaml_is_valid -q`
Expected: FAIL — `config/workstreams.yaml` does not exist yet (`cards == []` → "expected seeded workstreams").

- [ ] **Step 3: Create `config/workstreams.yaml`**

Seed from current state in `docs/AI_HANDOFF.md` + `STATUS.md`:

```yaml
# Hand-maintained source for the 進度 / Progress panel.
# Update this alongside docs/AI_HANDOFF.md at session end.
# status: active | blocked | done | shelved
# Milestones before `current` are treated done; `current` is in progress; the rest pending.
workstreams:
  - name: XS momentum
    status: blocked
    milestones: [spec, impl, backtest, wf_cpcv, demo, live]
    current: wf_cpcv
    state: "PSR 0.82 < 0.95 — promotion BLOCKED; xs_momentum stays disabled"
    next: "re-run after portfolio-vol sizing decision; raise PSR >= 0.95"
    links: [docs/superpowers/plans/2026-06-23-xs-momentum-universe.md]
    updated: 2026-06-25

  - name: Strategy research pipeline (batch 1 S5/S6/S7)
    status: blocked
    milestones: [spec, impl, backtest, wf_cpcv, review]
    current: wf_cpcv
    state: "S6 statistical_gate_passed:false; S5 data-universe artifact; S7 shelved_pending_research_review"
    next: "research review of refit artifacts before any adapter/ct_val work"
    links: [docs/superpowers/plans/2026-06-25-strategy-research-pipeline-stage1.md]
    updated: 2026-06-25

  - name: Multi-venue instrument specs (ADR-0007 P1)
    status: active
    milestones: [spec, impl, validation, consolidated_pr, merge]
    current: consolidated_pr
    state: "DB-parity PASS evidence committed; waiting on one consolidated P1 PR -> main"
    next: "open the consolidated P1 PR"
    links: [docs/superpowers/plans/2026-06-17-multi-venue-instrument-specs-p1.md]
    updated: 2026-06-23

  - name: User manual
    status: done
    milestones: [draft, write, verify]
    current: verify
    state: "All chapters written; manual.json marks chapters as written"
    next: ""
    links: [docs/superpowers/plans/2026-06-25-user-manual.md]
    updated: 2026-06-25
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/unit/test_routes_progress.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add config/workstreams.yaml tests/unit/test_routes_progress.py
git commit -m "feat(progress): seed config/workstreams.yaml from current state

AI-Origin: Codex"
```

---

### Task 3: Frontend — rewrite `view-progress.js` to the workstream view

**Files:**
- Modify (full rewrite): `frontend/view-progress.js`

**Interfaces:**
- Consumes: `window.API.fetchProgress()` → `{ generated_at, workstreams: [{name, status, state, next, links, updated, milestones:[{name,state}], error}], error }` (from Task 1; unchanged API client).

- [ ] **Step 1: Replace the entire contents of `frontend/view-progress.js`**

```javascript
import { h } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { html } from 'htm/preact';

const STATUS_CHIP = { active: "accent", blocked: "bad", done: "ok", shelved: "" };

function Stepper({ milestones, status }) {
  return html`
    <div class="row wrap" style=${{ gap: 0, alignItems: "flex-start" }}>
      ${milestones.map((m, i) => {
        const isDone = m.state === "done";
        const isCurrent = m.state === "current";
        const color = isDone
          ? "var(--profit)"
          : isCurrent
            ? (status === "blocked" ? "var(--loss, #e5484d)" : "var(--accent)")
            : "var(--border)";
        const filled = isDone || isCurrent;
        const glyph = isDone ? "✓" : isCurrent ? "●" : "○";
        return html`
          <div key=${m.name} class="row" style=${{ gap: 0, alignItems: "center" }}>
            ${i > 0 && html`<span style=${{ width: 16, height: 2, background: "var(--border)", marginTop: -14 }}></span>`}
            <div class="col" style=${{ alignItems: "center", gap: 3, width: 64 }}>
              <span style=${{
                width: 18, height: 18, borderRadius: 999, display: "grid", placeItems: "center",
                fontSize: 11, lineHeight: 1,
                color: filled ? "#fff" : "var(--text-subtle)",
                background: filled ? color : "transparent",
                border: `1px solid ${color}`,
              }}>${glyph}</span>
              <span class="mono" style=${{
                fontSize: 10, textAlign: "center", overflowWrap: "anywhere",
                color: isCurrent ? "var(--text)" : "var(--text-subtle)",
                fontWeight: isCurrent ? 600 : 400,
              }}>${m.name}</span>
            </div>
          </div>
        `;
      })}
    </div>
  `;
}

function WorkstreamCard({ ws }) {
  if (ws.error) {
    return html`
      <div class="card">
        <div class="card-h">
          <div class="card-title" style=${{ overflowWrap: "anywhere" }}>${ws.name}</div>
          <span class="chip bad">error</span>
        </div>
        <div class="empty">${ws.error}</div>
      </div>
    `;
  }
  const dim = ws.status === "shelved";
  return html`
    <div class="card" style=${{ opacity: dim ? 0.55 : 1 }}>
      <div class="card-h">
        <div style=${{ minWidth: 0 }}>
          <div class="card-title" style=${{ overflowWrap: "anywhere" }}>${ws.name}</div>
          ${ws.updated && html`<div class="card-sub">updated ${ws.updated}</div>`}
        </div>
        <span class=${`chip ${STATUS_CHIP[ws.status] || ""}`}>${ws.status}</span>
      </div>
      <div class="grid" style=${{ gap: 12 }}>
        <${Stepper} milestones=${ws.milestones || []} status=${ws.status} />
        ${ws.state && html`
          <div style=${{ fontSize: 13, lineHeight: 1.45, overflowWrap: "anywhere" }}>
            <span class="metric-label">state </span>${ws.state}
          </div>`}
        ${ws.next && html`
          <div style=${{ fontSize: 13, color: "var(--text-muted)", overflowWrap: "anywhere" }}>
            <span class="metric-label">next </span>${ws.next}
          </div>`}
        ${ws.links && ws.links.length ? html`
          <div class="row wrap" style=${{ gap: 6 }}>
            ${ws.links.map((lnk) => html`
              <a key=${lnk} class="chip" href=${"/" + lnk} target="_blank" rel="noreferrer"
                 style=${{ textTransform: "none", overflowWrap: "anywhere" }}>${lnk}</a>`)}
          </div>` : null}
      </div>
    </div>
  `;
}

function ProgressView() {
  const [payload, setPayload] = useState(null);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let alive = true;
    window.API.fetchProgress()
      .then((data) => { if (alive) setPayload(data); })
      .catch((err) => { if (alive) setLoadError(err.message || String(err)); });
    return () => { alive = false; };
  }, []);

  if (loadError) return html`<div class="card"><div class="empty">${loadError}</div></div>`;
  if (!payload) return html`<div class="card"><div class="empty">Loading progress...</div></div>`;
  if (payload.error) return html`<div class="card"><div class="empty">${payload.error}</div></div>`;

  const workstreams = payload.workstreams || [];
  const countBy = (s) => workstreams.filter((w) => w.status === s).length;

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="grid" style=${{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
        <div class="kpi"><div class="kpi-label">Workstreams</div><div class="kpi-value">${workstreams.length}</div></div>
        <div class="kpi"><div class="kpi-label">Active</div><div class="kpi-value">${countBy("active")}</div></div>
        <div class="kpi"><div class="kpi-label">Blocked</div><div class="kpi-value">${countBy("blocked")}</div></div>
        <div class="kpi"><div class="kpi-label">Done</div><div class="kpi-value">${countBy("done")}</div></div>
      </div>
      <div class="grid" style=${{ gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
        ${workstreams.length
          ? workstreams.map((ws) => html`<${WorkstreamCard} key=${ws.name} ws=${ws} />`)
          : html`<div class="card"><div class="empty">No workstreams in config/workstreams.yaml</div></div>`}
      </div>
    </div>
  `;
}

window.ProgressView = ProgressView;
```

- [ ] **Step 2: Syntax-check the file**

Run: `node --check frontend/view-progress.js`
Expected: no output, exit 0. (This is the repo's established JS check — see `docs/AI_HANDOFF.md` 2026-06-25 progress-panel note. If `node --check` rejects ES `import`, run it the same way the prior progress-panel commit did.)

- [ ] **Step 3: Commit**

```bash
git add frontend/view-progress.js
git commit -m "feat(progress): render workstream milestone steppers, drop git timeline UI

AI-Origin: Codex"
```

---

### Task 4: Docs + maintenance contract

**Files:**
- Modify: `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `AGENTS.md`, `CLAUDE.md`

- [ ] **Step 1: Update `docs/UI_MAP.md`**

Find the `frontend/view-progress.js` section (the lines describing "commit timeline rows colored by actor and branch cards from STATUS.md"). Replace that description with:

```markdown
- `frontend/view-progress.js` owns the `進度 / Progress` view in the Analysis nav
  group.
- It calls `GET /api/progress` through `window.API.fetchProgress`.
- The panel renders one card per workstream from `config/workstreams.yaml`, each
  with a horizontal milestone stepper (done/current/pending; current turns red
  when status is blocked) plus state/next lines and doc links.
- Backend endpoint is implemented in `src/okx_quant/api/routes_progress.py`; it
  reads `config/workstreams.yaml` only — no git, DB, or network.
```

Also update the `fetchProgress` line if it describes the old payload.

- [ ] **Step 2: Update `docs/DATA_FLOW.md`**

In the row/section for `/api/progress`, change the data source from "local git metadata, STATUS.md, linked plan checkboxes" to "`config/workstreams.yaml` (hand-maintained); no git/DB/network read".

- [ ] **Step 3: Update `docs/FEATURE_MAP.md`**

In the Progress-panel ownership row, change the behavior description to "workstream milestone view sourced from `config/workstreams.yaml`" (was git timeline + STATUS.md branch board).

- [ ] **Step 4: Add the maintenance contract to `AGENTS.md` and `CLAUDE.md`**

In `AGENTS.md` under the Context Resilience Harness session-end bullet (the line about ending each session with a Context Handoff), add:

```markdown
- Update `config/workstreams.yaml` whenever you update `docs/AI_HANDOFF.md`, so the
  Progress panel's per-workstream milestone status stays honest.
```

In `CLAUDE.md` under "## Session End", add the same line to the bullet list.

- [ ] **Step 5: Update state docs**

Add a dated note to `docs/AI_HANDOFF.md` (top of Current Goal area) and refresh `docs/CURRENT_STATE.md`:

```text
2026-06-26 Progress panel reworked: git timeline + STATUS.md branch cards removed;
panel now renders curated workstream milestone steppers from config/workstreams.yaml
(read-only). Maintenance contract: update config/workstreams.yaml alongside this file.
```

- [ ] **Step 6: Run the docs check**

Run: `make docs-check`
Expected: pass (pre-existing metadata warnings are acceptable). If `make` is unavailable in the shell, run the underlying scripts directly (e.g. `python scripts/docs/check_human_overview.py` and the feature-map/link checks the Makefile invokes) and report which ran.

- [ ] **Step 7: Commit**

```bash
git add docs/UI_MAP.md docs/DATA_FLOW.md docs/FEATURE_MAP.md docs/AI_HANDOFF.md docs/CURRENT_STATE.md AGENTS.md CLAUDE.md
git commit -m "docs(progress): workstream panel docs + workstreams.yaml maintenance contract

AI-Origin: Codex"
```

---

## Acceptance Criteria

- [ ] `python -m pytest tests/unit/test_routes_progress.py -q` is green (8 tests).
- [ ] `GET /api/progress` returns `{generated_at, workstreams, error}` with no `timeline`/`branches` keys.
- [ ] Missing `config/workstreams.yaml` → 200 with `workstreams == []`; malformed YAML or bad `current` → no crash, error surfaced.
- [ ] No `subprocess`/`git` reference remains in `src/okx_quant/api/routes_progress.py`.
- [ ] `node --check frontend/view-progress.js` passes; panel shows workstream cards + steppers, no timeline/branch cards.
- [ ] `config/workstreams.yaml` loads with zero per-card errors.
- [ ] `AGENTS.md` and `CLAUDE.md` carry the `config/workstreams.yaml` session-end maintenance line.
- [ ] Server restarted so the running instance serves the new route/panel.

## Self-Review

- **Spec coverage:** data schema → Task 2; loader + validation + payload shape → Task 1; frontend stepper + git removal → Task 3; docs + maintenance contract → Task 4; seed list → Task 2. All spec sections mapped.
- **Placeholder scan:** none — every code/test block is complete; the only intentionally empty value is the manual workstream's `next: ""`.
- **Type consistency:** `_load_workstreams` returns `(list, str|None)` and is consumed that way in Task 1 tests, Task 2 test, and `build_progress_payload`. Card keys (`name/status/state/next/links/updated/milestones/error`) and milestone keys (`name/state`) match between backend (Task 1), seed (Task 2), and frontend (Task 3).

## Notes for the executor

- Restart the FastAPI server (`scripts/run_server.py`) after Task 3 — the running instance holds the old module in memory; until restart the live panel will not reflect the change.
- This is a business-rule-neutral, read-only UI/API change: no Change Manifest, ADR, or gate edit is required (`docs/DOC_IMPACT_MATRIX.md` rows for PnL/fee/funding/sizing/fills/gates are untouched).
