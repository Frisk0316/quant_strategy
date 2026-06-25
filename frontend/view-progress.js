import { h } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { html } from 'htm/preact';

const ACTOR_CLASS = { you: "accent", claude: "warn", codex: "ok" };
const ACTOR_COLOR = { you: "var(--accent)", claude: "var(--warn)", codex: "var(--profit)" };

function fmtDate(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function fmtAge(days) {
  if (days == null) return "-";
  if (days === 0) return "today";
  return `${days}d`;
}

function chipClass(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("done")) return "ok";
  if (text.includes("blocked") || text.includes("stale")) return "bad";
  if (text.includes("waiting")) return "warn";
  return "accent";
}

function TimelineItem({ item }) {
  const docs = item.docs || [];
  return html`
    <div style=${{ display: "grid", gridTemplateColumns: "18px minmax(0, 1fr)", gap: 12 }}>
      <div style=${{ display: "grid", justifyItems: "center" }}>
        <span style=${{
          width: 10,
          height: 10,
          borderRadius: 999,
          marginTop: 4,
          background: ACTOR_COLOR[item.actor] || "var(--text-subtle)",
        }}></span>
        <span style=${{ width: 1, minHeight: 54, background: "var(--border)", marginTop: 4 }}></span>
      </div>
      <div style=${{ minWidth: 0, paddingBottom: 12 }}>
        <div class="between" style=${{ alignItems: "flex-start" }}>
          <div style=${{ minWidth: 0 }}>
            <div style=${{ fontWeight: 600, overflowWrap: "anywhere" }}>${item.subject || "(no subject)"}</div>
            <div class="mono" style=${{ color: "var(--text-subtle)", fontSize: 11, marginTop: 3, overflowWrap: "anywhere" }}>
              ${item.sha} · ${item.branch || "branch?"} · ${fmtDate(item.date)}
            </div>
          </div>
          <span class=${`chip ${ACTOR_CLASS[item.actor] || ""}`}>${item.actor}</span>
        </div>
        ${docs.length ? html`
          <div class="row wrap" style=${{ gap: 6, marginTop: 8 }}>
            ${docs.slice(0, 6).map((doc) => html`<span key=${doc} class="chip" style=${{ textTransform: "none", overflowWrap: "anywhere" }}>${doc}</span>`)}
            ${docs.length > 6 && html`<span class="chip">+${docs.length - 6}</span>`}
          </div>
        ` : null}
      </div>
    </div>
  `;
}

function BranchCard({ branch }) {
  const total = branch.tasks_total;
  const done = branch.tasks_done || 0;
  const pct = total ? Math.round((done / total) * 100) : 0;
  return html`
    <div class="card">
      <div class="card-h">
        <div style=${{ minWidth: 0 }}>
          <div class="card-title" style=${{ overflowWrap: "anywhere" }}>${branch.branch}</div>
          <div class="card-sub">${fmtAge(branch.age_days)} · ahead ${branch.ahead ?? "-"} / behind ${branch.behind ?? "-"}</div>
        </div>
        <span class=${`chip ${chipClass(branch.state)}`}>${branch.state || "-"}</span>
      </div>
      <div class="grid" style=${{ gap: 10 }}>
        <div class="between">
          <span class="metric-label">Turn</span>
          <span class="mono" style=${{ fontSize: 12 }}>${branch.whose_turn || "-"}</span>
        </div>
        <div style=${{ color: "var(--text-muted)", fontSize: 12, lineHeight: 1.45, overflowWrap: "anywhere" }}>
          ${branch.next || "-"}
        </div>
        ${total != null && html`
          <div>
            <div class="between" style=${{ marginBottom: 5 }}>
              <span class="metric-label">Tasks</span>
              <span class="mono" style=${{ fontSize: 11 }}>${done}/${total}</span>
            </div>
            <div class="bar"><i style=${{ width: `${pct}%` }}></i></div>
          </div>
        `}
        ${branch.plan && html`
          <a class="mono" href=${"/" + branch.plan} target="_blank" rel="noreferrer" style=${{ color: "var(--accent)", fontSize: 11, overflowWrap: "anywhere" }}>
            ${branch.plan}
          </a>
        `}
        ${branch.git_error && html`<div class="mono" style=${{ color: "var(--text-subtle)", fontSize: 10, overflowWrap: "anywhere" }}>${branch.git_error}</div>`}
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

  if (loadError) {
    return html`<div class="card"><div class="empty">${loadError}</div></div>`;
  }
  if (!payload) {
    return html`<div class="card"><div class="empty">Loading progress...</div></div>`;
  }
  if (payload.error) {
    return html`<div class="card"><div class="empty">${payload.error}</div></div>`;
  }

  const timeline = payload.timeline || [];
  const branches = payload.branches || [];
  const attribution = payload.attribution || {};

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="grid" style=${{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        <div class="kpi">
          <div class="kpi-label">Branch</div>
          <div class="kpi-value" style=${{ fontSize: 18, overflowWrap: "anywhere" }}>${payload.current_branch || "-"}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Timeline</div>
          <div class="kpi-value">${timeline.length}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Branches</div>
          <div class="kpi-value">${branches.length}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Attribution</div>
          <div class="row wrap" style=${{ gap: 6 }}>
            ${["you", "claude", "codex"].map((actor) => html`
              <span key=${actor} class=${`chip ${ACTOR_CLASS[actor]}`}>${actor}: ${attribution[actor] ?? 0}</span>
            `)}
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Timeline</div>
            <div class="card-sub">generated ${fmtDate(payload.generated_at)}</div>
          </div>
        </div>
        <div class="grid" style=${{ gap: 0 }}>
          ${timeline.length
            ? timeline.map((item) => html`<${TimelineItem} key=${item.sha} item=${item} />`)
            : html`<div class="empty">No commits found</div>`}
        </div>
      </div>

      <section>
        <div class="section-h">
          <h2>Branches</h2>
          <div class="section-sub">${branches.length} tracked</div>
        </div>
        <div class="grid" style=${{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
          ${branches.length
            ? branches.map((branch) => html`<${BranchCard} key=${branch.branch} branch=${branch} />`)
            : html`<div class="card"><div class="empty">No branch rows in STATUS.md</div></div>`}
        </div>
      </section>
    </div>
  `;
}

window.ProgressView = ProgressView;
