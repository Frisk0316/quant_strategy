/* global React, MOCK, RunConfigView, OverviewView, WalkForwardView, CPCVView, TradesView, CompareView, RiskView, useTweaks */
const { useState, useEffect } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "accentHue": 255,
  "density": "comfortable",
  "equityMode": "area"
}/*EDITMODE-END*/;

function NavGlyph({ kind }) {
  const stroke = "currentColor";
  const sw = 1.5;
  const common = { fill: "none", stroke, strokeWidth: sw, strokeLinecap: "round", strokeLinejoin: "round" };
  switch (kind) {
    case "config": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><circle cx="8" cy="8" r="2.5"/><path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8L3.4 3.4"/></svg>;
    case "overview": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><path d="M2 12l3-4 3 2 5-6"/><circle cx="13" cy="4" r="1.2"/></svg>;
    case "wf": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><rect x="1.5" y="3" width="4" height="10" rx="1"/><rect x="6.5" y="3" width="4" height="10" rx="1"/><rect x="11.5" y="3" width="3" height="10" rx="1"/></svg>;
    case "cpcv": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><rect x="1.5" y="1.5" width="4" height="4"/><rect x="6.5" y="1.5" width="4" height="4"/><rect x="1.5" y="6.5" width="4" height="4"/><rect x="6.5" y="6.5" width="4" height="4"/><rect x="11.5" y="6.5" width="3" height="4"/></svg>;
    case "trades": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><path d="M1.5 4h13M1.5 8h13M1.5 12h13"/></svg>;
    case "compare": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><path d="M3 13V6M8 13V3M13 13V8"/></svg>;
    case "risk": return <svg className="nav-glyph" viewBox="0 0 16 16" {...common}><path d="M8 1.5l6 2.5v4c0 3.5-2.5 6-6 7-3.5-1-6-3.5-6-7v-4l6-2.5z"/></svg>;
    default: return null;
  }
}

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [view, setView] = useState("overview");
  // "mock" = no server / backtest-only, "live" = engine is running
  const [mode, setMode] = useState("mock");
  const [liveData, setLiveData] = useState(null);

  useEffect(() => {
    let ws;
    window.API.fetchStatus()
      .then((status) => {
        setMode("live");
        const wsUrl = `ws://${location.host}/api/ws`;
        ws = new WebSocket(wsUrl);
        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data);
            if (msg.type === "RISK_SNAPSHOT") {
              // Mutate MOCK.risk in place so RiskView reads live values on re-render
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
        // Reflect live mode/equity in sidebar
        setLiveData({ status });
      })
      .catch(() => setMode("mock"));
    return () => { if (ws) ws.close(); };
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", tweaks.theme);
    document.documentElement.setAttribute("data-density", tweaks.density);
    document.documentElement.style.setProperty("--accent", `oklch(0.55 0.18 ${tweaks.accentHue})`);
    document.documentElement.style.setProperty("--accent-soft", `oklch(${tweaks.theme === "dark" ? 0.30 : 0.95} ${tweaks.theme === "dark" ? 0.06 : 0.04} ${tweaks.accentHue})`);
  }, [tweaks.theme, tweaks.accentHue, tweaks.density]);

  const NAV = [
    { id: "config", label: "Run Config", group: "Setup", glyph: "config" },
    { id: "overview", label: "Overview", group: "Results", glyph: "overview" },
    { id: "wf", label: "Walk-Forward", group: "Results", glyph: "wf" },
    { id: "cpcv", label: "CPCV / DSR", group: "Results", glyph: "cpcv" },
    { id: "trades", label: "Trades / Orders", group: "Results", glyph: "trades" },
    { id: "compare", label: "Compare runs", group: "Analysis", glyph: "compare" },
    { id: "risk", label: "Risk Monitor", group: "Live", glyph: "risk" },
  ];

  const groups = [...new Set(NAV.map((n) => n.group))];

  const titleMap = {
    config: ["回測設定", "Configure strategy, symbol, data source · post_only · maker-only"],
    overview: ["結果總覽", "Equity, drawdown, headline KPIs"],
    wf: ["Walk-Forward 驗證", "IS=14d / OOS=7d · non-overlapping windows"],
    cpcv: ["CPCV 驗證", "Combinatorial Purged CV · N=6, k=2, embargo=2%"],
    trades: ["成交紀錄", "Filterable order/trade ledger"],
    compare: ["策略對比", "Side-by-side runs"],
    risk: ["風險監控", "config/risk.yaml · live limits"],
  };

  return (
    <div className="app">
      <aside className="app-side">
        <div className="brand">
          <div className="brand-mark">QX</div>
          <div>
            <div className="brand-name">OKX Quant</div>
            <div className="brand-sub">backtester · v1</div>
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

        <div style={{ padding: "10px", color: "var(--text-subtle)", fontSize: 11, lineHeight: 1.5 }}>
          <div className="mono">equity_usd: {Math.round(liveData?.risk?.equity_usd ?? MOCK.risk.equity_usd).toLocaleString()}</div>
          <div className="mono">mode: {mode === "live" ? (liveData?.status?.mode ?? "live") : "demo"}</div>
          <div className="mono">DSR ≥ 0.95 to promote</div>
        </div>
      </aside>

      <header className="app-header">
        <div>
          <div className="h-title">{titleMap[view][0]}</div>
          <div className="h-sub">{titleMap[view][1]}</div>
        </div>
        <div className="h-spacer"></div>
        <span className="badge">
          <span className="mono">funding_carry</span>
        </span>
        <span className="badge">
          <span className="mono">BTC-USDT-SWAP · 1H</span>
        </span>
        {mode === "live"
          ? <span className="badge live"><span className="dot pulse"></span>LIVE</span>
          : <span className="badge demo"><span className="dot"></span>DEMO</span>
        }
        <button className="btn ghost sm" onClick={() => setTweak("theme", tweaks.theme === "dark" ? "light" : "dark")}>
          {tweaks.theme === "dark" ? "☼" : "☾"}
        </button>
        <button className="btn primary sm">▶ Run backtest</button>
      </header>

      <main className="app-main">
        {view === "config" && <RunConfigView tweaks={tweaks} setTweak={setTweak} />}
        {view === "overview" && <OverviewView tweaks={tweaks} />}
        {view === "wf" && <WalkForwardView />}
        {view === "cpcv" && <CPCVView />}
        {view === "trades" && <TradesView />}
        {view === "compare" && <CompareView />}
        {view === "risk" && <RiskView />}
      </main>

      {/* Tweaks panel */}
      <window.TweaksPanel title="Tweaks">
        <window.TweakSection title="外觀">
          <window.TweakRadio label="Theme" value={tweaks.theme} onChange={(v) => setTweak("theme", v)} options={[{value:"light",label:"Light"},{value:"dark",label:"Dark"}]} />
          <window.TweakRadio label="Density" value={tweaks.density} onChange={(v) => setTweak("density", v)} options={[{value:"comfortable",label:"Comfortable"},{value:"compact",label:"Compact"}]} />
        </window.TweakSection>
        <window.TweakSection title="Accent color">
          <window.TweakSlider label="Hue" value={tweaks.accentHue} onChange={(v) => setTweak("accentHue", v)} min={0} max={360} step={5} formatValue={(v) => `${v}°`} />
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
