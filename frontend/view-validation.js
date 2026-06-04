import { html } from 'htm/preact';
import { useEffect, useMemo, useRef, useState } from 'preact/hooks';

const ENGINES = ["vectorbt", "backtrader", "nautilus"];
const MISMATCH_FILES = [
  ["indicators", "mismatches_indicators.csv"],
  ["signals", "mismatches_signals.csv"],
  ["trades", "mismatches_trades.csv"],
  ["pnl", "mismatches_pnl.csv"],
  ["metrics", "mismatches_metrics.csv"],
];
const ADVISORY_SCOPE_TOOLTIP = "Advisory scope: 不阻擋 Differential validation gate，但 PnL/metric 真實性由 ct_val provenance、Idealized-fill exclusion、Walk-forward/CPCV 獨立 gate 把關。";
const REBUILT_FIXTURE_WARNING = "Rebuilt fixture · in_sample by default · not edge evidence";

function statusClass(status) {
  const s = String(status || "").toUpperCase();
  if (s === "PASS" || s === "OK" || s === "DONE") return "ok";
  if (s === "FAIL" || s === "ERROR") return "bad";
  return "warn";
}

function StatusChip({ status, note = "", title = "" }) {
  const chip = html`<span class=${"chip " + statusClass(status)}>${status || "unknown"}</span>`;
  if (!note) return title ? html`<span title=${title}>${chip}</span>` : chip;
  return html`
    <span class="chip-wrap" title=${title || note}>
      ${chip}
      <span class="chip-note">${note}</span>
    </span>
  `;
}

function InfoTooltip({ text }) {
  return html`<span class="info-dot" title=${text} aria-label=${text}>?</span>`;
}

function RebuiltFixtureBanner({ active }) {
  if (!active) return null;
  return html`<div class="risk-banner danger">${REBUILT_FIXTURE_WARNING}</div>`;
}

function ReviewerGuardrail({ compact = false }) {
  return html`
    <div class="scope-note" title=${ADVISORY_SCOPE_TOOLTIP}>
      <div>Differential validation PASS covers strict signal logic only; PnL realism remains gated by ct_val provenance, Idealized-fill exclusion, and Walk-forward/CPCV.</div>
      ${!compact && html`
        <div>When a future Backtrader <span class="mono">reference_full</span> adapter is available, trade/PnL/metric scopes become strict automatically. Advisory mismatch counts remain admissible promotion ADR rejection evidence.</div>
      `}
    </div>
  `;
}

function ScopeTag({ role }) {
  return html`<span class=${"scope-tag " + role}>${role}</span>`;
}

function fmtCount(value) {
  const n = Number(typeof value === "object" && value !== null ? value.total : value || 0);
  return Number.isFinite(n) ? n.toLocaleString() : "-";
}

function countPart(value, key) {
  if (typeof value === "object" && value !== null) {
    const n = Number(value[key] || 0);
    return Number.isFinite(n) ? n : 0;
  }
  return key === "total" ? Number(value || 0) : 0;
}

function CountCell({ value }) {
  const total = countPart(value, "total");
  const actionable = countPart(value, "actionable");
  const downstream = countPart(value, "downstream");
  return html`
    <div class="mono">${total.toLocaleString()}</div>
    ${actionable || downstream ? html`
      <div class="field-hint">${actionable.toLocaleString()} actionable / ${downstream.toLocaleString()} downstream</div>
    ` : null}
  `;
}

function roleLabel(role) {
  return String(role || "advisory").replaceAll("_", " ");
}

function runStrategy(run) {
  return run?.strategies?.[0] || run?.strategy || "";
}

function materializedFromSweep(value) {
  const validation = value?.validation || {};
  const parameterSweep = value?.parameter_sweep || validation?.parameter_sweep || {};
  return Boolean(
    value?.materialized_from_sweep_summary ||
    validation?.materialized_from_sweep_summary ||
    parameterSweep?.materialized_from_sweep_summary
  );
}

function validationStatusNote(summary) {
  if (String(summary?.status || "").toUpperCase() !== "PASS") return "";
  if (summary?.admissibility === "advisory_only" || summary?.signal_logic_gate) {
    return "signal logic only";
  }
  return "";
}

function fixtureCanRun(run) {
  if (!run) return false;
  return run.validation_ready !== false || Boolean(run.materialize_ready);
}

function fixtureOptionLabel(run) {
  const status = run.validation_ready === false
    ? (run.materialize_ready ? " (rebuild on run)" : " (unavailable)")
    : "";
  const idealized = run.idealized_fill ? " (idealized)" : "";
  return `${run.run_id}${status}${idealized}`;
}

