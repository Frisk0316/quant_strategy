import { h, Fragment } from 'preact';
import { render } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import { html } from 'htm/preact';

const useAppState = useState;
const useAppEffect = useEffect;
const useTweaks = window.useTweaks;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "accentHue": 255,
  "density": "comfortable",
  "equityMode": "area"
}/*EDITMODE-END*/;

function NavGlyph({ kind }) {
  const stroke = "currentColor";
  const common = { fill: "none", stroke, "stroke-width": 1.5, "stroke-linecap": "round", "stroke-linejoin": "round" };
  switch (kind) {
    case "config": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><circle cx="8" cy="8" r="2.5"/><path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8L3.4 3.4"/></svg>`;
    case "overview": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><path d="M2 12l3-4 3 2 5-6"/><circle cx="13" cy="4" r="1.2"/></svg>`;
    case "wf": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><rect x="1.5" y="3" width="4" height="10" rx="1"/><rect x="6.5" y="3" width="4" height="10" rx="1"/><rect x="11.5" y="3" width="3" height="10" rx="1"/></svg>`;
    case "cpcv": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><rect x="1.5" y="1.5" width="4" height="4"/><rect x="6.5" y="1.5" width="4" height="4"/><rect x="1.5" y="6.5" width="4" height="4"/><rect x="6.5" y="6.5" width="4" height="4"/><rect x="11.5" y="6.5" width="3" height="4"/></svg>`;
    case "trades": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><path d="M1.5 4h13M1.5 8h13M1.5 12h13"/></svg>`;
    case "compare": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><path d="M3 13V6M8 13V3M13 13V8"/></svg>`;
    case "validation": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><path d="M2.5 8.5l3 3 8-8"/><path d="M3 3.5h6M3 6h4M3 13h10"/></svg>`;
    case "metrics": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><path d="M3 2.5h10v11H3z"/><path d="M5.5 5h5M5.5 8h5M5.5 11h3"/></svg>`;
    case "risk": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><path d="M8 1.5l6 2.5v4c0 3.5-2.5 6-6 7-3.5-1-6-3.5-6-7v-4l6-2.5z"/></svg>`;
    case "backtest": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><rect x="1.5" y="2" width="13" height="9" rx="1.5"/><path d="M4 13h8M8 11v2"/><path d="M5 6l2 2 4-3"/></svg>`;
    case "manual": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><path d="M3 2.5h7a2 2 0 0 1 2 2v9H5a2 2 0 0 0-2 2z"/><path d="M5 5.5h4M5 8h4"/></svg>`;
    case "progress": return html`<svg class="nav-glyph" viewBox="0 0 16 16" ...${common}><path d="M2.5 12.5h11"/><path d="M4 12V6.5M8 12V3.5M12 12V8"/><circle cx="4" cy="6.5" r="1"/><circle cx="8" cy="3.5" r="1"/><circle cx="12" cy="8" r="1"/></svg>`;
    default: return null;
  }
}

