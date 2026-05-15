// Tiny SVG chart primitives — no third-party libs.
import { h } from 'preact';
import { useState, useRef, useCallback } from 'preact/hooks';
import { html } from 'htm/preact';

// Minimum brush selection in data-indices below which we treat the gesture as a click (no zoom).
const MIN_BRUSH_WIDTH = 2;

function clampIdx(i, lo, hi) {
  if (!Number.isFinite(i)) return lo;
  return Math.max(lo, Math.min(hi, Math.round(i)));
}

// Coerce a chart label (datetime string, ms number, or seconds number) to ms.
// Returns NaN when the value can't be parsed so callers can skip the row.
function tsToMs(label) {
  if (label == null || label === "") return NaN;
  if (typeof label === "number") {
    if (!Number.isFinite(label)) return NaN;
    return label > 1e12 ? label : label * 1000;
  }
  if (typeof label === "string" && /^\d+$/.test(label)) {
    const n = +label;
    return n > 1e12 ? n : n * 1000;
  }
  const t = new Date(label).getTime();
  return Number.isFinite(t) ? t : NaN;
}

// Convert a [startMs, endMs] time range to the local index slice of `timestamps`
// that falls inside it. Each chart resolves the global timestamp range against
// its own (possibly downsampled) label array so brushes stay aligned across
// charts that fetched different n= sample counts.
function rangeToSlice(rangeMs, timestamps) {
  const len = timestamps?.length || 0;
  const last = Math.max(0, len - 1);
  if (!rangeMs || !Array.isArray(rangeMs) || len === 0) return [0, last];
  let [startMs, endMs] = rangeMs;
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return [0, last];
  if (endMs < startMs) [startMs, endMs] = [endMs, startMs];
  let visibleStart = -1;
  let visibleEnd = -1;
  for (let i = 0; i < len; i++) {
    const ms = tsToMs(timestamps[i]);
    if (!Number.isFinite(ms)) continue;
    if (visibleStart < 0 && ms >= startMs) visibleStart = i;
    if (ms <= endMs) visibleEnd = i;
  }
  if (visibleStart < 0) visibleStart = 0;
  if (visibleEnd < 0) visibleEnd = last;
  if (visibleEnd < visibleStart) {
    [visibleStart, visibleEnd] = [Math.min(visibleStart, last), Math.min(visibleStart, last)];
  }
  return [visibleStart, visibleEnd];
}

// Map a clientX into a local data index for a chart that uses [padL, padL+innerW]
// to render the slice [visibleStart..visibleEnd] in absolute indices.
function pointerToAbsoluteIdx(e, { w, padL, innerW, visibleStart, visibleEnd }) {
  const box = e.currentTarget.getBoundingClientRect();
  const viewX = ((e.clientX - box.left) / Math.max(box.width, 1)) * w;
  const visibleLen = Math.max(visibleEnd - visibleStart, 1);
  const rel = ((viewX - padL) / Math.max(innerW, 1)) * visibleLen;
  return clampIdx(visibleStart + rel, visibleStart, visibleEnd);
}

// Build a [startMs, endMs] payload from a brush selection. Returns null when
// the chart has no usable timestamps, so brush gestures on label-less charts
// become no-ops instead of zeroing the global range.
function brushIdxToTsRange(loIdx, hiIdx, timestamps) {
  if (!timestamps || !timestamps.length) return null;
  const startMs = tsToMs(timestamps[loIdx]);
  const endMs = tsToMs(timestamps[hiIdx]);
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return null;
  return [Math.min(startMs, endMs), Math.max(startMs, endMs)];
}

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

function downsamplePoints(points, target) {
  if (points.length <= target) return points;
  const step = points.length / target;
  const out = [];
  for (let i = 0; i < target; i++) {
    out.push(points[Math.floor(i * step)]);
  }
  out.push(points[points.length - 1]);
  return out;
}

const SYMBOL_COLORS = [
  "#2563eb",
  "#dc2626",
  "#059669",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#db2777",
  "#4f46e5",
];

