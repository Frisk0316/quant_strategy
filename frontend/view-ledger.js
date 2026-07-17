import { Fragment, h } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { html } from 'htm/preact';

const EMPTY_COMMAND = "python scripts/run_pipeline_funnel_report.py --json-output frontend/research_funnel.json";
const display = (value) => value == null ? "—" : String(value);
const progressFileUrl = (path, text) => `/api/progress/file?path=${path}#:~:text=${encodeURIComponent(text)}`;

function RowLinks({ row, enabled }) {
  if (!enabled) {
    return html`<div class="row wrap" style=${{ gap: 6 }}><span class="chip">Ledger</span><span class="chip">Registry</span><span class="chip">History</span></div>`;
  }
  return html`
    <div class="row wrap" style=${{ gap: 6 }}>
      <a class="chip" href=${progressFileUrl("docs/HYPOTHESIS_LEDGER.md", row.hypothesis_id)} target="_blank" rel="noreferrer">Ledger</a>
      <a class="chip" href=${progressFileUrl("docs/EXPERIMENT_REGISTRY.md", row.family_id)} target="_blank" rel="noreferrer">Registry</a>
      <a class="chip" href=${progressFileUrl("docs/STRATEGY_HISTORY.md", row.hypothesis_id)} target="_blank" rel="noreferrer">History</a>
    </div>
  `;
}

function IterationDetail({ row, schemaVersion }) {
  const experiments = Array.isArray(row.experiments) ? row.experiments : [];
  return html`
    <tr>
      <td colSpan="15" style=${{ height: "auto", paddingTop: 0, whiteSpace: "normal" }}>
        <details>
          <summary class="card-sub" style=${{ cursor: "pointer", padding: "4px 0" }}>Iteration details</summary>
          ${schemaVersion >= 2 ? html`
            <div class="scope-note" style=${{ marginTop: 8, maxWidth: "calc(100vw - 320px)", overflowWrap: "anywhere" }}>
              <div><strong>Ideation source:</strong> ${display(row.source)}</div>
              <div><strong>Hypothesis / logic:</strong> ${display(row.hypothesis_text)}</div>
              <div><strong>Experiment timeline:</strong></div>
              ${experiments.length ? experiments.map((experiment) => html`
                <div key=${experiment.id} style=${{ borderLeft: "2px solid var(--border-strong)", paddingLeft: 10 }}>
                  <div class="row wrap" style=${{ alignItems: "center", gap: 6 }}>
                    <span class="chip">${display(experiment.id)}</span>
                    <span class="mono">${display(experiment.date)}</span>
                  </div>
                  <div><strong>Setup:</strong> ${display(experiment.setup)}</div>
                  <div><strong>Outcome:</strong> ${display(experiment.outcome)}</div>
                  <div><strong>Notes:</strong> ${display(experiment.notes)}</div>
                </div>
              `) : html`<div class="empty" style=${{ padding: 8 }}>No experiments recorded for this family.</div>`}
            </div>
          ` : html`
            <div class="empty" style=${{ padding: 12 }}>
              Regenerate with schema v2 to view source, logic, and experiment history.<br />
              <code class="mono">${EMPTY_COMMAND}</code>
            </div>
          `}
        </details>
      </td>
    </tr>
  `;
}

function LedgerView() {
  const [funnel, setFunnel] = useState(null);
  const [funnelMissing, setFunnelMissing] = useState(false);
  const [progress, setProgress] = useState(null);

  useEffect(() => {
    let alive = true;
    window.API.fetchResearchFunnel()
      .then((data) => { if (alive) setFunnel(data); })
      .catch(() => { if (alive) setFunnelMissing(true); });
    window.API.fetchProgress()
      .then((data) => { if (alive) setProgress(data); })
      .catch(() => { if (alive) setProgress({ file_links_enabled: false }); });
    return () => { alive = false; };
  }, []);

  if (funnelMissing) {
    return html`
      <div class="card">
        <div class="card-title">Research funnel unavailable</div>
        <div class="empty">
          Generate the read-only projection with<br />
          <code class="mono">${EMPTY_COMMAND}</code>
        </div>
      </div>
    `;
  }
  if (!funnel) return html`<div class="card"><div class="empty">Loading research funnel...</div></div>`;

  const rows = Array.isArray(funnel.families) ? funnel.families : [];
  const totals = funnel.totals || {};
  const linksEnabled = progress?.file_links_enabled === true;
  const schemaVersion = Number(funnel.schema_version) || 1;

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="grid" style=${{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }}>
        <div class="kpi"><div class="kpi-label">Families</div><div class="kpi-value">${rows.length}</div></div>
        <div class="kpi"><div class="kpi-label">Candidates</div><div class="kpi-value">${display(totals.candidates)}</div></div>
        <div class="kpi"><div class="kpi-label">Data feasible</div><div class="kpi-value">${display(totals.data_feasible)}</div></div>
        <div class="kpi"><div class="kpi-label">Power feasible</div><div class="kpi-value">${display(totals.power_feasible)}</div></div>
        <div class="kpi"><div class="kpi-label">Stage-3 runs</div><div class="kpi-value">${display(totals.stage3_run)}</div></div>
        <div class="kpi"><div class="kpi-label">Gate passes</div><div class="kpi-value">${display(totals.gate_pass)}</div></div>
        <div class="kpi"><div class="kpi-label">K spent</div><div class="kpi-value">${display(totals.k_spent)}</div></div>
      </div>

      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Research families</div>
            <div class="card-sub">Read-only projection; markdown ledgers remain authoritative.</div>
          </div>
        </div>
        ${rows.length ? html`
          <div class="tbl-wrap">
            <table class="tbl">
              <thead><tr>
                <th>Family</th><th>Hypothesis</th><th>Status</th>
                <th class="num">WF</th><th class="num">CPCV</th><th class="num">DSR</th><th class="num">PSR</th>
                <th class="num">Trials</th><th class="num">K used / limit</th>
                <th class="num">Candidates</th><th class="num">Data</th><th class="num">Power</th>
                <th class="num">Stage-3</th><th class="num">Gate</th><th>Docs</th>
              </tr></thead>
              <tbody>
                ${rows.map((row) => html`
                  <${Fragment} key=${`${row.family_id}:${row.hypothesis_id}`}>
                    <tr>
                      <td class="mono">${display(row.family_id)}</td>
                      <td class="mono">${display(row.hypothesis_id)}</td>
                      <td><span class="chip">${display(row.status)}</span></td>
                      <td class="num mono">${display(row.wf)}</td>
                      <td class="num mono">${display(row.cpcv)}</td>
                      <td class="num mono">${display(row.dsr)}</td>
                      <td class="num mono">${display(row.psr)}</td>
                      <td class="num mono">${display(row.n_trials)}</td>
                      <td class="num mono">${display(row.k_used)} / ${display(row.k_limit)}</td>
                      <td class="num mono">${display(row.candidates)}</td>
                      <td class="num mono">${display(row.data_feasible)}</td>
                      <td class="num mono">${display(row.power_feasible)}</td>
                      <td class="num mono">${display(row.stage3_run)}</td>
                      <td class="num mono">${display(row.gate_pass)}</td>
                      <td><${RowLinks} row=${row} enabled=${linksEnabled} /></td>
                    </tr>
                    <${IterationDetail} row=${row} schemaVersion=${schemaVersion} />
                  <//>
                `)}
              </tbody>
            </table>
          </div>
        ` : html`<div class="empty">No research families in the funnel report.</div>`}
      </div>
    </div>
  `;
}

window.LedgerView = LedgerView;
