---
status: accepted
type: adr
owner: human
created: 2026-05-11
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# ADR-0004: Frontend Module Loading

## Status

Accepted — 2026-05-11

## Context

The frontend is a vanilla JS SPA using native ES modules (`<script type="module">`). Browsers enforce strict MIME type checking for ES modules: the server must respond with `Content-Type: application/javascript` (or `text/javascript`). Any other MIME type causes a silent blank page with a console error.

FastAPI's `StaticFiles` derives MIME types from the OS `mimetypes` registry. On some systems (Windows, minimal Docker images), `.js` files may not be registered, causing `StaticFiles` to serve them as `application/octet-stream` or `text/plain`, which browsers reject for `type="module"`.

## Decision

The FastAPI server (`src/okx_quant/api/server.py`) explicitly registers JavaScript MIME types before mounting `StaticFiles`:

```python
import mimetypes
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".jsx")
mimetypes.add_type("application/javascript", ".mjs")
```

This registration must happen before `StaticFiles` is instantiated.

**Frontend file extension convention:** All frontend modules use `.js`. The `.jsx` extension is accepted but not required.

## Consequences

- Any PR that modifies `server.py` must verify MIME registration is preserved
- The smoke test for a frontend deployment: `curl -I http://localhost:8080/app.js` must return `Content-Type: application/javascript`
- If the frontend is ever migrated to a build step (Vite, esbuild), this MIME fix becomes irrelevant — update this ADR at that point
- Adding new file extensions to the frontend requires adding a matching `mimetypes.add_type()` call