function stableSymbolColor(symbol, index = 0) {
  return SYMBOL_COLORS[Math.abs(index) % SYMBOL_COLORS.length];
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

function money(v) {
  if (v == null || !Number.isFinite(+v)) return "--";
  return `$${Math.abs(+v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function compactQty(v) {
  if (v == null || !Number.isFinite(+v)) return "--";
  return (+v).toLocaleString(undefined, { maximumFractionDigits: 6 });
}

function indexedValue(price, base, indexed) {
  if (!indexed) return price;
  if (!Number.isFinite(+price) || !Number.isFinite(+base) || +base === 0) return NaN;
  return (+price / +base) * 100;
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
    const notional = group.rows.reduce((sum, row) => {
      const value = +row.notional_usd;
      if (Number.isFinite(value) && value > 0) return sum + Math.abs(value);
      const fallback = Math.abs((+row.price || 0) * (+row.qty || 0));
      return Number.isFinite(fallback) ? sum + fallback : sum;
    }, 0);
    const avgPrice = weightedAverage(group.rows, "actual_price", "qty");
    const pnlValues = group.rows.map((row) => +row.net_realized_pnl).filter(Number.isFinite);
    const dayPnlValues = group.rows.map((row) => +row.day_pnl).filter(Number.isFinite);
    const uniquePnl = [...new Map(pnlValues.map((v) => [v.toFixed(8), v])).values()];
    return {
      ...group,
      count: group.rows.length,
      qty,
      notional,
      avgPrice,
      pnl: uniquePnl.reduce((sum, v) => sum + v, 0),
      hasPnl: uniquePnl.length > 0,
      dayPnl: dayPnlValues.length ? dayPnlValues[dayPnlValues.length - 1] : NaN,
      price: Number.isFinite(avgPrice) ? avgPrice : +group.rows[0]?.actual_price,
      plotPrice: +group.rows[0]?.plot_price,
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
  range = null,
  onRangeChange = null,
}) {
  // series: [{ values: number[], color, label }]
  const [hover, setHover] = useState(null);
  const [brush, setBrush] = useState(null); // { startIdx, currentIdx } in absolute indices
  const w = 1000, h = height;
  const hasXLabels = Array.isArray(xLabels) && xLabels.length > 0;
  const padL = 44, padR = 12, padT = 12, padB = hasXLabels ? 36 : 24;
  const innerW = w - padL - padR, innerH = h - padT - padB;

  const cleanSeries = series.map((s) => ({ ...s, values: (s.values || []).map((v) => +v) }));
  const xN = cleanSeries[0]?.values.length || 1;
  // Time-based range: charts with different downsample sizes resolve the same
  // [startMs, endMs] against their own xLabels so the brush stays aligned.
  // Without xLabels we cannot translate ms back to indices, so range is ignored.
  const supportsTimeRange = hasXLabels && xLabels.length === xN;
  const [visibleStart, visibleEnd] = supportsTimeRange
    ? rangeToSlice(range, xLabels)
    : [0, Math.max(xN - 1, 0)];
  const visibleLen = Math.max(visibleEnd - visibleStart + 1, 1);

  const visibleValues = cleanSeries.flatMap((s) =>
    s.values.slice(visibleStart, visibleEnd + 1)
  ).filter((v) => Number.isFinite(v));
  if (!visibleValues.length) return null;
  const yMin = yDomain ? yDomain[0] : Math.min(...visibleValues);
  const yMax = yDomain ? yDomain[1] : Math.max(...visibleValues);
  const yPad = (yMax - yMin) * 0.05 || 0.01;
  const y0 = yMin - yPad, y1 = yMax + yPad;

  // Absolute-index scale (i in [visibleStart..visibleEnd] -> screen X).
  const xScale = (i) => padL + ((i - visibleStart) / Math.max(visibleLen - 1, 1)) * innerW;
  const yScale = (v) => padT + (1 - (v - y0) / (y1 - y0)) * innerH;

  const ticks = 4;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) => y0 + (i / ticks) * (y1 - y0));
  const xTicks = hasXLabels
    ? uniqueTicks(visibleLen, Math.min(5, visibleLen)).map((rel) => visibleStart + rel)
    : [];

  const interactive = typeof onRangeChange === "function";

  function pointerIdx(e) {
    return pointerToAbsoluteIdx(e, { w, padL, innerW, visibleStart, visibleEnd });
  }

  function handlePointerDown(e) {
    if (!interactive) return;
    if (e.button != null && e.button !== 0) return;
    const idx = pointerIdx(e);
    setBrush({ startIdx: idx, currentIdx: idx });
    try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* no-op */ }
  }

  function handlePointerMove(e) {
    const idx = pointerIdx(e);
    if (brush) {
      setBrush({ ...brush, currentIdx: idx });
    } else {
      setHover(idx);
    }
  }

  function handlePointerUp(e) {
    if (!brush) return;
    const lo = Math.min(brush.startIdx, brush.currentIdx);
    const hi = Math.max(brush.startIdx, brush.currentIdx);
    setBrush(null);
    if (interactive && hi - lo >= MIN_BRUSH_WIDTH) {
      const msRange = supportsTimeRange ? brushIdxToTsRange(lo, hi, xLabels) : null;
      if (msRange) onRangeChange(msRange);
    }
  }

  function handlePointerLeave() {
    setHover(null);
    if (brush) setBrush(null);
  }

  const brushLo = brush ? Math.min(brush.startIdx, brush.currentIdx) : null;
  const brushHi = brush ? Math.max(brush.startIdx, brush.currentIdx) : null;

  return html`
    <svg viewBox=${`0 0 ${w} ${h}`} width="100%" height=${h} preserveAspectRatio="none" style=${{ display: "block", maxWidth: "100%", cursor: interactive ? "crosshair" : "default" }}>
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
          <text x=${xScale(idx)} y=${h - 10} font-size="10" text-anchor=${idx === visibleStart ? "start" : idx === visibleEnd ? "end" : "middle"} fill="var(--text-subtle)" font-family="var(--font-mono)">
            ${xTickFormatter(xLabels[idx], idx)}
          </text>
        </g>
      `)}
      ${cleanSeries.map((s, si) => {
        const slice = s.values.slice(visibleStart, visibleEnd + 1);
        const ds = downsample(slice, 240);
        const pts = ds.map(([i, v]) => [
          padL + (i / Math.max(slice.length - 1, 1)) * innerW,
          yScale(v),
        ]);
        const stroke = s.color || color;
        const d = mode === "step" ? stepFromPoints(pts) : lineFromPoints(pts);
        return html`
          <g key=${si}>
            ${mode === "area" && html`<path d=${areaFromPoints(pts, yScale(y0))} fill=${stroke} opacity="0.12" />`}
            <path d=${d} fill="none" stroke=${stroke} stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
          </g>
        `;
      })}
      ${brush && html`
        <rect
          x=${xScale(brushLo)}
          y=${padT}
          width=${Math.max(xScale(brushHi) - xScale(brushLo), 1)}
          height=${innerH}
          fill="var(--accent)"
          opacity="0.14"
          pointer-events="none"
        />
      `}
      ${hover != null && !brush && hover >= visibleStart && hover <= visibleEnd && html`
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
        onPointerDown=${interactive ? handlePointerDown : undefined}
        onPointerMove=${handlePointerMove}
        onPointerUp=${interactive ? handlePointerUp : undefined}
        onPointerLeave=${handlePointerLeave}
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
  symbolColors = {},
  tooltipLabelFormatter = compactDateLabel,
  range = null,
  onRangeChange = null,
}) {
  const [hover, setHover] = useState(null);
  const [brush, setBrush] = useState(null);
  const w = 1000, h = height;
  const padL = 52, padR = 16, padT = 46, padB = 34;
  const innerW = w - padL - padR, innerH = h - padT - padB;

  const rawRows = (prices || [])
    .filter((r) => r.close != null && (r.datetime || r.ts))
    .map((r) => ({
      ...r,
      close: +r.close,
      inst_id: r.inst_id || "Market",
      key: String(r.datetime || r.ts),
    }));
  if (!rawRows.length) return null;

  const sortedKeys = [...new Set(rawRows.map((r) => r.key))].sort(
    (a, b) => new Date(a).getTime() - new Date(b).getTime()
  );
  const byKey = new Map(sortedKeys.map((key, i) => [key, i]));
  const symbols = [...new Set(rawRows.map((r) => r.inst_id))].sort();
  const indexed = symbols.length > 1;
  const series = symbols.map((symbol, i) => {
    const color = symbolColors[symbol] || stableSymbolColor(symbol, i);
    const rows = rawRows
      .filter((r) => r.inst_id === symbol && Number.isFinite(r.close))
      .sort((a, b) => (byKey.get(a.key) ?? 0) - (byKey.get(b.key) ?? 0));
    const base = rows.find((r) => Number.isFinite(r.close))?.close ?? NaN;
    const values = new Map(rows.map((r) => [byKey.get(r.key), indexedValue(r.close, base, indexed)]));
    const rawValues = new Map(rows.map((r) => [byKey.get(r.key), r.close]));
    return {
      symbol,
      color,
      base,
      rows,
      values,
      rawValues,
      points: rows.map((r) => [byKey.get(r.key), indexedValue(r.close, base, indexed)]).filter(([idx, v]) => idx != null && Number.isFinite(v)),
    };
  });
  const baseBySymbol = new Map(series.map((s) => [s.symbol, s.base]));

  // Time-based range resolved per chart against sortedKeys.
  const [visibleStart, visibleEnd] = rangeToSlice(range, sortedKeys);
  const visibleLen = Math.max(visibleEnd - visibleStart + 1, 1);
  const inVisibleRange = (idx) => idx >= visibleStart && idx <= visibleEnd;

  const yVals = series.flatMap((s) => s.points.filter(([idx]) => inVisibleRange(idx)).map(([, value]) => value)).filter((v) => Number.isFinite(v));
  const markerVals = (markers || [])
    .map((m) => indexedValue(+m.price, baseBySymbol.get(m.inst_id), indexed))
    .filter((v) => Number.isFinite(v));
  const allY = [...yVals, ...(yVals.length ? [] : markerVals)];
  const yMin = allY.length ? Math.min(...allY) : 0;
  const yMax = allY.length ? Math.max(...allY) : 1;
  const yPad = (yMax - yMin) * 0.06 || Math.max(Math.abs(yMax) * 0.01, 1);
  const y0 = yMin - yPad, y1 = yMax + yPad;
  const xScale = (i) => padL + ((i - visibleStart) / Math.max(visibleLen - 1, 1)) * innerW;
  const yScale = (v) => padT + (1 - (v - y0) / (y1 - y0)) * innerH;
  const yTicks = Array.from({ length: 5 }, (_, i) => y0 + (i / 4) * (y1 - y0));
  const xTicks = uniqueTicks(visibleLen, Math.min(5, visibleLen)).map((rel) => visibleStart + rel);
  const plottedMarkers = (markers || [])
    .map((m) => {
      const key = String(m.datetime || m.ts || "");
      let idx = byKey.get(key);
      if (idx == null) {
        const t = new Date(key).getTime();
        if (Number.isFinite(t)) {
          let best = 0, bestDiff = Infinity;
          sortedKeys.forEach((rowKey, i) => {
            const rt = new Date(rowKey).getTime();
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
      const actualPrice = +m.price;
      return {
        ...m,
        idx,
        actual_price: actualPrice,
        plot_price: indexedValue(actualPrice, baseBySymbol.get(m.inst_id), indexed),
        price: actualPrice,
        notional_usd: +m.notional_usd,
      };
    })
    .filter((m) => Number.isFinite(m.plot_price))
    .filter(Boolean);
  const markerGroups = aggregateTradeMarkers(plottedMarkers);

  function markerFill(m) {
    const symbolIndex = symbols.indexOf(m.inst_id);
    return symbolColors[m.inst_id] || stableSymbolColor(m.inst_id, Math.max(symbolIndex, 0));
  }

  function markerStroke(m) {
    return String(m.side || "").toLowerCase() === "buy" ? "var(--profit)" : "var(--loss)";
  }

  const interactive = typeof onRangeChange === "function";

  function pointerIdx(e) {
    return pointerToAbsoluteIdx(e, { w, padL, innerW, visibleStart, visibleEnd });
  }

  function handlePointerDown(e) {
    if (!interactive) return;
    if (e.button != null && e.button !== 0) return;
    const idx = pointerIdx(e);
    setBrush({ startIdx: idx, currentIdx: idx });
    try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* no-op */ }
  }

  function handlePointerMove(e) {
    const idx = pointerIdx(e);
    if (brush) {
      setBrush({ ...brush, currentIdx: idx });
    } else {
      setHover(idx);
    }
  }

  function handlePointerUp() {
    if (!brush) return;
    const lo = Math.min(brush.startIdx, brush.currentIdx);
    const hi = Math.max(brush.startIdx, brush.currentIdx);
    setBrush(null);
    if (interactive && hi - lo >= MIN_BRUSH_WIDTH) {
      const msRange = brushIdxToTsRange(lo, hi, sortedKeys);
      if (msRange) onRangeChange(msRange);
    }
  }

  function handlePointerLeave() {
    setHover(null);
    if (brush) setBrush(null);
  }

  const brushLo = brush ? Math.min(brush.startIdx, brush.currentIdx) : null;
  const brushHi = brush ? Math.max(brush.startIdx, brush.currentIdx) : null;
  const hoverInRange = hover != null && hover >= visibleStart && hover <= visibleEnd && !brush;
  const hoverMarkerGroups = !hoverInRange ? [] : markerGroups.filter((m) => Math.abs(m.idx - hover) <= 1).slice(0, 3);
  const tooltipW = 360;
  const tooltipX = !hoverInRange ? 0 : Math.min(xScale(hover) + 12, w - tooltipW - 8);
  const hoverPrices = !hoverInRange ? [] : series
    .map((s) => ({ symbol: s.symbol, color: s.color, value: s.values.get(hover), price: s.rawValues.get(hover) }))
    .filter((row) => Number.isFinite(row.value) || Number.isFinite(row.price));
  const tooltipH = 42 + hoverPrices.length * 16 + hoverMarkerGroups.length * 32;

  return html`
    <svg viewBox=${`0 0 ${w} ${h}`} width="100%" height=${h} preserveAspectRatio="none" style=${{ display: "block", maxWidth: "100%", cursor: interactive ? "crosshair" : "default" }}>
      ${series.length > 0 && html`
        <g transform=${`translate(${w / 2}, 18)`}>
          ${series.map((s, i) => {
            const legendW = 132;
            const x = (i - (series.length - 1) / 2) * legendW;
            return html`
              <g key=${s.symbol} transform=${`translate(${x}, 0)`}>
                <line x1="-52" x2="-28" y1="0" y2="0" stroke=${s.color} stroke-width="2.4" stroke-linecap="round" />
                <text x="-22" y="4" font-size="11" fill="var(--text)" font-family="var(--font-mono)" font-weight="600">
                  ${s.symbol}
                </text>
              </g>
            `;
          })}
        </g>
      `}
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
          <text x=${xScale(idx)} y=${h - 10} font-size="10" text-anchor=${idx === visibleStart ? "start" : idx === visibleEnd ? "end" : "middle"} fill="var(--text-subtle)" font-family="var(--font-mono)">
            ${compactDateLabel(sortedKeys[idx])}
          </text>
        </g>
      `)}
      ${series.map((s) => {
        const visiblePoints = s.points.filter(([idx]) => inVisibleRange(idx));
        const pts = downsamplePoints(visiblePoints, 360).map(([idx, v]) => [xScale(idx), yScale(v)]);
        return html`
          <path
            key=${s.symbol}
            d=${lineFromPoints(pts)}
            fill="none"
            stroke=${s.color}
            stroke-width="1.7"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
        `;
      })}
      ${plottedMarkers.filter((m) => inVisibleRange(m.idx)).map((m, i) => {
        const buy = String(m.side || "").toLowerCase() === "buy";
        const x = xScale(m.idx);
        const y = yScale(m.plot_price);
        return html`
          <g key=${i}>
            <path
              d=${buy ? `M${x},${y - 8} L${x - 5},${y + 2} L${x + 5},${y + 2} Z` : `M${x},${y + 8} L${x - 5},${y - 2} L${x + 5},${y - 2} Z`}
              fill=${markerFill(m)}
              stroke=${markerStroke(m)}
              stroke-width="1.5"
            />
          </g>
        `;
      })}
      ${brush && html`
        <rect
          x=${xScale(brushLo)}
          y=${padT}
          width=${Math.max(xScale(brushHi) - xScale(brushLo), 1)}
          height=${innerH}
          fill="var(--accent)"
          opacity="0.14"
          pointer-events="none"
        />
      `}
      ${hoverInRange && html`
        <g>
          <line x1=${xScale(hover)} x2=${xScale(hover)} y1=${padT} y2=${h - padB} stroke="var(--text-muted)" stroke-dasharray="3 4" />
          ${hoverPrices.map((row) => html`
            ${Number.isFinite(row.value) && html`<circle key=${row.symbol} cx=${xScale(hover)} cy=${yScale(row.value)} r="3.5" fill=${row.color} stroke="var(--surface)" stroke-width="1.5" />`}
          `)}
          <g transform=${`translate(${tooltipX}, ${padT + 8})`}>
            <rect width=${tooltipW} height=${tooltipH} rx="6" fill="var(--surface)" stroke="var(--border-strong)" />
            <text x="10" y="18" font-size="11" fill="var(--text-muted)" font-family="var(--font-mono)">
              ${tooltipLabelFormatter(sortedKeys[hover])}
            </text>
            ${hoverPrices.map((row, i) => html`
              <text key=${row.symbol} x="10" y=${36 + i * 16} font-size="10.5" fill=${row.color} font-family="var(--font-mono)">
                ${`${row.symbol}: ${defaultTooltipValue(row.price)}${indexed ? ` | ${defaultTooltipValue(row.value)}` : ""}`}
              </text>
            `)}
            ${hoverMarkerGroups.map((m, i) => html`
              <text key=${`a-${i}`} x="10" y=${58 + hoverPrices.length * 16 + i * 32} font-size="10.5" fill=${markerStroke(m)} font-family="var(--font-mono)">
                ${`${m.inst_id} ${m.side === "buy" ? "BUY" : "SELL"} ${m.count > 1 ? `${m.count} fills` : "1 fill"} | Qty ${compactQty(m.qty)} | Avg ${defaultTooltipValue(m.avgPrice)}`}
              </text>
              <text key=${`b-${i}`} x="10" y=${72 + hoverPrices.length * 16 + i * 32} font-size="10.5" fill="var(--text-muted)" font-family="var(--font-mono)">
                ${`Notional ${money(m.notional)} USDT | Trade PnL ${m.hasPnl ? signedMoney(m.pnl) : "--"}`}
              </text>
            `)}
          </g>
        </g>
      `}
      <rect
        x=${padL}
        y=${padT}
        width=${innerW}
        height=${innerH}
        fill="transparent"
        onPointerDown=${interactive ? handlePointerDown : undefined}
        onPointerMove=${handlePointerMove}
        onPointerUp=${interactive ? handlePointerUp : undefined}
        onPointerLeave=${handlePointerLeave}
      />
    </svg>
  `;
}

// Indicator chart: price + fast/slow lines + trade markers, optional MACD sub-panel.
// Mirrors the brush-zoom behavior used by LineChart / TradePriceChart so it stays
// in sync with the global chartRange wired from RunDetailView.
function IndicatorChart({
  symbol,
  timestamps,
  prices,
  fast,
  slow,
  fastLabel = "Fast",
  slowLabel = "Slow",
  macd,
  macdSignal,
  macdHistogram,
  markers = [],
  height = 320,
  macdHeight = 110,
  color = "var(--accent)",
  fastColor = "#2563eb",
  slowColor = "#dc2626",
  range = null,
  onRangeChange = null,
  tooltipLabelFormatter = compactDateLabel,
}) {
  const hasMacd = Array.isArray(macd) && macd.length > 0 && Array.isArray(macdSignal);
  const totalH = hasMacd ? height + macdHeight : height;
  const mainH = hasMacd ? height : totalH;
  const w = 1000;
  const padL = 52, padR = 16, padT = 32, padB = hasMacd ? 6 : 28;
  const innerW = w - padL - padR;
  const innerH = mainH - padT - padB;
  const macdPadT = 8, macdPadB = 26;
  const macdInnerH = Math.max(macdHeight - macdPadT - macdPadB, 1);
  const macdYTop = mainH + macdPadT;

  const [hover, setHover] = useState(null);
  const [brush, setBrush] = useState(null);

  const tsLen = timestamps?.length || 0;
  const [visibleStart, visibleEnd] = rangeToSlice(range, timestamps || []);
  const visibleLen = Math.max(visibleEnd - visibleStart + 1, 1);
  const inVisibleRange = (idx) => idx >= visibleStart && idx <= visibleEnd;

  const allSeries = [
    { values: prices, color, label: symbol || "Price" },
    { values: fast, color: fastColor, label: fastLabel },
    { values: slow, color: slowColor, label: slowLabel },
  ].filter((s) => Array.isArray(s.values) && s.values.length > 0);
  const visiblePriceVals = allSeries.flatMap((s) =>
    s.values.slice(visibleStart, visibleEnd + 1)
  ).filter((v) => Number.isFinite(v));
  if (!visiblePriceVals.length) return null;
  const yMin = Math.min(...visiblePriceVals);
  const yMax = Math.max(...visiblePriceVals);
  const yPad = (yMax - yMin) * 0.05 || Math.max(Math.abs(yMax) * 0.01, 1);
  const y0 = yMin - yPad, y1 = yMax + yPad;
  const xScale = (i) => padL + ((i - visibleStart) / Math.max(visibleLen - 1, 1)) * innerW;
  const yScale = (v) => padT + (1 - (v - y0) / (y1 - y0)) * innerH;

  // MACD sub-panel domain
  let macdY0 = 0, macdY1 = 0, macdYScale = null;
  if (hasMacd) {
    const macdSlice = [...macd, ...macdSignal, ...(macdHistogram || [])]
      .map((_, i) => i)
      .filter((i) => inVisibleRange(i));
    const macdVals = [];
    for (const arr of [macd, macdSignal, macdHistogram]) {
      if (!Array.isArray(arr)) continue;
      for (const i of macdSlice) {
        const v = +arr[i];
        if (Number.isFinite(v)) macdVals.push(v);
      }
    }
    if (macdVals.length) {
      const mMin = Math.min(...macdVals, 0);
      const mMax = Math.max(...macdVals, 0);
      const mPad = (mMax - mMin) * 0.1 || Math.max(Math.abs(mMax) * 0.05, 0.0001);
      macdY0 = mMin - mPad;
      macdY1 = mMax + mPad;
      macdYScale = (v) => macdYTop + (1 - (v - macdY0) / Math.max(macdY1 - macdY0, 1e-9)) * macdInnerH;
    }
  }

  const yTicks = Array.from({ length: 5 }, (_, i) => y0 + (i / 4) * (y1 - y0));
  const xTicks = uniqueTicks(visibleLen, Math.min(5, visibleLen)).map((rel) => visibleStart + rel);

  const interactive = typeof onRangeChange === "function";

  function pointerIdx(e) {
    return pointerToAbsoluteIdx(e, { w, padL, innerW, visibleStart, visibleEnd });
  }
  function handlePointerDown(e) {
    if (!interactive || (e.button != null && e.button !== 0)) return;
    const idx = pointerIdx(e);
    setBrush({ startIdx: idx, currentIdx: idx });
    try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* no-op */ }
  }
  function handlePointerMove(e) {
    const idx = pointerIdx(e);
    if (brush) setBrush({ ...brush, currentIdx: idx });
    else setHover(idx);
  }
  function handlePointerUp() {
    if (!brush) return;
    const lo = Math.min(brush.startIdx, brush.currentIdx);
    const hi = Math.max(brush.startIdx, brush.currentIdx);
    setBrush(null);
    if (interactive && hi - lo >= MIN_BRUSH_WIDTH) {
      const msRange = brushIdxToTsRange(lo, hi, timestamps || []);
      if (msRange) onRangeChange(msRange);
    }
  }
  function handlePointerLeave() {
    setHover(null);
    if (brush) setBrush(null);
  }

  const brushLo = brush ? Math.min(brush.startIdx, brush.currentIdx) : null;
  const brushHi = brush ? Math.max(brush.startIdx, brush.currentIdx) : null;
  const hoverInRange = hover != null && hover >= visibleStart && hover <= visibleEnd && !brush;

  function markerStroke(m) {
    return String(m.side || "").toLowerCase() === "buy" ? "var(--profit)" : "var(--loss)";
  }

  return html`
    <svg viewBox=${`0 0 ${w} ${totalH}`} width="100%" height=${totalH} preserveAspectRatio="none" style=${{ display: "block", maxWidth: "100%", cursor: interactive ? "crosshair" : "default" }}>
      <g transform=${`translate(${padL}, 14)`}>
        <text x="0" y="0" font-size="12" fill="var(--text)" font-family="var(--font-mono)" font-weight="600">${symbol || ""}</text>
        ${allSeries.map((s, i) => html`
          <g key=${i} transform=${`translate(${120 + i * 120}, -3)`}>
            <line x1="0" x2="22" y1="0" y2="0" stroke=${s.color} stroke-width="2.4" />
            <text x="28" y="4" font-size="11" fill="var(--text-muted)" font-family="var(--font-mono)">${s.label}</text>
          </g>
        `)}
      </g>
      ${yTicks.map((t, i) => html`
        <g key=${`y-${i}`}>
          <line x1=${padL} x2=${w - padR} y1=${yScale(t)} y2=${yScale(t)} stroke="var(--border)" stroke-dasharray="2 4" />
          <text x=${padL - 8} y=${yScale(t) + 3} font-size="10" text-anchor="end" fill="var(--text-subtle)" font-family="var(--font-mono)">${Math.abs(t) > 100 ? t.toFixed(0) : t.toFixed(2)}</text>
        </g>
      `)}
      ${!hasMacd && xTicks.map((idx) => html`
        <g key=${`x-${idx}`}>
          <line x1=${xScale(idx)} x2=${xScale(idx)} y1=${padT} y2=${mainH - padB} stroke="var(--border)" stroke-dasharray="2 4" opacity="0.45" />
          <text x=${xScale(idx)} y=${mainH - 10} font-size="10" text-anchor=${idx === visibleStart ? "start" : idx === visibleEnd ? "end" : "middle"} fill="var(--text-subtle)" font-family="var(--font-mono)">${compactDateLabel(timestamps[idx])}</text>
        </g>
      `)}
      ${allSeries.map((s, si) => {
        const slice = s.values.slice(visibleStart, visibleEnd + 1);
        const ds = downsample(slice, 360);
        const pts = ds.map(([i, v]) => [padL + (i / Math.max(slice.length - 1, 1)) * innerW, yScale(v)])
          .filter(([, y]) => Number.isFinite(y));
        return html`<path key=${si} d=${lineFromPoints(pts)} fill="none" stroke=${s.color} stroke-width=${si === 0 ? 1.6 : 1.4} stroke-linejoin="round" stroke-linecap="round" opacity=${si === 0 ? 0.95 : 0.85} />`;
      })}
      ${(markers || []).filter((m) => inVisibleRange(m.idx) && Number.isFinite(+m.price)).map((m, i) => {
        const buy = String(m.side || "").toLowerCase() === "buy";
        const x = xScale(m.idx);
        const y = yScale(+m.price);
        return html`
          <g key=${i}>
            <path
              d=${buy ? `M${x},${y - 8} L${x - 5},${y + 2} L${x + 5},${y + 2} Z` : `M${x},${y + 8} L${x - 5},${y - 2} L${x + 5},${y - 2} Z`}
              fill=${color}
              stroke=${markerStroke(m)}
              stroke-width="1.5"
            />
          </g>
        `;
      })}
      ${hasMacd && macdYScale && html`
        <g>
          <line x1=${padL} x2=${w - padR} y1=${macdYScale(0)} y2=${macdYScale(0)} stroke="var(--border-strong)" />
          ${(macdHistogram || []).map((v, i) => {
            if (!inVisibleRange(i) || !Number.isFinite(+v)) return null;
            const x = xScale(i);
            const yZero = macdYScale(0);
            const yVal = macdYScale(+v);
            const top = Math.min(yZero, yVal);
            const barH = Math.max(Math.abs(yVal - yZero), 1);
            const fill = +v >= 0 ? "var(--profit)" : "var(--loss)";
            const barW = Math.max(innerW / Math.max(visibleLen, 1) * 0.7, 1);
            return html`<rect key=${i} x=${x - barW / 2} y=${top} width=${barW} height=${barH} fill=${fill} opacity="0.55" />`;
          })}
          ${[
            { values: macd, color: fastColor },
            { values: macdSignal, color: slowColor },
          ].map((s, si) => {
            const slice = s.values.slice(visibleStart, visibleEnd + 1);
            const ds = downsample(slice, 360);
            const pts = ds.map(([i, v]) => [padL + (i / Math.max(slice.length - 1, 1)) * innerW, macdYScale(+v)])
              .filter(([, y]) => Number.isFinite(y));
            return html`<path key=${`macd-${si}`} d=${lineFromPoints(pts)} fill="none" stroke=${s.color} stroke-width="1.3" />`;
          })}
          ${xTicks.map((idx) => html`
            <text key=${`mx-${idx}`} x=${xScale(idx)} y=${macdYTop + macdInnerH + 16} font-size="10" text-anchor=${idx === visibleStart ? "start" : idx === visibleEnd ? "end" : "middle"} fill="var(--text-subtle)" font-family="var(--font-mono)">${compactDateLabel(timestamps[idx])}</text>
          `)}
        </g>
      `}
      ${brush && html`
        <rect
          x=${xScale(brushLo)}
          y=${padT}
          width=${Math.max(xScale(brushHi) - xScale(brushLo), 1)}
          height=${(hasMacd ? mainH + macdInnerH + macdPadT - padT : innerH)}
          fill="var(--accent)"
          opacity="0.14"
          pointer-events="none"
        />
      `}
      ${hoverInRange && html`
        <g>
          <line x1=${xScale(hover)} x2=${xScale(hover)} y1=${padT} y2=${hasMacd ? macdYTop + macdInnerH : mainH - padB} stroke="var(--text-muted)" stroke-dasharray="3 4" />
          <g transform=${`translate(${Math.min(xScale(hover) + 12, w - 240)}, ${padT + 4})`}>
            <rect width="228" height=${36 + allSeries.length * 16 + (hasMacd ? 32 : 0)} rx="6" fill="var(--surface)" stroke="var(--border-strong)" />
            <text x="10" y="18" font-size="11" fill="var(--text-muted)" font-family="var(--font-mono)">${tooltipLabelFormatter(timestamps[hover])}</text>
            ${allSeries.map((s, si) => {
              const value = s.values[hover];
              if (!Number.isFinite(value)) return null;
              return html`
                <g key=${si} transform=${`translate(10, ${36 + si * 16})`}>
                  <circle cx="0" cy="-4" r="3" fill=${s.color} />
                  <text x="10" y="0" font-size="11" fill="var(--text)" font-family="var(--font-mono)">${s.label}: ${defaultTooltipValue(value)}</text>
                </g>
              `;
            })}
            ${hasMacd && html`
              <text x="10" y=${36 + allSeries.length * 16 + 14} font-size="11" fill="var(--text-muted)" font-family="var(--font-mono)">
                MACD ${defaultTooltipValue(macd[hover])} | sig ${defaultTooltipValue(macdSignal[hover])}
              </text>
            `}
          </g>
        </g>
      `}
      <rect
        x=${padL}
        y=${padT}
        width=${innerW}
        height=${hasMacd ? mainH - padT - padB + macdInnerH + macdPadT : innerH}
        fill="transparent"
        onPointerDown=${interactive ? handlePointerDown : undefined}
        onPointerMove=${handlePointerMove}
        onPointerUp=${interactive ? handlePointerUp : undefined}
        onPointerLeave=${handlePointerLeave}
      />
    </svg>
  `;
}

window.Charts = { LineChart, Sparkline, BarChart, HistogramChart, TradePriceChart, IndicatorChart };