function BacktestNotifications({ notifications, onDismiss, onView }) {
  if (!notifications.length) return null;
  return html`
    <div style=${{ position: "fixed", top: 16, right: 16, zIndex: 1000, display: "flex", flexDirection: "column", gap: 8 }}>
      ${notifications.map((n) => html`
        <div key=${n.job_id} style=${{
          background: "var(--surface)",
          border: `1px solid ${n.status === "error" ? "var(--loss)" : "var(--accent)"}`,
          borderRadius: "var(--radius)",
          padding: "14px 16px",
          minWidth: 280,
          maxWidth: 380,
          boxShadow: "0 4px 20px rgba(0,0,0,0.18)",
        }}>
          <div class="row" style=${{ alignItems: "flex-start", gap: 8 }}>
            <div style=${{ flex: 1 }}>
              <div style=${{ fontWeight: 600, fontSize: 13, color: n.status === "error" ? "var(--loss)" : "var(--text)" }}>
                ${n.status === "error" ? "Backtest failed" : "Backtest complete"}
              </div>
              <div class="mono" style=${{ fontSize: 11, color: "var(--text-subtle)", marginTop: 2 }}>${n.run_id}</div>
              ${n.message && html`<div style=${{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>${n.message}</div>`}
            </div>
            <button class="btn ghost sm" style=${{ padding: "2px 6px", fontSize: 14, lineHeight: 1 }} onClick=${() => onDismiss(n.job_id)}>×</button>
          </div>
          ${n.status === "done" && n.run_id && html`
            <button class="btn primary sm" style=${{ marginTop: 10, width: "100%" }} onClick=${() => onView(n.run_id)}>
              View Result
            </button>
          `}
        </div>
      `)}
    </div>
  `;
}

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [view, setView] = useAppState("backtest");
  const [selectedRunId, setSelectedRunId] = useAppState(null);
  const [allRuns, setAllRuns] = useAppState([]);
  const [mode, setMode] = useAppState("mock");
  const [liveData, setLiveData] = useAppState(null);
  // Notifications for completed/failed background backtests
  const [backtestNotifs, setBacktestNotifs] = useAppState([]);
  const seenJobStates = useAppEffect(() => {}, []); // use ref via closure

  const refreshRuns = () => {
    window.API.fetchRuns()
      .then((runs) => setAllRuns(runs || []))
      .catch(() => {});
  };

  useAppEffect(() => {
    refreshRuns();
  }, []);

  // Poll background jobs so notifications survive page refresh
  useAppEffect(() => {
    const seen = {};
    let iv = null;
    function poll() {
      if (!window.API.fetchBacktestJobs) return;
      window.API.fetchBacktestJobs().then((jobs) => {
        const hasRunning = (jobs || []).some((j) => j.status === "running");
        for (const job of (jobs || [])) {
          const prev = seen[job.job_id];
          if (!prev && job.status === "running") {
            seen[job.job_id] = job.status;
            continue;
          }
          if (prev === "running" && (job.status === "done" || job.status === "error")) {
            seen[job.job_id] = job.status;
            setBacktestNotifs((ns) => {
              if (ns.find((n) => n.job_id === job.job_id)) return ns;
              return [...ns, { job_id: job.job_id, run_id: job.run_id, status: job.status, message: job.message }];
            });
            refreshRuns();
          }
          if (!prev) seen[job.job_id] = job.status;
        }
        // If nothing running, slow down polling; if running, keep 3s
        if (!hasRunning && iv) {
          clearInterval(iv);
          iv = setInterval(poll, 15000);
        } else if (hasRunning && iv) {
          clearInterval(iv);
          iv = setInterval(poll, 3000);
        }
      }).catch(() => {});
    }
    iv = setInterval(poll, 5000);
    poll();
    return () => { if (iv) clearInterval(iv); };
  }, []);

  useAppEffect(() => {
    let ws;
    window.API.fetchStatus()
      .then((status) => {
        if (!status?.running) return;
        setMode("live");
        const wsUrl = `ws://${location.host}/api/ws`;
        ws = new WebSocket(wsUrl);
        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data);
            if (msg.type === "RISK_SNAPSHOT") {
              Object.assign(window.MOCK.risk, msg.payload);
              setLiveData((d) => ({ ...d, risk: msg.payload }));
            } else if (msg.type === "FILL") {
              const trade = { ...msg.payload, ts: msg.payload.ts ?? Date.now() };
              window.MOCK.trades.unshift(trade);
              setLiveData((d) => ({ ...d, fillTs: msg.ts }));
            }
          } catch (_) {}
        };
        ws.onclose = () => setMode("mock");
        setLiveData({ status });
      })
      .catch(() => setMode("mock"));
    return () => { if (ws) ws.close(); };
  }, []);

  useAppEffect(() => {
    document.documentElement.setAttribute("data-theme", tweaks.theme);
    document.documentElement.setAttribute("data-density", tweaks.density);
    document.documentElement.style.setProperty("--accent", `oklch(0.55 0.18 ${tweaks.accentHue})`);
    document.documentElement.style.setProperty("--accent-soft", `oklch(${tweaks.theme === "dark" ? 0.30 : 0.95} ${tweaks.theme === "dark" ? 0.06 : 0.04} ${tweaks.accentHue})`);
  }, [tweaks.theme, tweaks.accentHue, tweaks.density]);

  const NAV = [
    { id: "config", label: "Run Backtest", group: "Setup", glyph: "config" },
    { id: "backtest", label: "Backtest Runs", group: "Backtest", glyph: "backtest" },
    { id: "validation", label: "Validation Lab", group: "Backtest", glyph: "validation" },
    { id: "compare", label: "Compare runs", group: "Analysis", glyph: "compare" },
    { id: "metrics", label: "Metrics Glossary", group: "Analysis", glyph: "metrics" },
    { id: "progress", label: "進度 / Progress", group: "Analysis", glyph: "progress" },
    { id: "risk", label: "Risk Monitor", group: "Live", glyph: "risk" },
    { id: "manual", label: "使用手冊", group: "Help", glyph: "manual" },
  ];
  const groups = [...new Set(NAV.map((n) => n.group))];
  const titleMap = {
    config: ["Run Backtest", "Configure and launch strategy backtest"],
    backtest: ["Backtest Runs", "Real results saved by --save-artifacts"],
    validation: ["Validation Lab", "Strategy-level reference checks"],
    wf: ["Walk-Forward", "Out-of-sample validation windows"],
    cpcv: ["CPCV / DSR", "Combinatorial Purged CV and promotion gates"],
    trades: ["Trades / Orders", "Filterable order and trade ledger"],
    compare: ["Compare Runs", "Aligned equity comparison across saved runs"],
    metrics: ["Metrics Glossary", "Definitions for result metrics and execution counters"],
    progress: ["進度 / Progress", "Git timeline and branch status board"],
    risk: ["Risk Monitor", "Config limits and selected-run gate status"],
    manual: ["使用手冊", "架構、驗證、風控與設定來源"],
  };
  const selectedRunSummary = allRuns.find((r) => r.run_id === selectedRunId);

  const dismissNotif = (jobId) => setBacktestNotifs((ns) => ns.filter((n) => n.job_id !== jobId));
  const viewResult = (runId) => {
    setSelectedRunId(runId);
    setView("backtest");
    dismissNotif(backtestNotifs.find((n) => n.run_id === runId)?.job_id);
  };

  return html`
    <${BacktestNotifications}
      notifications=${backtestNotifs}
      onDismiss=${dismissNotif}
      onView=${viewResult}
    />
    <div class="app">
      <aside class="app-side">
        <div class="brand">
          <div class="brand-mark">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"
                 stroke-linecap="round" style=${{ width: 22, height: 22 }}>
              <polyline points="2,16 6,10 10,13 14,6 18,4" />
              <circle cx="18" cy="4" r="1.5" fill="currentColor" stroke="none" />
            </svg>
          </div>
          <div>
            <div class="brand-name">Quant Backtester</div>
          </div>
        </div>

        ${groups.map((g) => html`
          <div key=${g}>
            <div class="nav-section">${g}</div>
            ${NAV.filter((n) => n.group === g).map((n) => html`
              <div
                key=${n.id}
                class="nav-item"
                aria-current=${view === n.id ? "page" : undefined}
                onClick=${() => setView(n.id)}
              >
                <${NavGlyph} kind=${n.glyph} />
                <span>${n.label}</span>
              </div>
            `)}
          </div>
        `)}

        <div style=${{ flex: 1 }}></div>

        <div style=${{ padding: "10px 12px", color: "var(--text-subtle)", fontSize: 11, lineHeight: 1.6, borderTop: "1px solid var(--border)" }}>
          ${selectedRunId ? html`
            <${Fragment}>
              <div class="mono" style=${{ color: "var(--text-muted)", marginBottom: 2 }}>
                ${selectedRunId.slice(0, 32)}
              </div>
              <div>Return: <span class="mono">${selectedRunSummary?.total_return != null
                ? ((+selectedRunSummary.total_return) * 100).toFixed(2) + "%" : "-"}</span></div>
              <div>Sharpe: <span class="mono">${selectedRunSummary?.sharpe != null
                ? (+selectedRunSummary.sharpe).toFixed(2) : "-"}</span></div>
            <//>
          ` : html`<div style=${{ color: "var(--text-subtle)" }}>No run selected</div>`}
        </div>
      </aside>

      <header class="app-header">
        <div>
          <div class="h-title">${titleMap[view][0]}</div>
          <div class="h-sub">${titleMap[view][1]}</div>
        </div>
        <div class="h-spacer"></div>
        <button class="btn ghost sm" onClick=${() => setTweak("theme", tweaks.theme === "dark" ? "light" : "dark")}>
          ${tweaks.theme === "dark" ? "Light" : "Dark"}
        </button>
      </header>

      <main class="app-main">
        ${view === "config" && html`<${window.RunConfigView} tweaks=${tweaks} setTweak=${setTweak} setView=${setView} setSelectedRunId=${setSelectedRunId} />`}
        ${view === "backtest" && html`<${window.BacktestView} selectedRunId=${selectedRunId} setSelectedRunId=${setSelectedRunId} onRunsChanged=${refreshRuns} />`}
        ${view === "validation" && html`<${window.ValidationLabView} selectedRunId=${selectedRunId} setSelectedRunId=${setSelectedRunId} />`}
        ${view === "wf" && html`<${window.WalkForwardView} selectedRunId=${selectedRunId} />`}
        ${view === "cpcv" && html`<${window.CPCVView} selectedRunId=${selectedRunId} />`}
        ${view === "trades" && html`<${window.TradesView} selectedRunId=${selectedRunId} />`}
        ${view === "compare" && html`<${window.CompareView} selectedRunId=${selectedRunId} />`}
        ${view === "metrics" && html`<${window.MetricsGlossaryView} />`}
        ${view === "progress" && html`<${window.ProgressView} />`}
        ${view === "risk" && html`<${window.RiskView} selectedRunId=${selectedRunId} />`}
        ${view === "manual" && html`<${window.ManualView} />`}
      </main>

      <${window.TweaksPanel} title="Tweaks">
        <${window.TweakSection} title="Theme">
          <${window.TweakRadio} label="Theme" value=${tweaks.theme} onChange=${(v) => setTweak("theme", v)} options=${[{value:"light",label:"Light"},{value:"dark",label:"Dark"}]} />
          <${window.TweakRadio} label="Density" value=${tweaks.density} onChange=${(v) => setTweak("density", v)} options=${[{value:"comfortable",label:"Comfortable"},{value:"compact",label:"Compact"}]} />
        <//>
        <${window.TweakSection} title="Accent color">
          <${window.TweakSlider} label="Hue" value=${tweaks.accentHue} onChange=${(v) => setTweak("accentHue", v)} min=${0} max=${360} step=${5} formatValue=${(v) => `${v}deg`} />
          <div class="row wrap" style=${{ gap: 6, marginTop: 4 }}>
            ${[
              ["Cobalt", 255], ["Indigo", 280], ["Teal", 195],
              ["Forest", 150], ["Rose", 15], ["Amber", 70],
            ].map(([name, hue]) => html`
              <button key=${hue} class="btn sm" onClick=${() => setTweak("accentHue", hue)} style=${{ padding: "3px 8px", fontSize: 11, borderColor: tweaks.accentHue === hue ? "var(--accent)" : undefined }}>
                <span style=${{ width: 8, height: 8, borderRadius: 999, background: `oklch(0.55 0.18 ${hue})`, display: "inline-block", marginRight: 6 }}></span>
                ${name}
              </button>
            `)}
          </div>
        <//>
        <${window.TweakSection} title="Equity curve">
          <${window.TweakRadio} label="Style" value=${tweaks.equityMode} onChange=${(v) => setTweak("equityMode", v)} options=${[{value:"line",label:"Line"},{value:"area",label:"Area"},{value:"step",label:"Step"}]} />
        <//>
      <//>
    </div>
  `;
}

render(html`<${App} />`, document.getElementById("root"));
