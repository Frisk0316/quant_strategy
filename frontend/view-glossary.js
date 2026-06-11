import { h } from 'preact';
import { html } from 'htm/preact';

function metricLabel(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

const METRIC_GROUPS = [
  {
    title: "Return / Risk",
    keys: [
      "total_return", "cagr", "sharpe", "sortino", "max_drawdown",
      "calmar", "omega", "tail_ratio", "skewness", "kurtosis",
    ],
  },
  {
    title: "Validation",
    keys: ["dsr", "psr", "validation_only", "n_periods"],
  },
  {
    title: "Execution",
    keys: [
      "order_count", "submitted_order_count", "orders_filled_count",
      "fill_count", "real_fill_count", "partial_fill_count",
      "pending_fill_event_count", "fill_rate", "fill_notional_usd",
      "total_fees",
    ],
  },
  {
    title: "Portfolio / Funding",
    keys: [
      "win_rate", "profit_factor", "min_equity", "last_equity",
      "funding_cashflow", "funding_settlement_count",
    ],
  },
  {
    title: "Terminal Closeout",
    keys: [
      "bankrupt", "terminal_open_position_count",
      "terminal_liquidation_fill_count", "terminal_liquidation_notional_usd",
    ],
  },
];

function MetricsGlossaryView() {
  const descriptions = window.METRIC_DESCRIPTIONS || {};
  const grouped = new Set(METRIC_GROUPS.flatMap((group) => group.keys));
  const extraKeys = Object.keys(descriptions)
    .filter((key) => !grouped.has(key))
    .sort();
  const groups = extraKeys.length
    ? [...METRIC_GROUPS, { title: "Other", keys: extraKeys }]
    : METRIC_GROUPS;

  return html`
    <div class="col" style=${{ gap: "var(--gap-lg)" }}>
      <div class="card">
        <div class="card-h">
          <div>
            <div class="card-title">Metrics Glossary</div>
            <div class="card-sub">analytics/performance.py + replay artifact fields</div>
          </div>
          <span class="chip">${Object.keys(descriptions).length} terms</span>
        </div>
        <div class="metrics-glossary">
          ${groups.map((group) => html`
            <section key=${group.title} class="metrics-section">
              <div class="section-h">
                <h2>${group.title}</h2>
              </div>
              <div class="metrics-grid">
                ${group.keys.filter((key) => descriptions[key]).map((key) => {
                  const entry = descriptions[key];
                  return html`
                    <div key=${key} class="metric-definition">
                      <div class="metric-definition-name mono">${key}</div>
                      <div class="metric-definition-title">${metricLabel(key)}</div>
                      <div class="metric-definition-desc">${entry.desc}</div>
                      <div class="metric-definition-unit mono">Unit: ${entry.unit}</div>
                    </div>
                  `;
                })}
              </div>
            </section>
          `)}
        </div>
      </div>
    </div>
  `;
}

window.MetricsGlossaryView = MetricsGlossaryView;