function fixtureStatusText(run) {
  if (!run) return "";
  if (run.validation_ready !== false) return "ready";
  if (run.materialize_ready) {
    const missing = (run.missing_artifacts || []).join(", ");
    return `missing artifact files${missing ? `: ${missing}` : ""}; will rebuild from sweep metadata`;
  }
  return run.unavailable_reason || "not enough artifact evidence to validate";
}

function fetchFixtureOptions(strategy) {
  const api = window.API || {};
  if (typeof api.fetchStrategyValidationFixtures === "function") {
    return api.fetchStrategyValidationFixtures(strategy);
  }
  if (typeof api.fetchRuns === "function") {
    return api.fetchRuns().then((rows) => (rows || []).filter((run) => runStrategy(run) === strategy));
  }
  return Promise.resolve([]);
}

function EngineSelector({ selected, setSelected }) {
  return html`
    <div class="row wrap" style=${{ gap: 8 }}>
      ${ENGINES.map((engine) => html`
        <label key=${engine} class="check-row" style=${{ minWidth: 130 }}>
          <input
            type="checkbox"
            checked=${selected.includes(engine)}
            onChange=${(e) => {
              if (e.currentTarget.checked) setSelected([...new Set([...selected, engine])]);
              else setSelected(selected.filter((item) => item !== engine));
            }}
          />
          <span>${engine}</span>
        </label>
      `)}
    </div>
  `;
}

function ValidationTable({ rows, onSelect, selectedId }) {
  if (!rows.length) {
    return html`<div class="field-hint" style=${{ padding: 18 }}>No differential validation runs.</div>`;
  }
  return html`
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>Validation</th>
            <th>Status</th>
            <th>Engines</th>
            <th title=${ADVISORY_SCOPE_TOOLTIP}>Indicators <${ScopeTag} role="advisory" /></th>
            <th>Signals <${ScopeTag} role="strict" /></th>
            <th title=${ADVISORY_SCOPE_TOOLTIP}>Trades <${ScopeTag} role="advisory" /></th>
            <th title=${ADVISORY_SCOPE_TOOLTIP}>PnL <${ScopeTag} role="advisory" /></th>
            <th title=${ADVISORY_SCOPE_TOOLTIP}>Metrics <${ScopeTag} role="advisory" /></th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => html`
            <tr
              key=${row.validation_id}
              onClick=${() => onSelect(row.validation_id)}
              style=${{ cursor: "pointer", background: selectedId === row.validation_id ? "var(--surface-2)" : undefined }}
            >
              <td class="mono">${row.validation_id}</td>
              <td><${StatusChip} status=${row.status} note=${validationStatusNote(row)} title=${ADVISORY_SCOPE_TOOLTIP} /></td>
              <td>${(row.engines || []).join(", ")}</td>
              <td><${CountCell} value=${row.mismatch_counts?.indicators} /></td>
              <td><${CountCell} value=${row.mismatch_counts?.signals} /></td>
              <td><${CountCell} value=${row.mismatch_counts?.trades} /></td>
              <td><${CountCell} value=${row.mismatch_counts?.pnl} /></td>
              <td><${CountCell} value=${row.mismatch_counts?.metrics} /></td>
            </tr>
          `)}
        </tbody>
      </table>
    </div>
  `;
}

function EngineSummary({ detail }) {
  const engines = detail?.engines || {};
  const names = Object.keys(engines);
  if (!names.length) return null;
  return html`
    <div class="grid two">
      ${names.map((name) => {
        const engine = engines[name] || {};
        const comparison = engine.comparison || {};
        const scopes = comparison.scopes || {};
        return html`
          <div class="card" key=${name}>
            <div class="row" style=${{ justifyContent: "space-between", alignItems: "center" }}>
              <div class="card-title">${name}</div>
              <${StatusChip} status=${engine.status} />
            </div>
            <div class="field-hint" style=${{ marginTop: 8 }}>Role: ${roleLabel(engine.reference_role)}</div>
            ${engine.reason && html`<div class="field-hint" style=${{ marginTop: 8 }}>${engine.reason}</div>`}
            <div class="metric-grid" style=${{ marginTop: 12 }}>
              <div><div class="metric-label">Indicators</div><div class="metric-value">${fmtCount(engine.rows?.indicator_series)}</div></div>
              <div><div class="metric-label">Signals</div><div class="metric-value">${fmtCount(engine.rows?.signals)}</div></div>
              <div><div class="metric-label">Trades</div><div class="metric-value">${fmtCount(engine.rows?.trades)}</div></div>
              <div><div class="metric-label">Comparison</div><div class="metric-value"><${StatusChip} status=${comparison.status || engine.status} /></div></div>
            </div>
            ${Object.keys(scopes).length > 0 && html`
              <div class="tbl-wrap" style=${{ marginTop: 12 }}>
                <table class="tbl compact">
                  <tbody>
                    ${Object.entries(scopes).map(([scope, info]) => html`
                      <tr key=${scope}>
                        <td>${scope.replaceAll("_", " ")}</td>
                        <td><${StatusChip} status=${info.status} /></td>
                        <td><${CountCell} value=${info} /></td>
                      </tr>
                    `)}
                  </tbody>
                </table>
              </div>
            `}
          </div>
        `;
      })}
    </div>
  `;
}

