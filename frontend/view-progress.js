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
        const glyph = isDone ? "✓" : isCurrent ? "•" : "";
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
