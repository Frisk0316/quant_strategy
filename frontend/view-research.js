import { h } from "preact";
import { useEffect, useState } from "preact/hooks";
import { html } from "htm/preact";

const fmt = (value, digits = 3) => value == null || !Number.isFinite(Number(value))
  ? "—"
  : Number(value).toFixed(digits);
const pct = (value) => value == null || !Number.isFinite(Number(value))
  ? "—"
  : `${(Number(value) * 100).toFixed(2)}%`;

function parseList(text, parser, label) {
  const values = String(text).split(",").map((part) => parser(part.trim())).filter(Number.isFinite);
  if (!values.length) throw new Error(`${label} 至少需要一個數值`);
  return values;
}

function ResearchOpsView() {
  const [h014, setH014] = useState(null);
  const [h014Busy, setH014Busy] = useState(false);
  const [h014Error, setH014Error] = useState("");
  const [lookbacks, setLookbacks] = useState("7, 14");
  const [quantiles, setQuantiles] = useState("0.20, 0.30");
  const [h009Job, setH009Job] = useState(null);
  const [h009Error, setH009Error] = useState("");

  const refreshH014 = () => window.API.fetchH014Research()
    .then(setH014)
    .catch((error) => setH014Error(error.message || "H-014 狀態讀取失敗"));

  useEffect(() => {
    refreshH014();
    window.API.fetchH009ResearchJobs()
      .then((jobs) => { if (jobs?.length) setH009Job(jobs[0]); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!h009Job?.job_id || ["done", "error"].includes(h009Job.status)) return undefined;
    const timer = setInterval(() => {
      window.API.fetchH009ResearchSweep(h009Job.job_id)
        .then(setH009Job)
        .catch((error) => setH009Error(error.message || "H-009 job 狀態讀取失敗"));
    }, 1500);
    return () => clearInterval(timer);
  }, [h009Job?.job_id, h009Job?.status]);

  async function runH014() {
    setH014Busy(true);
    setH014Error("");
    try {
      const result = await window.API.runH014Research();
      setH014((current) => ({ ...current, report: result.report, last_run: result }));
    } catch (error) {
      setH014Error(error.message || "H-014 shadow cycle 失敗");
    } finally {
      setH014Busy(false);
    }
  }

  async function runH009() {
    setH009Error("");
    try {
      const payload = {
        lookback_days: parseList(lookbacks, Number, "lookback_days"),
        quantiles: parseList(quantiles, Number.parseFloat, "quantile"),
      };
      setH009Job(await window.API.runH009ResearchSweep(payload));
    } catch (error) {
      setH009Error(error.message || "H-009 parameter screen 失敗");
    }
  }

  const criteria = h014?.report?.exit_criteria || {};
  const h009Running = ["queued", "running"].includes(h009Job?.status);
  const rows = h009Job?.top_results || [];

  return html`
    <div class="stack" style=${{ gap: 16 }}>
      <div class="callout warning">
        <strong>Research / shadow only.</strong> 本頁不會切換 live mode；H-014 不具下單能力，H-009 sweep 也不能作為 promotion evidence。
      </div>

      <div class="grid cols-2" style=${{ alignItems: "start" }}>
        <section class="card">
          <div class="card-title">H-014 · Deribit options shadow</div>
          <div class="muted" style=${{ marginTop: 6 }}>使用公開行情手動跑一個 daily cycle；不讀交易憑證、不送訂單。</div>
          <div class="grid cols-2" style=${{ marginTop: 14 }}>
            <div><div class="muted">Journal weeks</div><div class="mono">${fmt(criteria.journal_weeks, 2)} / 8</div></div>
            <div><div class="muted">Distinct weeks</div><div class="mono">${criteria.distinct_journal_weeks ?? "—"} / 8</div></div>
            <div><div class="muted">Bias metrics</div><div>${criteria.bias_metrics_complete ? "Complete" : "Incomplete"}</div></div>
            <div><div class="muted">Live ADR discussion</div><div>${criteria.live_adr_discussion_unlocked ? "Unlocked" : "Locked"}</div></div>
          </div>
          ${h014?.last_run && html`<div class="callout" style=${{ marginTop: 12 }}>Last cycle: ${h014.last_run.intents?.map((row) => `${row.currency} ${row.status}`).join(" · ") || "no intents"}</div>`}
          ${h014Error && html`<div class="callout danger" style=${{ marginTop: 12 }}>${h014Error}</div>`}
          <div class="row" style=${{ marginTop: 14, gap: 8 }}>
            <button class="btn primary" disabled=${h014Busy || !h014?.actions_enabled} onClick=${runH014}>
              ${h014Busy ? "Running…" : "Run one shadow cycle"}
            </button>
            <button class="btn" disabled=${h014Busy} onClick=${refreshH014}>Refresh report</button>
          </div>
          ${h014 && !h014.actions_enabled && html`<div class="muted" style=${{ marginTop: 10 }}>操作只在 loopback standalone server 開放：<span class="mono">python scripts/run_server.py</span></div>`}
        </section>

        <section class="card">
          <div class="card-title">H-009 · Funding XS parameter screen</div>
          <div class="muted" style=${{ marginTop: 6 }}>只開放既有 lookback / quantile 維度；完整樣本 sensitivity，不是 WF/CPCV。</div>
          <div class="grid cols-2" style=${{ marginTop: 14 }}>
            <label>
              <div class="muted">Lookback days</div>
              <input value=${lookbacks} onInput=${(event) => setLookbacks(event.currentTarget.value)} placeholder="7, 14" />
            </label>
            <label>
              <div class="muted">Quantiles</div>
              <input value=${quantiles} onInput=${(event) => setQuantiles(event.currentTarget.value)} placeholder="0.20, 0.30" />
            </label>
          </div>
          <button class="btn primary" style=${{ marginTop: 14 }} disabled=${h009Running || h014?.actions_enabled === false} onClick=${runH009}>
            ${h009Running ? "Screening…" : "Run research screen"}
          </button>
          ${h009Job && html`
            <div class="callout" aria-live="polite" style=${{ marginTop: 12 }}>
              <span class="mono">${h009Job.status}</span> · ${h009Job.message}
              ${h009Job.known_family_n_trials_lower_bound != null && html` · known n_trials≥${h009Job.known_family_n_trials_lower_bound}`}
            </div>
          `}
          ${h009Error && html`<div class="callout danger" style=${{ marginTop: 12 }}>${h009Error}</div>`}
        </section>
      </div>

      ${rows.length > 0 && html`
        <section class="card">
          <div class="card-title">H-009 screen results</div>
          <div class="muted" style=${{ marginTop: 6 }}>排名只供研究導覽；任何決策使用前都要登錄 experiment，並保留累計 trial penalty。</div>
          <div class="table-wrap" style=${{ marginTop: 12 }}>
            <table>
              <thead><tr><th>Rank</th><th>Lookback</th><th>Quantile</th><th>Sharpe</th><th>Return</th><th>Max DD</th></tr></thead>
              <tbody>${rows.map((row) => html`
                <tr key=${row.rank}>
                  <td>${row.rank}</td><td>${row.lookback_days}</td><td>${fmt(row.quantile, 2)}</td>
                  <td>${fmt(row.sharpe)}</td><td>${pct(row.total_return)}</td><td>${pct(row.max_drawdown)}</td>
                </tr>
              `)}</tbody>
            </table>
          </div>
        </section>
      `}
    </div>
  `;
}

window.ResearchOpsView = ResearchOpsView;