function MismatchPreview({ strategy, validationId }) {
  const [active, setActive] = useState("metrics");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const file = MISMATCH_FILES.find(([name]) => name === active)?.[1] || "mismatches_metrics.csv";

  useEffect(() => {
    if (!strategy || !validationId) return;
    setLoading(true);
    window.API.fetchStrategyValidationArtifact(strategy, validationId, file)
      .then((data) => setRows((data || []).slice(0, 100)))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [strategy, validationId, file]);

  return html`
    <div class="card" title=${ADVISORY_SCOPE_TOOLTIP}>
      <div class="row wrap" style=${{ justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <div>
          <div class="card-title">Mismatches <${InfoTooltip} text=${ADVISORY_SCOPE_TOOLTIP} /></div>
          <div class="field-hint">Advisory means not auto-failing this gate; actionable counts remain promotion ADR reviewer evidence.</div>
        </div>
        <div class="seg">
          ${MISMATCH_FILES.map(([name]) => html`
            <button
              class=${active === name ? "active" : ""}
              title=${["trades", "pnl", "metrics"].includes(name) ? ADVISORY_SCOPE_TOOLTIP : ""}
              onClick=${() => setActive(name)}
            >${name}</button>
          `)}
        </div>
      </div>
      ${loading
        ? html`<div class="field-hint" style=${{ padding: 18 }}>Loading...</div>`
        : html`
          <div class="tbl-wrap" style=${{ marginTop: 12 }}>
            <table class="tbl">
              <thead>
                <tr>
                  <th>Engine</th>
                  <th>Category</th>
                  <th>Field</th>
                  <th>Status</th>
                  <th>Downstream</th>
                  <th>Project</th>
                  <th>Reference</th>
                  <th>Diff</th>
                </tr>
              </thead>
              <tbody>
                ${rows.length
                  ? rows.map((row, idx) => html`
                    <tr key=${idx}>
                      <td>${row.engine || ""}</td>
                      <td>${row.category || ""}</td>
                      <td>${row.field || ""}</td>
                      <td>${row.status || ""}</td>
                      <td>${row.downstream ? "yes" : ""}</td>
                      <td class="mono">${String(row.project_value ?? "").slice(0, 40)}</td>
                      <td class="mono">${String(row.reference_value ?? "").slice(0, 40)}</td>
                      <td class="mono">${row.abs_diff ?? ""}</td>
                    </tr>
                  `)
                  : html`<tr><td colSpan="8" class="field-hint" style=${{ textAlign: "center", padding: 16 }}>No rows.</td></tr>`}
              </tbody>
            </table>
          </div>
        `}
    </div>
  `;
}

function ValidationLabView({ selectedRunId, setSelectedRunId }) {
  const [fixtures, setFixtures] = useState([]);
  const [validations, setValidations] = useState([]);
  const [validationsStrategy, setValidationsStrategy] = useState("");
  const [selectedValidation, setSelectedValidation] = useState(null);
  const [detail, setDetail] = useState(null);
  const [strategy, setStrategy] = useState("ma_crossover");
  const [fixtureRunId, setFixtureRunId] = useState("");
  const [engines, setEngines] = useState(["vectorbt", "backtrader", "nautilus"]);
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const validationRequestSeq = useRef(0);

  const strategyOptions = useMemo(() => window.MOCK?.STRATEGIES || [], []);
  const fixtureOptions = useMemo(() => fixtures || [], [fixtures]);
  const activeValidations = validationsStrategy === strategy ? validations : [];
  const selectedFixtureRunId = fixtureRunId || fixtureOptions[0]?.run_id || "";
  const selectedFixture = fixtureOptions.find((run) => run.run_id === selectedFixtureRunId) || null;
  const selectedFixtureCanRun = fixtureCanRun(selectedFixture);
  const activeDetail = detail?.__strategy === strategy && detail?.validation_id === selectedValidation ? detail : null;
  const selectedFixtureWasRebuilt = materializedFromSweep(selectedFixture);
  const activeDetailWasRebuilt = materializedFromSweep(activeDetail) || (
    activeDetail?.fixture_run_id &&
    activeDetail.fixture_run_id === selectedFixture?.run_id &&
    selectedFixtureWasRebuilt
  );

  function refreshValidations(name = strategy) {
    if (!name) return;
    const requestId = ++validationRequestSeq.current;
    setLoading(true);
    window.API.fetchStrategyValidations(name)
      .then((rows) => {
        if (requestId !== validationRequestSeq.current) return;
        const list = rows || [];
        setValidationsStrategy(name);
        setValidations(list);
        setSelectedValidation((current) => {
          if (current && list.some((row) => row.validation_id === current)) return current;
          return list[0]?.validation_id || null;
        });
      })
      .catch(() => {
        if (requestId !== validationRequestSeq.current) return;
        setValidationsStrategy(name);
        setValidations([]);
        setSelectedValidation(null);
      })
      .finally(() => {
        if (requestId === validationRequestSeq.current) setLoading(false);
      });
  }

  useEffect(() => {
    window.API.fetchRuns().then((rows) => {
      const list = rows || [];
      const selected = list.find((run) => run.run_id === selectedRunId) || list[0];
      const selectedStrategy = runStrategy(selected);
      if (selectedStrategy) setStrategy(selectedStrategy);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setSelectedValidation(null);
    setDetail(null);
    setFixtureRunId("");
    setFixtures([]);
    setValidations([]);
    setValidationsStrategy(strategy);
    fetchFixtureOptions(strategy)
      .then((rows) => {
        if (cancelled) return;
        const list = rows || [];
        setFixtures(list);
        const preferred =
          list.find((run) => run.run_id === selectedRunId) ||
          list.find((run) => fixtureCanRun(run)) ||
          list[0];
        if (preferred?.run_id) {
          setFixtureRunId(preferred.run_id);
          if (selectedRunId !== preferred.run_id) setSelectedRunId?.(preferred.run_id);
        }
      })
      .catch(() => {
        if (!cancelled) setFixtures([]);
      });
    refreshValidations(strategy);
    return () => { cancelled = true; };
  }, [strategy]);

  useEffect(() => {
    if (!selectedRunId || !fixtureOptions.some((run) => run.run_id === selectedRunId)) return;
    setFixtureRunId(selectedRunId);
  }, [selectedRunId, fixtureOptions]);

  useEffect(() => {
    if (!strategy || !selectedValidation || validationsStrategy !== strategy) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setDetail(null);
    window.API.fetchStrategyValidation(strategy, selectedValidation)
      .then((data) => {
        if (!cancelled) setDetail({ ...(data || {}), __strategy: strategy });
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      });
    return () => { cancelled = true; };
  }, [strategy, selectedValidation, validationsStrategy]);

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "error") return;
    const timer = setInterval(() => {
      window.API.fetchDifferentialValidationStatus(job.job_id)
        .then((state) => {
          setJob(state);
          if (state.status === "done") {
            refreshValidations(state.strategy || strategy);
            if (state.validation_id) setSelectedValidation(state.validation_id);
          }
        })
        .catch(() => {});
    }, 1500);
    return () => clearInterval(timer);
  }, [job?.job_id, job?.status]);

  function trigger() {
    if (!strategy || !selectedFixtureRunId || !selectedFixtureCanRun || !engines.length) return;
    setJob({ status: "queued", progress: 0, message: "Queued" });
    window.API.triggerStrategyValidation({ strategy, fixture_run_id: selectedFixtureRunId || null, engines })
      .then(setJob)
      .catch((err) => setJob({ status: "error", message: err.message }));
  }

  return html`
    <div class="stack">
      <div class="card">
        <div class="row wrap" style=${{ justifyContent: "space-between", alignItems: "flex-end", gap: 14 }}>
          <div style=${{ minWidth: 280, flex: 1 }}>
            <div class="field-label">Strategy</div>
            <select class="select" value=${strategy} onChange=${(e) => setStrategy(e.currentTarget.value)}>
              ${strategyOptions.map((item) => html`<option key=${item.id} value=${item.id}>${item.name}</option>`)}
            </select>
          </div>
          <div style=${{ minWidth: 280, flex: 1 }}>
            <div class="field-label">Fixture artifact</div>
            <select
              class="select"
              value=${selectedFixtureRunId}
              onChange=${(e) => { setFixtureRunId(e.currentTarget.value); setSelectedRunId?.(e.currentTarget.value); }}
            >
              ${fixtureOptions.map((run) => html`
                <option key=${run.run_id} value=${run.run_id}>
                  ${fixtureOptionLabel(run)}
                </option>
              `)}
            </select>
            ${selectedFixture && html`
              <div class="field-hint" style=${{ marginTop: 8 }}>${fixtureStatusText(selectedFixture)}</div>
              <${RebuiltFixtureBanner} active=${selectedFixtureWasRebuilt} />
            `}
            ${!fixtureOptions.length && html`
              <div class="field-hint" style=${{ marginTop: 8 }}>No historical fixture candidates for this strategy.</div>
            `}
          </div>
          <div>
            <div class="field-label">Reference engines</div>
            <${EngineSelector} selected=${engines} setSelected=${setEngines} />
          </div>
          <button class="btn primary" disabled=${!strategy || !selectedFixtureRunId || !selectedFixtureCanRun || !engines.length || job?.status === "running"} onClick=${trigger}>
            Run validation
          </button>
        </div>
        ${job && html`
          <div class="row wrap" style=${{ marginTop: 12, gap: 10, alignItems: "center" }}>
            <${StatusChip} status=${job.status} />
            <span class="field-hint">${job.message || ""}</span>
            ${job.validation_id && html`<span class="mono">${job.validation_id}</span>`}
          </div>
        `}
      </div>

      <div class="card">
        <div class="row" style=${{ justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div class="card-title">Validation Runs</div>
            <div class="card-sub">OHLCV source validation: deferred</div>
          </div>
          ${loading && html`<span class="field-hint">Loading...</span>`}
        </div>
        <${ReviewerGuardrail} compact=${true} />
        <${ValidationTable} rows=${activeValidations} onSelect=${setSelectedValidation} selectedId=${selectedValidation} />
      </div>

      ${activeDetail && html`
        <div class="card">
          <${RebuiltFixtureBanner} active=${activeDetailWasRebuilt} />
          <div class="row wrap" style=${{ justifyContent: "space-between", alignItems: "center", gap: 10 }}>
            <div>
              <div class="card-title">${activeDetail.validation_id}</div>
              <div class="card-sub">${activeDetail.created_at}</div>
              <div class="field-hint">Promotion gate evidence: ${String(Boolean(activeDetail.promotion_gate_evidence))}; ${activeDetail.admissibility || "advisory_only"}</div>
            </div>
            <${StatusChip} status=${activeDetail.status} note=${validationStatusNote(activeDetail)} title=${ADVISORY_SCOPE_TOOLTIP} />
          </div>
          <div class="metric-grid" style=${{ marginTop: 12 }}>
            <div title=${ADVISORY_SCOPE_TOOLTIP}><div class="metric-label">Indicators <${ScopeTag} role="advisory" /></div><div class="metric-value"><${CountCell} value=${activeDetail.mismatch_counts?.indicators} /></div></div>
            <div><div class="metric-label">Signals <${ScopeTag} role="strict" /></div><div class="metric-value"><${CountCell} value=${activeDetail.mismatch_counts?.signals} /></div></div>
            <div title=${ADVISORY_SCOPE_TOOLTIP}><div class="metric-label">PnL <${ScopeTag} role="advisory" /> <${InfoTooltip} text=${ADVISORY_SCOPE_TOOLTIP} /></div><div class="metric-value"><${CountCell} value=${activeDetail.mismatch_counts?.pnl} /></div></div>
            <div title=${ADVISORY_SCOPE_TOOLTIP}><div class="metric-label">Metrics <${ScopeTag} role="advisory" /> <${InfoTooltip} text=${ADVISORY_SCOPE_TOOLTIP} /></div><div class="metric-value"><${CountCell} value=${activeDetail.mismatch_counts?.metrics} /></div></div>
          </div>
          <${ReviewerGuardrail} />
        </div>
        <${EngineSummary} detail=${activeDetail} />
        <${MismatchPreview} strategy=${strategy} validationId=${activeDetail.validation_id} />
      `}
    </div>
  `;
}

window.ValidationLabView = ValidationLabView;
