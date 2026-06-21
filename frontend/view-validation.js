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
/*
const ADVISORY_SCOPE_TOOLTIP = "Advisory scope: 不阻擋 Differential validation gate，但 PnL/metric 真實性由 ct_val provenance、Idealized-fill exclusion、Walk-forward/CPCV 獨立 gate 把關。";
const REBUILT_FIXTURE_WARNING = "Rebuilt fixture · in_sample by default · not edge evidence";

*/
const ADVISORY_SCOPE_TOOLTIP = "Advisory scope: does not block the Differential validation gate. PnL and metric realism are gated separately by ct_val provenance, idealized-fill exclusion, and Walk-forward/CPCV.";
const REBUILT_FIXTURE_WARNING = "Rebuilt fixture - in_sample by default - not edge evidence";

function statusClass(status) {
  const s = String(status || "").toUpperCase();
  if (["PASS", "OK", "DONE", "IMPLEMENTED"].includes(s)) return "ok";
  if (["FAIL", "ERROR", "ADAPTER_REQUIRED", "MISSING"].includes(s)) return "bad";
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
  // A passing scope reports 0 mismatches; render it as a clear "✓ 0" so it does
  // not read as "empty / nothing compared".
  if (total === 0) {
    return html`<div class="mono" style=${{ color: "var(--profit)" }} title="0 mismatches">✓ 0</div>`;
  }
  return html`
    <div class="mono">${total.toLocaleString()}</div>
    ${actionable || downstream ? html`
      <div class="field-hint">${actionable.toLocaleString()} actionable / ${downstream.toLocaleString()} downstream</div>
    ` : null}
  `;
}

// True if any reference engine actually executed trades. When false, the
// PnL/Trades/Metrics advisory counts are structural noise (the signals-only v1
// reference keeps equity flat), not defects.
function referenceExecutesTrades(detail) {
  const engines = detail?.engines || {};
  return Object.values(engines).some((e) => Number(e?.rows?.trades || 0) > 0);
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
  return `${run.display_name || run.run_id}${status}${idealized}`;
}

function validationLabel(row) {
  return row?.display_name || row?.validation_id || "";
}

