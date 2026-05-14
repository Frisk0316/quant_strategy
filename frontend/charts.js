// Tiny SVG chart primitives — no third-party libs.
import { h } from 'preact';
import { useState } from 'preact/hooks';
import { html } from 'htm/preact';

function lineFromPoints(pts) {
  return pts.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(" ");
}
function stepFromPoints(pts) {
  let d = "";
  pts.forEach((p, i) => {
    if (i === 0) d += `M${p[0]},${p[1]}`;
    else d += `L${p[0]},${pts[i - 1][1]}L${p[0]},${p[1]}`;
  });
  return d;
}
function areaFromPoints(pts, baselineY) {
  if (!pts.length) return "";
  const head = `M${pts[0][0]},${baselineY}`;
  const body = pts.map((p) => `L${p[0]},${p[1]}`).join("");
  const tail = `L${pts[pts.length - 1][0]},${baselineY}Z`;
  return head + body + tail;
}

function downsample(arr, target) {
  if (arr.length <= target) return arr.map((v, i) => [i, v]);
  const step = arr.length / target;
  const out = [];
  for (let i = 0; i < target; i++) {
    const idx = Math.floor(i * step);
    out.push([idx, arr[idx]]);
  }
  out.push([arr.length - 1, arr[arr.length - 1]]);
  return out;
}

function compactDateLabel(value) {
  if (value == null || value === "") return "";
  const d = new Date(value);
  if (isNaN(d.getTime())) return String(value);
  return d.toISOString().slice(0, 10);
}

function defaultTooltipValue(v) {
  if (v == null || isNaN(+v)) return "--";
  return Math.abs(+v) > 100 ? (+v).toLocaleString(undefined, { maximumFractionDigits: 2 }) : (+v).toFixed(4);
}

