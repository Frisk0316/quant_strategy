/* global React, MOCK, RunConfigView, OverviewView, WalkForwardView, CPCVView, TradesView, CompareView, RiskView, BacktestView, useTweaks */
const { useState: useAppState, useEffect: useAppEffect } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "accentHue": 255,
  "density": "comfortable",
  "equityMode": "area"
}/*EDITMODE-END*/;

function NavGlyph({ kind }) {
  const stroke = "currentColor";
  const common = { fill: "none", stroke, strokeWidth: 1.5, strokeLinecap: "round", strokeLinejoin: "round" };
  switch (kind) {
    case "config": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><circle cx="8" cy="8" r="2.5"/><path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8L3.4 3.4"/></svg>;
    case "overview": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><path d="M2 12l3-4 3 2 5-6"/><circle cx="13" cy="4" r="1.2"/></svg>;
    case "wf": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><rect x="1.5" y="3" width="4" height="10" rx="1"/><rect x="6.5" y="3" width="4" height="10" rx="1"/><rect x="11.5" y="3" width="3" height="10" rx="1"/></svg>;
    case "cpcv": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><rect x="1.5" y="1.5" width="4" height="4"/><rect x="6.5" y="1.5" width="4" height="4"/><rect x="1.5" y="6.5" width="4" height="4"/><rect x="6.5" y="6.5" width="4" height="4"/><rect x="11.5" y="6.5" width="3" height="4"/></svg>;
    case "trades": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><path d="M1.5 4h13M1.5 8h13M1.5 12h13"/></svg>;
    case "compare": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><path d="M3 13V6M8 13V3M13 13V8"/></svg>;
    case "risk": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><path d="M8 1.5l6 2.5v4c0 3.5-2.5 6-6 7-3.5-1-6-3.5-6-7v-4l6-2.5z"/></svg>;
    case "backtest": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><rect x="1.5" y="2" width="13" height="9" rx="1.5"/><path d="M4 13h8M8 11v2"/><path d="M5 6l2 2 4-3"/></svg>;
    default: return null;
  }
}

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [view, setView] = useAppState("overview");
  const [selectedRunId, setSelectedRunId] = useAppState(
    () => localStorage.getItem("selectedRunId") || null
  );
  const [allRuns, setAllRuns] = useAppState([]);
  const [mode, setMode] = useAppState("mock");
  const [liveData, setLiveData] = useAppState(null);

  const refreshRuns = () => {
    window.API.fetchRuns()
      .then((runs) => setAllRuns(runs || []))
      .catch(() => {});
  };

  useAppEffect(() => {
    refreshRuns();
  }, []);

  useAppEffect(() => {
    if (selectedRunId) localStorage.setItem("selectedRunId", selectedRunId);
  }, [selectedRunId]);

  useAppEffect(() => {
    let ws;
    window.API.fetchStatus()
      .then((status) => {
        if (status?.running) setMode("live");
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
    { id: "overview", label: "Overview", group: "Backtest", glyph: "overview" },
    { id: "wf", label: "Walk-Forward", group: "Backtest", glyph: "wf" },
    { id: "cpcv", label: "CPCV / DSR", group: "Backtest", glyph: "cpcv" },
    { id: "trades", label: "Trades / Orders", group: "Backtest", glyph: "trades" },
    { id: "compare", label: "Compare runs", group: "Analysis", glyph: "compare" },
    { id: "risk", label: "Risk Monitor", group: "Live", glyph: "risk" },
  ];
  const groups = [...new Set(NAV.map((n) => n.group))];
  const titleMap = {
    config: ["Run Backtest", "Configure and launch strategy backtest"],
    backtest: ["Backtest Runs", "Real results saved by --save-artifacts"],
    overview: ["Overview", "Equity, drawdown, and headline KPIs"],
    wf: ["Walk-Forward", "Out-of-sample validation windows"],
    cpcv: ["CPCV / DSR", "Combinatorial Purged CV and promotion gates"],
    trades: ["Trades / Orders", "Filterable order and trade ledger"],
    compare: ["Compare Runs", "Aligned equity comparison across saved runs"],
    risk: ["Risk Monitor", "Config limits and selected-run gate status"],
  };
  const selectedRunSummary = allRuns.find((r) => r.run_id === selectedRunId);

  return (
    <div className="app">
      <aside className="app-side">
        <div className="brand">
          <div className="brand-mark">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"
                 strokeLinecap="round" style={{ width: 22, height: 22 }}>
              <polyline points="2,16 6,10 10,13 14,6 18,4" />
              <circle cx="18" cy="4" r="1.5" fill="currentColor" stroke="none" />
            </svg>
          </div>
          <div>
            <div className="brand-name">Quant Backtester</div>
          </div>
        </div>

        {groups.map((g) => (
          <div key={g}>
            <div className="nav-section">{g}</div>
            {NAV.filter((n) => n.group === g).map((n) => (
              <div
                key={n.id}
                className="nav-item"
                aria-current={view === n.id ? "page" : undefined}
                onClick={() => setView(n.id)}
              >
                <NavGlyph kind={n.glyph} />
                <span>{n.label}</span>
              </div>
            ))}
          </div>
        ))}

        <div style={{ flex: 1 }}></div>

        <div style={{ padding: "10px 12px", color: "var(--text-subtle)", fontSize: 11, lineHeight: 1.6, borderTop: "1px solid var(--border)" }}>
          {selectedRunId ? (
            <>
              <div className="mono" style={{ color: "var(--text-muted)", marginBottom: 2 }}>
                {selectedRunId.slice(0, 32)}
              </div>
              <div>Return: <span className="mono">{selectedRunSummary?.total_return != null
                ? ((+selectedRunSummary.total_return) * 100).toFixed(2) + "%" : "-"}</span></div>
              <div>Sharpe: <span className="mono">{selectedRunSummary?.sharpe != null
                ? (+selectedRunSummary.sharpe).toFixed(2) : "-"}</span></div>
            </>
          ) : (
            <div style={{ color: "var(--text-subtle)" }}>No run selected</div>
          )}
        </div>
      </aside>

      <header className="app-header">
        <div>
          <div className="h-title">{titleMap[view][0]}</div>
          <div className="h-sub">{titleMap[view][1]}</div>
        </div>
        <div className="h-spacer"></div>
        <button className="btn ghost sm" onClick={() => setTweak("theme", tweaks.theme === "dark" ? "light" : "dark")}>
          {tweaks.theme === "dark" ? "Light" : "Dark"}
        </button>
      </header>

      <main className="app-main">
        {view === "config" && <RunConfigView tweaks={tweaks} setTweak={setTweak} />}
        {view === "backtest" && <BacktestView selectedRunId={selectedRunId} setSelectedRunId={setSelectedRunId} onRunsChanged={refreshRuns} />}
        {view === "overview" && <OverviewView tweaks={tweaks} selectedRunId={selectedRunId} />}
        {view === "wf" && <WalkForwardView selectedRunId={selectedRunId} />}
        {view === "cpcv" && <CPCVView selectedRunId={selectedRunId} />}
        {view === "trades" && <TradesView selectedRunId={selectedRunId} />}
        {view === "compare" && <CompareView selectedRunId={selectedRunId} />}
        {view === "risk" && <RiskView selectedRunId={selectedRunId} />}
      </main>

      <window.TweaksPanel title="Tweaks">
        <window.TweakSection title="Theme">
          <window.TweakRadio label="Theme" value={tweaks.theme} onChange={(v) => setTweak("theme", v)} options={[{value:"light",label:"Light"},{value:"dark",label:"Dark"}]} />
          <window.TweakRadio label="Density" value={tweaks.density} onChange={(v) => setTweak("density", v)} options={[{value:"comfortable",label:"Comfortable"},{value:"compact",label:"Compact"}]} />
        </window.TweakSection>
        <window.TweakSection title="Accent color">
          <window.TweakSlider label="Hue" value={tweaks.accentHue} onChange={(v) => setTweak("accentHue", v)} min={0} max={360} step={5} formatValue={(v) => `${v}deg`} />
          <div className="row wrap" style={{ gap: 6, marginTop: 4 }}>
            {[
              ["Cobalt", 255], ["Indigo", 280], ["Teal", 195],
              ["Forest", 150], ["Rose", 15], ["Amber", 70],
            ].map(([name, h]) => (
              <button key={h} className="btn sm" onClick={() => setTweak("accentHue", h)} style={{ padding: "3px 8px", fontSize: 11, borderColor: tweaks.accentHue === h ? "var(--accent)" : undefined }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: `oklch(0.55 0.18 ${h})`, display: "inline-block", marginRight: 6 }}></span>
                {name}
              </button>
            ))}
          </div>
        </window.TweakSection>
        <window.TweakSection title="Equity curve">
          <window.TweakRadio label="Style" value={tweaks.equityMode} onChange={(v) => setTweak("equityMode", v)} options={[{value:"line",label:"Line"},{value:"area",label:"Area"},{value:"step",label:"Step"}]} />
        </window.TweakSection>
      </window.TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