function fixtureLabel(row) {
  return row?.fixture_display_name || row?.fixture_run_id || row?.run_id || "";
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

function engineCapability(contract, engine) {
  return contract?.engines?.[engine] || {
    status: "missing",
    role: "not_applicable",
    limitation: "No reference-engine contract declared for this engine.",
  };
}

function compactStatus(status) {
  return String(status || "missing").replaceAll("_", " ");
}

function dependencyRequirement(engine) {
  if (engine === "vectorbt") return "Python package vectorbt is installed";
  if (engine === "backtrader") return "Python package backtrader is installed";
  if (engine === "nautilus") return "advisory export plus optional signal replay execution; full project strategy parity remains out of scope";
  return "adapter dependency is available";
}

function triggerConditions(capability, engine) {
  const role = capability?.role || "advisory";
  const artifacts = capability?.required_artifacts || [];
  const conditions = [
    `${engine} is selected for the validation run`,
    `contract status is ${compactStatus(capability?.status || "missing")}`,
    dependencyRequirement(engine),
  ];
  if (artifacts.length) {
    conditions.push(`required artifacts present: ${artifacts.join(", ")}`);
  }
  if (role === "reference_signals_only") {
    conditions.push("strict comparison scope: signal_logic");
  } else if (role === "reference_full") {
    conditions.push("strict comparison scope: signals, trades, PnL, and metrics");
  } else if (role === "advisory") {
    conditions.push("advisory comparison only; portable gate requires independent reference evidence");
  } else {
    conditions.push(`role: ${roleLabel(role)}`);
  }
  return conditions;
}

function EngineSelector({ selected, setSelected, contract }) {
  return html`
    <div class="row wrap" style=${{ gap: 8 }}>
      ${ENGINES.map((engine) => {
        const capability = engineCapability(contract, engine);
        return html`
        <label key=${engine} class="check-row" title=${capability.limitation || ""} style=${{ minWidth: 170 }}>
          <input
            type="checkbox"
            checked=${selected.includes(engine)}
            onChange=${(e) => {
              if (e.currentTarget.checked) setSelected([...new Set([...selected, engine])]);
              else setSelected(selected.filter((item) => item !== engine));
            }}
          />
          <span>${engine}</span>
          <${StatusChip} status=${capability.status} />
        </label>
      `})}
    </div>
  `;
}

function ReferenceContractPanel({ contract, selectedEngines = [] }) {
  if (!contract) return null;
  const engines = contract.engines || {};
  return html`
    <div class="scope-note" style=${{ marginTop: 12 }}>
      <div class="row wrap" style=${{ justifyContent: "space-between", gap: 10, alignItems: "center" }}>
        <div>
          <div class="field-label">Reference portability</div>
          <div class="field-hint">
            ${contract.strategy_class || "strategy"} · minimum references ${contract.minimum_reference_engines ?? 1}
            ${contract.validation_only ? " · validation only" : ""}
          </div>
        </div>
        <${StatusChip} status=${contract.contract_status || "missing"} />
      </div>
      <div class="tbl-wrap" style=${{ marginTop: 10 }}>
        <table class="tbl compact">
          <thead>
            <tr>
              <th>Engine</th>
              <th>Status</th>
              <th>Role</th>
              <th>Trigger</th>
              <th>Artifacts</th>
              <th>Limitation</th>
            </tr>
          </thead>
          <tbody>
            ${ENGINES.map((engine) => {
              const capability = engines[engine] || engineCapability(contract, engine);
              const artifacts = capability.required_artifacts || [];
              return html`
                <tr key=${engine} style=${{ opacity: selectedEngines.length && !selectedEngines.includes(engine) ? 0.72 : 1 }}>
                  <td class="mono">${engine}</td>
                  <td><${StatusChip} status=${capability.status} note=${compactStatus(capability.status)} /></td>
                  <td>${roleLabel(capability.role)}</td>
                  <td>
                    <ul class="compact-list">
                      ${triggerConditions(capability, engine).map((item) => html`<li key=${item}>${item}</li>`)}
                    </ul>
                  </td>
                  <td class="mono">${artifacts.length ? artifacts.join(", ") : "-"}</td>
                  <td>${capability.limitation || "-"}</td>
                </tr>
              `;
            })}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function SourceDataValidationPanel({ validation, conclusion }) {
  if (!validation && !conclusion) return null;
  const checks = validation?.checks || {};
  const rows = Object.entries(checks);
  return html`
    <div class="scope-note" style=${{ marginTop: 12 }}>
      <div class="row wrap" style=${{ justifyContent: "space-between", gap: 10, alignItems: "center" }}>
        <div>
          <div class="field-label">Validation conclusion</div>
          <div class="field-hint">${conclusion?.summary || validation?.ohlcv_source_validation || ""}</div>
        </div>
        <${StatusChip} status=${conclusion?.status || validation?.status || "unknown"} />
      </div>
      ${validation && html`
        <div class="tbl-wrap" style=${{ marginTop: 10 }}>
          <table class="tbl compact">
            <thead>
              <tr>
                <th>Check</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(([name, check]) => html`
                <tr key=${name}>
                  <td>${name.replaceAll("_", " ")}</td>
                  <td><${StatusChip} status=${check.status} /></td>
                  <td class="mono">${check.rows ?? "-"}</td>
                  <td>${check.reason || check.missing?.join(", ") || "-"}</td>
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;
}

function ExternalValidationConclusionPanel({ conclusion }) {
  if (!conclusion) return null;
  const engines = conclusion.external_engines || {};
  const gaps = conclusion.blocking_gaps || [];
  const actions = conclusion.next_required_actions || [];
  return html`
    <div class="scope-note" style=${{ marginTop: 12 }}>
      <div class="row wrap" style=${{ justifyContent: "space-between", gap: 10, alignItems: "center" }}>
        <div>
          <div class="field-label">External validation conclusion</div>
          <div class="field-hint">${conclusion.summary || ""}</div>
        </div>
        <${StatusChip} status=${conclusion.status || "unknown"} />
      </div>
      <div class="metric-grid" style=${{ marginTop: 10 }}>
        <div><div class="metric-label">Completed</div><div class="metric-value">${(engines.completed || []).join(", ") || "-"}</div></div>
        <div><div class="metric-label">Independent</div><div class="metric-value">${(engines.independent_reference || []).join(", ") || "-"}</div></div>
        <div><div class="metric-label">Advisory</div><div class="metric-value">${(engines.advisory_only || []).join(", ") || "-"}</div></div>
        <div><div class="metric-label">Data</div><div class="metric-value"><${StatusChip} status=${conclusion.data_correctness?.status || "unknown"} /></div></div>
      </div>
      ${gaps.length ? html`
        <div class="field-hint" style=${{ marginTop: 10 }}>Blocking gaps</div>
        <ul class="compact-list">
          ${gaps.map((item) => html`<li key=${item}>${item}</li>`)}
        </ul>
      ` : null}
      ${actions.length ? html`
        <div class="field-hint" style=${{ marginTop: 10 }}>Next required actions</div>
        <ul class="compact-list">
          ${actions.map((item) => html`<li key=${item}>${item}</li>`)}
        </ul>
      ` : null}
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
            <th>Backtest</th>
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
              <td>
                <div class="mono">${validationLabel(row)}</div>
                ${row.display_name && row.validation_id !== row.display_name && html`<div class="field-hint mono">${row.validation_id}</div>`}
              </td>
              <td>
                <div class="mono">${fixtureLabel(row) || "-"}</div>
                ${row.fixture_display_name && row.fixture_run_id && row.fixture_display_name !== row.fixture_run_id && html`<div class="field-hint mono">${row.fixture_run_id}</div>`}
              </td>
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

function EngineSummary({ detail, contract }) {
  const engines = detail?.engines || {};
  const capabilities = contract?.engines || detail?.reference_validation_contract?.engines || {};
  const names = Object.keys(engines);
  if (!names.length) return null;
  return html`
    <div class="grid two">
      ${names.map((name) => {
        const engine = engines[name] || {};
        const capability = capabilities[name] || engineCapability(contract || detail?.reference_validation_contract, name);
        const comparison = engine.comparison || {};
        const scopes = comparison.scopes || {};
        const metadata = engine.metadata || {};
        const priceInput = metadata.price_input || {};
        const artifacts = capability.required_artifacts || [];
        return html`
          <div class="card" key=${name}>
            <div class="row" style=${{ justifyContent: "space-between", alignItems: "center" }}>
              <div class="card-title">${name}</div>
              <${StatusChip} status=${engine.status} />
            </div>
            <div class="field-hint" style=${{ marginTop: 8 }}>Role: ${roleLabel(engine.reference_role || capability.role)}</div>
            ${capability.role && engine.reference_role && capability.role !== engine.reference_role && html`
              <div class="field-hint" style=${{ marginTop: 8 }}>Contract role: ${roleLabel(capability.role)}</div>
            `}
            ${artifacts.length ? html`<div class="field-hint mono" style=${{ marginTop: 8 }}>Artifacts: ${artifacts.join(", ")}</div>` : null}
            ${capability.limitation && html`<div class="field-hint" style=${{ marginTop: 8 }}>Contract limit: ${capability.limitation}</div>`}
            <div class="field-hint" style=${{ marginTop: 8 }}>Trigger:</div>
            <ul class="compact-list">
              ${triggerConditions(capability, name).map((item) => html`<li key=${item}>${item}</li>`)}
            </ul>
            ${engine.reason && html`<div class="field-hint" style=${{ marginTop: 8 }}>${engine.reason}</div>`}
            ${metadata.reference_mode && html`<div class="field-hint" style=${{ marginTop: 8 }}>Mode: ${String(metadata.reference_mode).replaceAll("_", " ")}</div>`}
            ${priceInput.source && html`
              <div class="field-hint" style=${{ marginTop: 8 }}>
                Price input: ${String(priceInput.source).replaceAll("_", " ")}
                ${priceInput.reason ? html` · ${priceInput.reason}` : ""}
              </div>
            `}
            ${metadata.scope_limit && html`<div class="field-hint" style=${{ marginTop: 8 }}>Limit: ${metadata.scope_limit}</div>`}
            <div class="field-hint" style=${{ marginTop: 12 }}>Reference output (row counts, not mismatches)</div>
            <div class="metric-grid" style=${{ marginTop: 6 }}>
              <div><div class="metric-label">Indicator rows</div><div class="metric-value">${fmtCount(engine.rows?.indicator_series)}</div></div>
              <div><div class="metric-label">Signal rows</div><div class="metric-value">${fmtCount(engine.rows?.signals)}</div></div>
              <div><div class="metric-label">Trade rows</div><div class="metric-value">${fmtCount(engine.rows?.trades)}</div></div>
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

function EngineExecutionMatrix({ matrix }) {
  const rows = Array.isArray(matrix) ? matrix : [];
  if (!rows.length) return null;
  return html`
    <div class="card">
      <div class="card-title">Engine execution matrix</div>
      <div class="tbl-wrap" style=${{ marginTop: 10 }}>
        <table class="tbl compact">
          <thead>
            <tr>
              <th>Engine</th>
              <th>Run state</th>
              <th>Trigger</th>
              <th>Gate role</th>
              <th>Dependency</th>
              <th>Replay coverage</th>
              <th>Missing artifacts</th>
              <th>Limit</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((row) => {
              const missing = row.missing_artifacts || [];
              const limit = (row.limitations || [row.scope_limit || ""]).filter(Boolean)[0] || "-";
              const dep = row.dependency
                ? `${row.dependency}: ${row.dependency_available === true ? "available" : row.dependency_available === false ? "missing" : "unknown"}`
                : "-";
              const coverage = row.signal_replay_coverage || {};
              const coverageText = coverage.total_signal_rows != null
                ? `${coverage.replayable_signal_rows || 0}/${coverage.total_signal_rows || 0}`
                : "-";
              const coverageTitle = coverage.skipped_symbols?.length
                ? `Skipped symbols: ${coverage.skipped_symbols.join(", ")}`
                : "";
              return html`
                <tr key=${row.engine}>
                  <td class="mono">${row.engine}</td>
                  <td><${StatusChip} status=${row.status} note=${String(row.engine_execution || row.execution_state || "").replaceAll("_", " ")} /></td>
                  <td>${String(row.trigger_status || "-").replaceAll("_", " ")}</td>
                  <td>${String(row.gate_role || "-").replaceAll("_", " ")}</td>
                  <td>${dep}</td>
                  <td title=${coverageTitle}>${coverageText}</td>
                  <td class="mono">${missing.length ? missing.join(", ") : "-"}</td>
                  <td title=${limit}>${limit}</td>
                </tr>
              `;
            })}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function SignalPointCorrectnessMatrix({ matrix }) {
  const rows = Array.isArray(matrix?.rows) ? matrix.rows : [];
  if (!rows.length) return null;
  const strictFields = matrix.strict_fields || [];
  const advisoryScope = matrix.advisory_scope || [];
  const advisoryText = (diffs) => {
    const value = diffs || {};
    return ["trades", "pnl", "metrics"]
      .map((name) => `${name}: ${fmtCount(value[name])}`)
      .join(" / ");
  };
  return html`
    <div class="card">
      <div class="row wrap" style=${{ justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <div>
          <div class="card-title">Signal point correctness</div>
          <div class="card-sub">
            ${strictFields.length ? strictFields.join(", ") : "timestamp/bar, symbol, side, action"}
            ${advisoryScope.length ? html` · Advisory: ${advisoryScope.join(", ")}` : ""}
          </div>
        </div>
        <${StatusChip} status=${matrix.status || (matrix.passed ? "PASS" : "FAIL")} />
      </div>
      <div class="tbl-wrap" style=${{ marginTop: 10 }}>
        <table class="tbl compact">
          <thead>
            <tr>
              <th>Engine</th>
              <th>Point correctness</th>
              <th>Mismatches</th>
              <th>Examples</th>
              <th>Advisory differences</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((row) => {
              const examples = Array.isArray(row.mismatch_examples) ? row.mismatch_examples : [];
              const exampleText = examples.length
                ? examples.map((item) => `${item.field || "field"} #${item.sequence ?? "-"}`).join(", ")
                : "-";
              return html`
                <tr key=${row.engine}>
                  <td class="mono">${row.engine}</td>
                  <td><${StatusChip} status=${row.point_correctness_status || row.status} note=${roleLabel(row.reference_role)} /></td>
                  <td><${CountCell} value=${{ total: row.mismatch_count || 0, actionable: row.actionable_mismatch_count || 0, downstream: row.downstream_mismatch_count || 0 }} /></td>
                  <td title=${JSON.stringify(examples)}>${exampleText}</td>
                  <td title=${(row.advisory_differences?.advisory_scope || []).join(", ")}>${advisoryText(row.advisory_differences)}</td>
                </tr>
              `;
            })}
          </tbody>
        </table>
      </div>
      ${matrix.missing_or_failed_target_engines?.length ? html`
        <div class="field-hint" style=${{ marginTop: 10 }}>
          Target gaps: ${matrix.missing_or_failed_target_engines.join(", ")}
        </div>
      ` : null}
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
  const [contract, setContract] = useState(null);
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
  const activeContract = activeDetail?.reference_validation_contract || contract;
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
    if (!strategy || typeof window.API.fetchStrategyValidationContracts !== "function") {
      setContract(null);
      return;
    }
    let cancelled = false;
    setContract(null);
    window.API.fetchStrategyValidationContracts(strategy)
      .then((data) => {
        if (!cancelled) setContract(data || null);
      })
      .catch(() => {
        if (!cancelled) setContract(null);
      });
    return () => { cancelled = true; };
  }, [strategy]);

  useEffect(() => {
    if (!selectedRunId || typeof window.API.fetchRuns !== "function") return;
    let cancelled = false;
    window.API.fetchRuns()
      .then((runs) => {
        if (cancelled) return;
        const run = (runs || []).find((row) => row.run_id === selectedRunId);
        const selectedStrategy = runStrategy(run);
        if (selectedStrategy) setStrategy(selectedStrategy);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [selectedRunId]);

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
        <div class="validation-run-form">
          <div class="field validation-run-field">
            <div class="field-label">Strategy</div>
            <select class="select" value=${strategy} onChange=${(e) => setStrategy(e.currentTarget.value)}>
              ${strategyOptions.map((item) => html`<option key=${item.id} value=${item.id}>${item.name}</option>`)}
            </select>
          </div>
          <div class="field validation-run-field">
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
          <div class="validation-run-engines">
            <div class="field-label">Reference engines</div>
            <${EngineSelector} selected=${engines} setSelected=${setEngines} contract=${contract} />
          </div>
          <div class="validation-run-action">
            <button class="btn primary" disabled=${!strategy || !selectedFixtureRunId || !selectedFixtureCanRun || !engines.length || job?.status === "running"} onClick=${trigger}>
              Run validation
            </button>
          </div>
        </div>
        <${ReferenceContractPanel} contract=${contract} selectedEngines=${engines} />
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
            <div class="card-sub">OHLCV source validation: ${activeDetail?.ohlcv_source_validation || "select a run"}</div>
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
              <div class="card-title">${activeDetail.display_name || activeDetail.validation_id}</div>
              <div class="card-sub">${activeDetail.created_at}</div>
              <div class="field-hint">
                Validates backtest:
                <span class="mono">${activeDetail.fixture_display_name || activeDetail.fixture_run_id || activeDetail.run_id || "-"}</span>
                ${activeDetail.fixture_run_id && html`<span class="mono"> (${activeDetail.fixture_run_id})</span>`}
              </div>
              <div class="field-hint">Promotion gate evidence: ${String(Boolean(activeDetail.promotion_gate_evidence))}; ${activeDetail.admissibility || "advisory_only"}</div>
              ${activeDetail.portable_validation_gate && html`
                <div class="field-hint">
                  Portable gate:
                  ${String(Boolean(activeDetail.portable_validation_gate.passed))}
                  ${activeDetail.portable_validation_gate.blocked_reason ? html` · ${activeDetail.portable_validation_gate.blocked_reason}` : ""}
                </div>
              `}
            </div>
            <${StatusChip} status=${activeDetail.status} note=${validationStatusNote(activeDetail)} title=${ADVISORY_SCOPE_TOOLTIP} />
          </div>
          <div class="metric-grid" style=${{ marginTop: 12 }}>
            <div title=${ADVISORY_SCOPE_TOOLTIP}><div class="metric-label">Indicators <${ScopeTag} role="advisory" /></div><div class="metric-value"><${CountCell} value=${activeDetail.mismatch_counts?.indicators} /></div></div>
            <div><div class="metric-label">Signals <${ScopeTag} role="strict" /></div><div class="metric-value"><${CountCell} value=${activeDetail.mismatch_counts?.signals} /></div></div>
            <div title=${ADVISORY_SCOPE_TOOLTIP}><div class="metric-label">PnL <${ScopeTag} role="advisory" /> <${InfoTooltip} text=${ADVISORY_SCOPE_TOOLTIP} /></div><div class="metric-value"><${CountCell} value=${activeDetail.mismatch_counts?.pnl} /></div></div>
            <div title=${ADVISORY_SCOPE_TOOLTIP}><div class="metric-label">Metrics <${ScopeTag} role="advisory" /> <${InfoTooltip} text=${ADVISORY_SCOPE_TOOLTIP} /></div><div class="metric-value"><${CountCell} value=${activeDetail.mismatch_counts?.metrics} /></div></div>
          </div>
          ${!referenceExecutesTrades(activeDetail) && html`
            <div class="field-hint" style=${{ marginTop: 6 }}>
              PnL / Trades / Metrics advisory counts compare against a signals-only reference that does not execute trades (v1), so its equity stays flat — nonzero counts here are expected and are not defects. Read signal logic + engine quorum instead.
            </div>
          `}
          <${ReviewerGuardrail} />
          <${SourceDataValidationPanel} validation=${activeDetail.source_data_validation} conclusion=${activeDetail.validation_conclusion} />
          <${ExternalValidationConclusionPanel} conclusion=${activeDetail.external_validation_conclusion} />
          <${ReferenceContractPanel} contract=${activeContract} selectedEngines=${Object.keys(activeDetail.engines || {})} />
        </div>
        <${EngineSummary} detail=${activeDetail} contract=${activeContract} />
        <${EngineExecutionMatrix} matrix=${activeDetail.engine_execution_matrix} />
        <${SignalPointCorrectnessMatrix} matrix=${activeDetail.signal_point_correctness} />
        <${MismatchPreview} strategy=${strategy} validationId=${activeDetail.validation_id} />
      `}
    </div>
  `;
}

window.ValidationLabView = ValidationLabView;