function signedMoney(v) {
  if (v == null || !Number.isFinite(+v)) return "--";
  const n = +v;
  const sign = n > 0 ? "+" : n < 0 ? "-" : "";
  return `${sign}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function compactQty(v) {
  if (v == null || !Number.isFinite(+v)) return "--";
  return (+v).toLocaleString(undefined, { maximumFractionDigits: 6 });
}

function weightedAverage(rows, valueKey, weightKey) {
  let weighted = 0;
  let weight = 0;
  for (const row of rows) {
    const value = +row[valueKey];
    const qty = Math.abs(+row[weightKey]);
    if (Number.isFinite(value) && Number.isFinite(qty) && qty > 0) {
      weighted += value * qty;
      weight += qty;
    }
  }
  return weight > 0 ? weighted / weight : NaN;
}

function aggregateTradeMarkers(markers) {
  const groups = new Map();
  for (const marker of markers || []) {
    const side = String(marker.side || "").toLowerCase() === "buy" ? "buy" : "sell";
    const key = `${marker.idx}-${marker.inst_id || ""}-${side}`;
    if (!groups.has(key)) {
      groups.set(key, { idx: marker.idx, inst_id: marker.inst_id || "", side, rows: [] });
    }
    groups.get(key).rows.push(marker);
  }
  return [...groups.values()].map((group) => {
    const qty = group.rows.reduce((sum, row) => sum + (Number.isFinite(+row.qty) ? Math.abs(+row.qty) : 0), 0);
    const avgPrice = weightedAverage(group.rows, "price", "qty");
    const pnlValues = group.rows.map((row) => +row.net_realized_pnl).filter(Number.isFinite);
    const dayPnlValues = group.rows.map((row) => +row.day_pnl).filter(Number.isFinite);
    const uniquePnl = [...new Map(pnlValues.map((v) => [v.toFixed(8), v])).values()];
    return {
      ...group,
      count: group.rows.length,
      qty,
      avgPrice,
      pnl: uniquePnl.reduce((sum, v) => sum + v, 0),
      hasPnl: uniquePnl.length > 0,
      dayPnl: dayPnlValues.length ? dayPnlValues[dayPnlValues.length - 1] : NaN,
      price: Number.isFinite(avgPrice) ? avgPrice : +group.rows[0]?.price,
    };
  });
}

function uniqueTicks(count, maxTicks) {
  if (count <= 0) return [];
  if (count === 1) return [0];
  const ticks = [];
  for (let i = 0; i < maxTicks; i++) {
    ticks.push(Math.round((i / (maxTicks - 1)) * (count - 1)));
  }
  return [...new Set(ticks)];
}

function LineChart({
  series,
  height = 220,
  mode = "line",
  color = "var(--accent)",
  showAxes = true,
  yDomain,
  xLabels,
  xTickFormatter = compactDateLabel,
  tooltipLabelFormatter = compactDateLabel,
  tooltipValueFormatter = defaultTooltipValue,
}) {
  // series: [{ values: number[], color, label }]
  const [hover, setHover] = useState(null);
  const w = 1000, h = height;
  const hasXLabels = Array.isArray(xLabels) && xLabels.length > 0;
  const padL = 44, padR = 12, padT = 12, padB = hasXLabels ? 36 : 24;
  const innerW = w - padL - padR, innerH = h - padT - padB;

  const cleanSeries = series.map((s) => ({ ...s, values: (s.values || []).map((v) => +v) }));
  const all = cleanSeries.flatMap((s) => s.values).filter((v) => Number.isFinite(v));
  if (!all.length) return null;
  const yMin = yDomain ? yDomain[0] : Math.min(...all);
  const yMax = yDomain ? yDomain[1] : Math.max(...all);
  const yPad = (yMax - yMin) * 0.05 || 0.01;
  const y0 = yMin - yPad, y1 = yMax + yPad;

  const xN = cleanSeries[0]?.values.length || 1;
  const xScale = (i) => padL + (i / Math.max(xN - 1, 1)) * innerW;
  const yScale = (v) => padT + (1 - (v - y0) / (y1 - y0)) * innerH;

  const ticks = 4;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) => y0 + (i / ticks) * (y1 - y0));
  const xTicks = hasXLabels ? uniqueTicks(xN, Math.min(5, xN)) : [];

  function handlePointerMove(e) {
    const box = e.currentTarget.getBoundingClientRect();
    const viewX = ((e.clientX - box.left) / Math.max(box.width, 1)) * w;
    const idx = Math.round(((viewX - padL) / Math.max(innerW, 1)) * Math.max(xN - 1, 0));
    setHover(Math.max(0, Math.min(xN - 1, idx)));
  }

  return html`
    <svg viewBox=${`0 0 ${w} ${h}`} width="100%" height=${h} preserveAspectRatio="none" style=${{ display: "block", maxWidth: "100%" }}>
      ${showAxes && yTicks.map((t, i) => html`
        <g key=${i}>
          <line x1=${padL} x2=${w - padR} y1=${yScale(t)} y2=${yScale(t)} stroke="var(--border)" stroke-dasharray="2 4" />
          <text x=${padL - 8} y=${yScale(t) + 3} font-size="10" text-anchor="end" fill="var(--text-subtle)" font-family="var(--font-mono)">
            ${Math.abs(t) > 100 ? t.toFixed(0) : t.toFixed(2)}
          </text>
        </g>
      `)}
      ${showAxes && xTicks.map((idx) => html`
        <g key=${`x-${idx}`}>
          <line x1=${xScale(idx)} x2=${xScale(idx)} y1=${padT} y2=${h - padB} stroke="var(--border)" stroke-dasharray="2 4" opacity="0.5" />
          <text x=${xScale(idx)} y=${h - 10} font-size="10" text-anchor=${idx === 0 ? "start" : idx === xN - 1 ? "end" : "middle"} fill="var(--text-subtle)" font-family="var(--font-mono)">
            ${xTickFormatter(xLabels[idx], idx)}
          </text>
        </g>
      `)}
      ${cleanSeries.map((s, si) => {
        const ds = downsample(s.values, 240);
        const pts = ds.map(([i, v]) => [xScale(i), yScale(v)]);
        const stroke = s.color || color;
        const d = mode === "step" ? stepFromPoints(pts) : lineFromPoints(pts);
        return html`
          <g key=${si}>
            ${mode === "area" && html`<path d=${areaFromPoints(pts, yScale(y0))} fill=${stroke} opacity="0.12" />`}
            <path d=${d} fill="none" stroke=${stroke} stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
          </g>
        `;
      })}
      ${hover != null && html`
        <g>
          <line x1=${xScale(hover)} x2=${xScale(hover)} y1=${padT} y2=${h - padB} stroke="var(--text-muted)" stroke-dasharray="3 4" />
          ${cleanSeries.map((s, si) => {
            const value = s.values[hover];
            if (!Number.isFinite(value)) return null;
            return html`<circle key=${si} cx=${xScale(hover)} cy=${yScale(value)} r="3.5" fill=${s.color || color} stroke="var(--surface)" stroke-width="1.5" />`;
          })}
          <g transform=${`translate(${Math.min(xScale(hover) + 12, w - 214)}, ${padT + 8})`}>
            <rect width="202" height=${32 + cleanSeries.length * 16} rx="6" fill="var(--surface)" stroke="var(--border-strong)" />
            <text x="10" y="18" font-size="11" fill="var(--text-muted)" font-family="var(--font-mono)">
              ${tooltipLabelFormatter(hasXLabels ? xLabels[hover] : hover, hover)}
            </text>
            ${cleanSeries.map((s, si) => {
              const value = s.values[hover];
              if (!Number.isFinite(value)) return null;
              return html`
                <g key=${si} transform=${`translate(10, ${36 + si * 16})`}>
                  <circle cx="0" cy="-4" r="3" fill=${s.color || color} />
                  <text x="10" y="0" font-size="11" fill="var(--text)" font-family="var(--font-mono)">
                    ${(s.label || "Value") + ": " + tooltipValueFormatter(value, s, hover)}
                  </text>
                </g>
              `;
            })}
          </g>
        </g>
      `}
      <rect
        x=${padL}
        y=${padT}
        width=${innerW}
        height=${innerH}
        fill="transparent"
        onMouseMove=${handlePointerMove}
        onMouseLeave=${() => setHover(null)}
      />
    </svg>
  `;
}

function Sparkline({ values, color = "var(--accent)", height = 36, mode = "line" }) {
  const w = 200, h = height;
  const padT = 4, padB = 4;
  const yMin = Math.min(...values), yMax = Math.max(...values);
  const yPad = (yMax - yMin) * 0.08 || 0.001;
  const y0 = yMin - yPad, y1 = yMax + yPad;
  const ds = downsample(values, 80);
  const pts = ds.map(([i, v], k) => [
    (k / Math.max(ds.length - 1, 1)) * w,
    padT + (1 - (v - y0) / (y1 - y0)) * (h - padT - padB),
  ]);
  return html`
    <svg viewBox=${`0 0 ${w} ${h}`} width="100%" height=${h} preserveAspectRatio="none" style=${{ display: "block", maxWidth: "100%" }}>
      ${mode === "area" && html`<path d=${areaFromPoints(pts, h - padB)} fill=${color} opacity="0.14" />`}
      <path d=${mode === "step" ? stepFromPoints(pts) : lineFromPoints(pts)} fill="none" stroke=${color} stroke-width="1.4" />
    </svg>
  `;
}

function BarChart({ values, height = 160, color = "var(--accent)", labels, threshold }) {
  const w = 1000, h = height;
  const padL = 44, padR = 12, padT = 12, padB = 28;
  const innerW = w - padL - padR, innerH = h - padT - padB;
  const yMax = Math.max(...values, 0.01);
  const yMin = Math.min(...values, 0);
  const y0 = yMin - 0.1 * Math.abs(yMin || 1), y1 = yMax + 0.1 * yMax;
  const yScale = (v) => padT + (1 - (v - y0) / (y1 - y0)) * innerH;
  const xScale = (i) => padL + (i + 0.1) * (innerW / values.length);
  const barW = (innerW / values.length) * 0.8;
  return html`
    <svg viewBox=${`0 0 ${w} ${h}`} width="100%" height=${h} preserveAspectRatio="none" style=${{ display: "block", maxWidth: "100%" }}>
      <line x1=${padL} x2=${w - padR} y1=${yScale(0)} y2=${yScale(0)} stroke="var(--border-strong)" />
      ${threshold != null && html`
        <line x1=${padL} x2=${w - padR} y1=${yScale(threshold)} y2=${yScale(threshold)} stroke="var(--warn)" stroke-dasharray="3 4" />
      `}
      ${values.map((v, i) => {
        const y = yScale(Math.max(v, 0));
        const yEnd = yScale(Math.min(v, 0));
        const fill = v < 0 ? "var(--loss)" : color;
        return html`<rect key=${i} x=${xScale(i)} y=${y} width=${barW} height=${Math.max(yEnd - y, 1)} fill=${fill} rx="1.5" opacity=${v < 0 ? 0.8 : 0.9} />`;
      })}
      ${labels && labels.map((l, i) => html`
        <text key=${i} x=${xScale(i) + barW / 2} y=${h - 8} font-size="10" text-anchor="middle" fill="var(--text-subtle)" font-family="var(--font-mono)">${l}</text>
      `)}
    </svg>
  `;
}

function HistogramChart({ values, bins = 24, height = 140, color = "var(--accent)" }) {
  const min = Math.min(...values), max = Math.max(...values);
  const step = (max - min) / bins || 1;
  const counts = new Array(bins).fill(0);
  values.forEach((v) => {
    const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / step)));
    counts[idx]++;
  });
  return html`<${BarChart} values=${counts} height=${height} color=${color} labels=${null} />`;
}

function TradePriceChart({
  prices,
  markers,
  height = 280,
  tooltipLabelFormatter = compactDateLabel,
}) {
  const [hover, setHover] = useState(null);
  const w = 1000, h = height;
  const padL = 52, padR = 16, padT = 14, padB = 34;
  const innerW = w - padL - padR, innerH = h - padT - padB;

  const rows = (prices || [])
    .filter((r) => r.close != null && (r.datetime || r.ts))
    .map((r) => ({ ...r, close: +r.close, key: String(r.datetime || r.ts) }));
  if (!rows.length) return null;

  const byKey = new Map(rows.map((r, i) => [r.key, i]));
  const yVals = rows.map((r) => r.close).filter((v) => Number.isFinite(v));
  const markerVals = (markers || []).map((m) => +m.price).filter((v) => Number.isFinite(v));
  const allY = [...yVals, ...markerVals];
  const yMin = Math.min(...allY);
  const yMax = Math.max(...allY);
  const yPad = (yMax - yMin) * 0.06 || Math.max(Math.abs(yMax) * 0.01, 1);
  const y0 = yMin - yPad, y1 = yMax + yPad;
  const xScale = (i) => padL + (i / Math.max(rows.length - 1, 1)) * innerW;
  const yScale = (v) => padT + (1 - (v - y0) / (y1 - y0)) * innerH;
  const pts = downsample(rows.map((r) => r.close), 360).map(([i, v]) => [xScale(i), yScale(v)]);
  const yTicks = Array.from({ length: 5 }, (_, i) => y0 + (i / 4) * (y1 - y0));
  const xTicks = uniqueTicks(rows.length, Math.min(5, rows.length));
  const plottedMarkers = (markers || [])
    .map((m) => {
      const key = String(m.datetime || m.ts || "");
      let idx = byKey.get(key);
      if (idx == null) {
        const t = new Date(key).getTime();
        if (Number.isFinite(t)) {
          let best = 0, bestDiff = Infinity;
          rows.forEach((r, i) => {
            const rt = new Date(r.key).getTime();
            const diff = Math.abs(rt - t);
            if (diff < bestDiff) {
              best = i;
              bestDiff = diff;
            }
          });
          idx = best;
        }
      }
      if (idx == null || !Number.isFinite(+m.price)) return null;
      return { ...m, idx, price: +m.price };
    })
    .filter(Boolean);
  const markerGroups = aggregateTradeMarkers(plottedMarkers);

  function markerColor(m) {
    return String(m.side || "").toLowerCase() === "buy" ? "var(--profit)" : "var(--loss)";
  }

  function handlePointerMove(e) {
    const box = e.currentTarget.getBoundingClientRect();
    const viewX = ((e.clientX - box.left) / Math.max(box.width, 1)) * w;
    const idx = Math.round(((viewX - padL) / Math.max(innerW, 1)) * Math.max(rows.length - 1, 0));
    setHover(Math.max(0, Math.min(rows.length - 1, idx)));
  }

  const hoverMarkerGroups = hover == null ? [] : markerGroups.filter((m) => Math.abs(m.idx - hover) <= 1).slice(0, 3);
  const tooltipW = 360;
  const tooltipX = hover == null ? 0 : Math.min(xScale(hover) + 12, w - tooltipW - 8);
  const tooltipH = 58 + hoverMarkerGroups.length * 32;

  return html`
    <svg viewBox=${`0 0 ${w} ${h}`} width="100%" height=${h} preserveAspectRatio="none" style=${{ display: "block", maxWidth: "100%" }}>
      ${yTicks.map((t, i) => html`
        <g key=${i}>
          <line x1=${padL} x2=${w - padR} y1=${yScale(t)} y2=${yScale(t)} stroke="var(--border)" stroke-dasharray="2 4" />
          <text x=${padL - 8} y=${yScale(t) + 3} font-size="10" text-anchor="end" fill="var(--text-subtle)" font-family="var(--font-mono)">
            ${Math.abs(t) > 100 ? t.toFixed(0) : t.toFixed(2)}
          </text>
        </g>
      `)}
      ${xTicks.map((idx) => html`
        <g key=${`x-${idx}`}>
          <line x1=${xScale(idx)} x2=${xScale(idx)} y1=${padT} y2=${h - padB} stroke="var(--border)" stroke-dasharray="2 4" opacity="0.45" />
          <text x=${xScale(idx)} y=${h - 10} font-size="10" text-anchor=${idx === 0 ? "start" : idx === rows.length - 1 ? "end" : "middle"} fill="var(--text-subtle)" font-family="var(--font-mono)">
            ${compactDateLabel(rows[idx]?.key)}
          </text>
        </g>
      `)}
      <path d=${lineFromPoints(pts)} fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />
      ${plottedMarkers.map((m, i) => {
        const buy = String(m.side || "").toLowerCase() === "buy";
        const x = xScale(m.idx);
        const y = yScale(m.price);
        return html`
          <g key=${i}>
            <path
              d=${buy ? `M${x},${y - 8} L${x - 5},${y + 2} L${x + 5},${y + 2} Z` : `M${x},${y + 8} L${x - 5},${y - 2} L${x + 5},${y - 2} Z`}
              fill=${markerColor(m)}
              stroke="var(--surface)"
              stroke-width="1"
            />
          </g>
        `;
      })}
      ${hover != null && html`
        <g>
          <line x1=${xScale(hover)} x2=${xScale(hover)} y1=${padT} y2=${h - padB} stroke="var(--text-muted)" stroke-dasharray="3 4" />
          <circle cx=${xScale(hover)} cy=${yScale(rows[hover].close)} r="3.5" fill="var(--accent)" stroke="var(--surface)" stroke-width="1.5" />
          <g transform=${`translate(${tooltipX}, ${padT + 8})`}>
            <rect width=${tooltipW} height=${tooltipH} rx="6" fill="var(--surface)" stroke="var(--border-strong)" />
            <text x="10" y="18" font-size="11" fill="var(--text-muted)" font-family="var(--font-mono)">
              ${tooltipLabelFormatter(rows[hover].key)}
            </text>
            <text x="10" y="36" font-size="11" fill="var(--text)" font-family="var(--font-mono)">
              Price: ${defaultTooltipValue(rows[hover].close)}
            </text>
            ${hoverMarkerGroups.map((m, i) => html`
              <text key=${`a-${i}`} x="10" y=${58 + i * 32} font-size="10.5" fill=${markerColor(m)} font-family="var(--font-mono)">
                ${`${m.side === "buy" ? "BUY" : "SELL"} ${m.count > 1 ? `${m.count} fills` : "1 fill"} | Qty ${compactQty(m.qty)} | Avg ${defaultTooltipValue(m.avgPrice)}`}
              </text>
              <text key=${`b-${i}`} x="10" y=${72 + i * 32} font-size="10.5" fill="var(--text-muted)" font-family="var(--font-mono)">
                ${`Trade PnL ${m.hasPnl ? signedMoney(m.pnl) : "--"} | Day PnL ${signedMoney(m.dayPnl)}`}
              </text>
            `)}
          </g>
        </g>
      `}
      <rect x=${padL} y=${padT} width=${innerW} height=${innerH} fill="transparent" onMouseMove=${handlePointerMove} onMouseLeave=${() => setHover(null)} />
    </svg>
  `;
}

window.Charts = { LineChart, Sparkline, BarChart, HistogramChart, TradePriceChart };
