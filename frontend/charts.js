// Tiny SVG chart primitives — no third-party libs.
import { h } from 'preact';
import { useState, useRef, useCallback } from 'preact/hooks';
import { html } from 'htm/preact';

// Minimum brush selection in data-indices below which we treat the gesture as a click (no zoom).
const MIN_BRUSH_WIDTH = 2;
const MAX_Y_ZOOM = 8;

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

function adaptiveDateLabel(value, rangeMs) {
  if (value == null || value === "") return "";
  const d = new Date(value);
  if (isNaN(d.getTime())) return String(value);
  const iso = d.toISOString();
  const day = iso.slice(0, 10);
  const time = iso.slice(11, 19);
  const days = 24 * 60 * 60 * 1000;
  const hours = 60 * 60 * 1000;
  const minutes = 60 * 1000;
  if (!Number.isFinite(rangeMs)) return day;
  if (rangeMs >= 365 * days) return iso.slice(0, 7);
  if (rangeMs >= 90 * days) return iso.slice(0, 7);
  if (rangeMs >= 3 * days) return day;
  if (rangeMs >= 6 * hours) return `${iso.slice(5, 10)} ${time.slice(0, 5)}`;
  if (rangeMs >= 30 * minutes) return time.slice(0, 5);
  return time;
}

function visibleRangeMs(timestamps, visibleStart, visibleEnd) {
  if (!timestamps?.length) return NaN;
  const startMs = tsToMs(timestamps[visibleStart]);
  const endMs = tsToMs(timestamps[visibleEnd]);
  return Number.isFinite(startMs) && Number.isFinite(endMs) ? Math.abs(endMs - startMs) : NaN;
}

function calendarTickIndices(timestamps, visibleStart, visibleEnd, maxTicks = 5) {
  const fallback = uniqueTicks(visibleEnd - visibleStart + 1, maxTicks).map((rel) => visibleStart + rel);
  const startMs = tsToMs(timestamps?.[visibleStart]);
  const endMs = tsToMs(timestamps?.[visibleEnd]);
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs) return fallback;

  const dayMs = 24 * 60 * 60 * 1000;
  const rangeMs = endMs - startMs;
  if (rangeMs < 60 * dayMs) return fallback;

  const stepMonths = rangeMs >= 730 * dayMs ? 6 : rangeMs >= 365 * dayMs ? 3 : 1;
  const start = new Date(startMs);
  const cursor = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), 1));
  while (cursor.getTime() < startMs) cursor.setUTCMonth(cursor.getUTCMonth() + stepMonths);

  const targets = [];
  while (cursor.getTime() <= endMs && targets.length < maxTicks * 3) {
    targets.push(cursor.getTime());
    cursor.setUTCMonth(cursor.getUTCMonth() + stepMonths);
  }
  if (!targets.length) return fallback;

  const ticks = [];
  let scan = visibleStart;
  for (const target of targets) {
    while (scan <= visibleEnd && tsToMs(timestamps[scan]) < target) scan += 1;
    if (scan <= visibleEnd) ticks.push(scan);
  }
  const unique = [...new Set(ticks)].filter((idx) => idx >= visibleStart && idx <= visibleEnd);
  if (unique.length > maxTicks) {
    return uniqueTicks(unique.length, maxTicks).map((rel) => unique[rel]);
  }
  return unique.length ? unique : fallback;
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

function applyYZoomDomain(y0, y1, yZoom = 1, yZoomAnchor = "mid") {
  const zoom = Number.isFinite(+yZoom) ? Math.max(1, Math.min(+yZoom, MAX_Y_ZOOM)) : 1;
  if (zoom <= 1) return [y0, y1];
  const anchor = yZoomAnchor === "min"
    ? y0
    : yZoomAnchor === "max"
      ? y1
      : Number.isFinite(+yZoomAnchor)
        ? +yZoomAnchor
        : (y0 + y1) / 2;
  const nextY0 = anchor + (y0 - anchor) / zoom;
  const nextY1 = anchor + (y1 - anchor) / zoom;
  if (Math.abs(nextY1 - nextY0) < 1e-9) return [y0, y1];
  return [nextY0, nextY1];
}

function formatAxisTick(t) {
  if (!Number.isFinite(+t)) return "";
  const v = +t;
  if (Math.abs(v) >= 1000) return v.toFixed(0);
  if (Math.abs(v) >= 100) return v.toFixed(1);
  if (Math.abs(v) >= 1) return v.toFixed(2);
  return v.toFixed(4);
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

function RangeBrush({
  timestamps,
  values,
  range = null,
  onRangeChange = null,
  height = 58,
  color = "var(--accent)",
}) {
  const interactive = typeof onRangeChange === "function";
  const len = timestamps?.length || 0;
  if (!interactive || len < 2) return null;

  const w = 1000, h = height;
  const padL = 52, padR = 16, padT = 8, padB = 14;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const last = len - 1;
  const [rangeStart, rangeEnd] = rangeToSlice(range, timestamps);
  const [draft, setDraft] = useState(null);
  const [drag, setDrag] = useState(null);
  const windowStart = draft ? draft.start : rangeStart;
  const windowEnd = draft ? draft.end : rangeEnd;

  const cleanValues = (values || []).slice(0, len).map((v) => +v);
  const finiteValues = cleanValues.filter(Number.isFinite);
  const yMin = finiteValues.length ? Math.min(...finiteValues) : 0;
  const yMax = finiteValues.length ? Math.max(...finiteValues) : 1;
  const yPad = (yMax - yMin) * 0.08 || Math.max(Math.abs(yMax) * 0.01, 1);
  const y0 = yMin - yPad, y1 = yMax + yPad;
  const xScale = (i) => padL + (i / Math.max(last, 1)) * innerW;
  const yScale = (v) => padT + (1 - (v - y0) / Math.max(y1 - y0, 1e-9)) * innerH;
  const overviewPoints = downsample(
    cleanValues.map((v) => (Number.isFinite(v) ? v : NaN)),
    260,
  )
    .filter(([, v]) => Number.isFinite(v))
    .map(([idx, v]) => [xScale(idx), yScale(v)]);

  function pointerIdx(e) {
    return pointerToAbsoluteIdx(e, { w, padL, innerW, visibleStart: 0, visibleEnd: last });
  }

  function handlePointerDown(e) {
    if (e.button != null && e.button !== 0) return;
    const idx = pointerIdx(e);
    const handlePad = Math.max(Math.ceil(len * 0.01), 2);
    let mode = "move";
    if (Math.abs(idx - windowStart) <= handlePad) mode = "start";
    else if (Math.abs(idx - windowEnd) <= handlePad) mode = "end";
    else if (idx < windowStart || idx > windowEnd) {
      const half = Math.max(Math.round((windowEnd - windowStart) / 2), MIN_BRUSH_WIDTH);
      const start = clampIdx(idx - half, 0, Math.max(last - MIN_BRUSH_WIDTH, 0));
      const end = clampIdx(start + Math.max(windowEnd - windowStart, MIN_BRUSH_WIDTH), MIN_BRUSH_WIDTH, last);
      setDraft({ start: Math.min(start, end), end: Math.max(start, end) });
      mode = "move";
    }
    setDrag({ mode, anchorIdx: idx, start: windowStart, end: windowEnd });
    try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* no-op */ }
  }

  function handlePointerMove(e) {
    if (!drag) return;
    const idx = pointerIdx(e);
    let start = drag.start;
    let end = drag.end;
    if (drag.mode === "start") {
      start = clampIdx(idx, 0, end - MIN_BRUSH_WIDTH);
    } else if (drag.mode === "end") {
      end = clampIdx(idx, start + MIN_BRUSH_WIDTH, last);
    } else {
      const width = Math.max(drag.end - drag.start, MIN_BRUSH_WIDTH);
      const delta = idx - drag.anchorIdx;
      start = clampIdx(drag.start + delta, 0, Math.max(last - width, 0));
      end = clampIdx(start + width, start + MIN_BRUSH_WIDTH, last);
    }
    setDraft({ start, end });
  }

  function finish() {
    if (!drag) return;
    const start = draft ? draft.start : windowStart;
    const end = draft ? draft.end : windowEnd;
    setDrag(null);
    setDraft(null);
    const msRange = brushIdxToTsRange(start, end, timestamps);
    if (msRange) onRangeChange(msRange);
  }

  const winX = xScale(windowStart);
  const winW = Math.max(xScale(windowEnd) - winX, 1);

  return html`
    <svg
      class="range-brush"
      viewBox=${`0 0 ${w} ${h}`}
      width="100%"
      height=${h}
      preserveAspectRatio="none"
      style=${{ display: "block", maxWidth: "100%", cursor: drag ? "grabbing" : "grab" }}
      onPointerDown=${handlePointerDown}
      onPointerMove=${handlePointerMove}
      onPointerUp=${finish}
      onPointerLeave=${finish}
    >
      <rect x=${padL} y=${padT} width=${innerW} height=${innerH} rx="3" fill="var(--surface-2)" stroke="var(--border)" />
      ${overviewPoints.length > 1 && html`<path d=${lineFromPoints(overviewPoints)} fill="none" stroke=${color} stroke-width="1.1" opacity="0.72" />`}
      <rect x=${padL} y=${padT} width=${innerW} height=${innerH} fill="var(--surface)" opacity="0.55" />
      <rect x=${winX} y=${padT} width=${winW} height=${innerH} fill=${color} opacity="0.16" stroke=${color} stroke-width="1.2" />
      ${[windowStart, windowEnd].map((idx, i) => html`
        <g key=${i} transform=${`translate(${xScale(idx)}, 0)`}>
          <rect x="-4" y=${padT - 2} width="8" height=${innerH + 4} rx="2" fill="var(--surface)" stroke=${color} stroke-width="1.2" />
          <line x1="-1.5" x2="-1.5" y1=${padT + 7} y2=${padT + innerH - 7} stroke=${color} stroke-width="1" />
          <line x1="1.5" x2="1.5" y1=${padT + 7} y2=${padT + innerH - 7} stroke=${color} stroke-width="1" />
        </g>
      `)}
    </svg>
  `;
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
  yZoom = 1,
  yZoomAnchor = "mid",
}) {
  // series: [{ values: number[], color, label }]
  const [hover, setHover] = useState(null);
  const [brush, setBrush] = useState(null); // { startIdx, currentIdx } in absolute indices
  const clipId = useRef(`line-clip-${Math.random().toString(36).slice(2)}`).current;
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
  let y0 = yMin - yPad, y1 = yMax + yPad;
  [y0, y1] = applyYZoomDomain(y0, y1, yZoom, yZoomAnchor);

  // Absolute-index scale (i in [visibleStart..visibleEnd] -> screen X).
  const xScale = (i) => padL + ((i - visibleStart) / Math.max(visibleLen - 1, 1)) * innerW;
  const yScale = (v) => padT + (1 - (v - y0) / (y1 - y0)) * innerH;

  const ticks = 4;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) => y0 + (i / ticks) * (y1 - y0));
  const xTicks = hasXLabels
    ? calendarTickIndices(xLabels, visibleStart, visibleEnd, Math.min(5, visibleLen))
    : [];
  const tickRangeMs = supportsTimeRange ? visibleRangeMs(xLabels, visibleStart, visibleEnd) : NaN;

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
    <div>
    <svg viewBox=${`0 0 ${w} ${h}`} width="100%" height=${h} preserveAspectRatio="none" style=${{ display: "block", maxWidth: "100%", cursor: interactive ? "crosshair" : "default" }}>
      <defs><clipPath id=${clipId}><rect x=${padL} y=${padT} width=${innerW} height=${innerH} /></clipPath></defs>
      ${showAxes && yTicks.map((t, i) => html`
        <g key=${i}>
          <line x1=${padL} x2=${w - padR} y1=${yScale(t)} y2=${yScale(t)} stroke="var(--border)" stroke-dasharray="2 4" />
          <text x=${padL - 8} y=${yScale(t) + 3} font-size="10" text-anchor="end" fill="var(--text-subtle)" font-family="var(--font-mono)">
            ${formatAxisTick(t)}
          </text>
        </g>
      `)}
      ${showAxes && xTicks.map((idx) => html`
        <g key=${`x-${idx}`}>
          <line x1=${xScale(idx)} x2=${xScale(idx)} y1=${padT} y2=${h - padB} stroke="var(--border)" stroke-dasharray="2 4" opacity="0.5" />
          <text x=${xScale(idx)} y=${h - 10} font-size="10" text-anchor=${idx === visibleStart ? "start" : idx === visibleEnd ? "end" : "middle"} fill="var(--text-subtle)" font-family="var(--font-mono)">
            ${xTickFormatter(xLabels[idx], idx, tickRangeMs)}
          </text>
        </g>
      `)}
      <g clip-path=${`url(#${clipId})`}>
        ${cleanSeries.map((s, si) => {
          const slice = s.values.slice(visibleStart, visibleEnd + 1);
          const ds = downsample(slice, 240);
          const pts = ds.map(([i, v]) => [
            padL + (i / Math.max(slice.length - 1, 1)) * innerW,
            yScale(v),
          ]).filter(([, y]) => Number.isFinite(y));
          const stroke = s.color || color;
          const d = mode === "step" ? stepFromPoints(pts) : lineFromPoints(pts);
          return html`
            <g key=${si}>
              ${mode === "area" && html`<path d=${areaFromPoints(pts, yScale(y0))} fill=${stroke} opacity="0.12" />`}
              <path d=${d} fill="none" stroke=${stroke} stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
            </g>
          `;
        })}
      </g>
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
          <g clip-path=${`url(#${clipId})`}>
            ${cleanSeries.map((s, si) => {
              const value = s.values[hover];
              if (!Number.isFinite(value)) return null;
              return html`<circle key=${si} cx=${xScale(hover)} cy=${yScale(value)} r="3.5" fill=${s.color || color} stroke="var(--surface)" stroke-width="1.5" />`;
            })}
          </g>
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
    ${interactive && supportsTimeRange && html`
      <${RangeBrush}
        timestamps=${xLabels}
        values=${cleanSeries[0]?.values || []}
        range=${range}
        onRangeChange=${onRangeChange}
        color=${cleanSeries[0]?.color || color}
      />
    `}
    </div>
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
  xTickFormatter = adaptiveDateLabel,
  tooltipLabelFormatter = compactDateLabel,
  range = null,
  onRangeChange = null,
  yZoom = 1,
  yZoomAnchor = "mid",
}) {
  const [hover, setHover] = useState(null);
  const [brush, setBrush] = useState(null);
  const clipId = useRef(`trade-clip-${Math.random().toString(36).slice(2)}`).current;
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
  let y0 = yMin - yPad, y1 = yMax + yPad;
  [y0, y1] = applyYZoomDomain(y0, y1, yZoom, yZoomAnchor);
  const xScale = (i) => padL + ((i - visibleStart) / Math.max(visibleLen - 1, 1)) * innerW;
  const yScale = (v) => padT + (1 - (v - y0) / (y1 - y0)) * innerH;
  const yTicks = Array.from({ length: 5 }, (_, i) => y0 + (i / 4) * (y1 - y0));
  const xTicks = calendarTickIndices(sortedKeys, visibleStart, visibleEnd, Math.min(5, visibleLen));
  const tickRangeMs = visibleRangeMs(sortedKeys, visibleStart, visibleEnd);
  const overviewValues = sortedKeys.map((_, idx) => {
    for (const s of series) {
      const v = s.values.get(idx);
      if (Number.isFinite(v)) return v;
    }
    return NaN;
  });
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
    <div>
    <svg viewBox=${`0 0 ${w} ${h}`} width="100%" height=${h} preserveAspectRatio="none" style=${{ display: "block", maxWidth: "100%", cursor: interactive ? "crosshair" : "default" }}>
      <defs><clipPath id=${clipId}><rect x=${padL} y=${padT} width=${innerW} height=${innerH} /></clipPath></defs>
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
            ${formatAxisTick(t)}
          </text>
        </g>
      `)}
      ${xTicks.map((idx) => html`
        <g key=${`x-${idx}`}>
          <line x1=${xScale(idx)} x2=${xScale(idx)} y1=${padT} y2=${h - padB} stroke="var(--border)" stroke-dasharray="2 4" opacity="0.45" />
          <text x=${xScale(idx)} y=${h - 10} font-size="10" text-anchor=${idx === visibleStart ? "start" : idx === visibleEnd ? "end" : "middle"} fill="var(--text-subtle)" font-family="var(--font-mono)">
            ${xTickFormatter(sortedKeys[idx], tickRangeMs)}
          </text>
        </g>
      `)}
      <g clip-path=${`url(#${clipId})`}>
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
      </g>
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
          <g clip-path=${`url(#${clipId})`}>
            ${hoverPrices.map((row) => html`
              ${Number.isFinite(row.value) && html`<circle key=${row.symbol} cx=${xScale(hover)} cy=${yScale(row.value)} r="3.5" fill=${row.color} stroke="var(--surface)" stroke-width="1.5" />`}
            `)}
          </g>
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
    ${interactive && html`
      <${RangeBrush}
        timestamps=${sortedKeys}
        values=${overviewValues}
        range=${range}
        onRangeChange=${onRangeChange}
        color=${series[0]?.color || "var(--accent)"}
      />
    `}
    </div>
  `;
}

// Indicator chart: price + fast/slow lines + trade markers, optional MACD sub-panel.
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
  color = "var(--text)",
  fastColor = "#2563eb",
  slowColor = "#dc2626",
  visibleSeries = null,
  range = null,
  onRangeChange = null,
  xTickFormatter = adaptiveDateLabel,
  tooltipLabelFormatter = compactDateLabel,
  yZoom = 1,
  yZoomAnchor = "mid",
  macdYZoom = null,
  macdYZoomAnchor = "mid",
}) {
  const show = {
    price: visibleSeries?.price !== false,
    fast: visibleSeries?.fast !== false,
    slow: visibleSeries?.slow !== false,
    macd: visibleSeries?.macd !== false,
  };
  const hasMacd = show.macd && Array.isArray(macd) && macd.length > 0 && Array.isArray(macdSignal);
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
  const mainClipId = useRef(`indicator-main-clip-${Math.random().toString(36).slice(2)}`).current;
  const macdClipId = useRef(`indicator-macd-clip-${Math.random().toString(36).slice(2)}`).current;

  const tsLen = timestamps?.length || 0;
  const [visibleStart, visibleEnd] = rangeToSlice(range, timestamps || []);
  const visibleLen = Math.max(visibleEnd - visibleStart + 1, 1);
  const inVisibleRange = (idx) => idx >= visibleStart && idx <= visibleEnd;

  const allSeries = [
    show.price ? { values: prices, color, label: symbol || "Price" } : null,
    show.fast ? { values: fast, color: fastColor, label: fastLabel } : null,
    show.slow ? { values: slow, color: slowColor, label: slowLabel } : null,
  ].filter((s) => s && Array.isArray(s.values) && s.values.length > 0);
  const visiblePriceVals = allSeries.flatMap((s) =>
    s.values.slice(visibleStart, visibleEnd + 1)
  ).filter((v) => Number.isFinite(v));
  if (!visiblePriceVals.length && !hasMacd) return null;
  const yMin = visiblePriceVals.length ? Math.min(...visiblePriceVals) : 0;
  const yMax = visiblePriceVals.length ? Math.max(...visiblePriceVals) : 1;
  const yPad = (yMax - yMin) * 0.05 || Math.max(Math.abs(yMax) * 0.01, 1);
  let y0 = yMin - yPad, y1 = yMax + yPad;
  [y0, y1] = applyYZoomDomain(y0, y1, yZoom, yZoomAnchor);
  const xScale = (i) => padL + ((i - visibleStart) / Math.max(visibleLen - 1, 1)) * innerW;
  const yScale = (v) => padT + (1 - (v - y0) / (y1 - y0)) * innerH;

  // MACD sub-panel domain
  let macdY0 = 0, macdY1 = 0, macdYScale = null;
  let macdYTicks = [];
  if (hasMacd) {
    const macdSlice = Array.from({ length: tsLen }, (_, i) => i).filter((i) => inVisibleRange(i));
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
      [macdY0, macdY1] = applyYZoomDomain(macdY0, macdY1, macdYZoom ?? 1, macdYZoomAnchor);
      macdYTicks = Array.from({ length: 3 }, (_, i) => macdY0 + (i / 2) * (macdY1 - macdY0));
      macdYScale = (v) => macdYTop + (1 - (v - macdY0) / Math.max(macdY1 - macdY0, 1e-9)) * macdInnerH;
    }
  }

  const yTicks = Array.from({ length: 5 }, (_, i) => y0 + (i / 4) * (y1 - y0));
  const xTicks = calendarTickIndices(timestamps || [], visibleStart, visibleEnd, Math.min(5, visibleLen));
  const tickRangeMs = visibleRangeMs(timestamps || [], visibleStart, visibleEnd);
  const overviewValues = (allSeries[0]?.values || prices || []).slice(0, tsLen);

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
    <div>
    <svg viewBox=${`0 0 ${w} ${totalH}`} width="100%" height=${totalH} preserveAspectRatio="none" style=${{ display: "block", maxWidth: "100%", cursor: interactive ? "crosshair" : "default" }}>
      <defs>
        <clipPath id=${mainClipId}><rect x=${padL} y=${padT} width=${innerW} height=${innerH} /></clipPath>
        <clipPath id=${macdClipId}><rect x=${padL} y=${macdYTop} width=${innerW} height=${macdInnerH} /></clipPath>
      </defs>
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
          <text x=${padL - 8} y=${yScale(t) + 3} font-size="10" text-anchor="end" fill="var(--text-subtle)" font-family="var(--font-mono)">${formatAxisTick(t)}</text>
        </g>
      `)}
      ${!hasMacd && xTicks.map((idx) => html`
        <g key=${`x-${idx}`}>
          <line x1=${xScale(idx)} x2=${xScale(idx)} y1=${padT} y2=${mainH - padB} stroke="var(--border)" stroke-dasharray="2 4" opacity="0.45" />
          <text x=${xScale(idx)} y=${mainH - 10} font-size="10" text-anchor=${idx === visibleStart ? "start" : idx === visibleEnd ? "end" : "middle"} fill="var(--text-subtle)" font-family="var(--font-mono)">${xTickFormatter(timestamps[idx], tickRangeMs)}</text>
        </g>
      `)}
      <g clip-path=${`url(#${mainClipId})`}>
        ${allSeries.map((s, si) => {
          const slice = s.values.slice(visibleStart, visibleEnd + 1);
          const ds = downsample(slice, 360);
          const pts = ds.map(([i, v]) => [padL + (i / Math.max(slice.length - 1, 1)) * innerW, yScale(v)])
            .filter(([, y]) => Number.isFinite(y));
          return html`<path key=${si} d=${lineFromPoints(pts)} fill="none" stroke=${s.color} stroke-width=${si === 0 ? 1.6 : 1.4} stroke-linejoin="round" stroke-linecap="round" opacity=${si === 0 ? 0.95 : 0.85} />`;
        })}
        ${show.price && (markers || []).filter((m) => inVisibleRange(m.idx) && Number.isFinite(+m.price)).map((m, i) => {
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
      </g>
      ${hasMacd && macdYScale && html`
        <g>
          <line x1=${padL} x2=${w - padR} y1=${mainH} y2=${mainH} stroke="var(--border)" />
          <text x=${padL} y=${macdYTop - 2} font-size="10" fill="var(--text-subtle)" font-family="var(--font-mono)">MACD</text>
          ${macdYTicks.map((t, i) => html`
            <g key=${`my-${i}`}>
              <line x1=${padL} x2=${w - padR} y1=${macdYScale(t)} y2=${macdYScale(t)} stroke="var(--border)" stroke-dasharray="2 4" opacity="0.65" />
              <text x=${padL - 8} y=${macdYScale(t) + 3} font-size="10" text-anchor="end" fill="var(--text-subtle)" font-family="var(--font-mono)">${formatAxisTick(t)}</text>
            </g>
          `)}
          <line x1=${padL} x2=${w - padR} y1=${macdYScale(0)} y2=${macdYScale(0)} stroke="var(--border-strong)" />
          <g clip-path=${`url(#${macdClipId})`}>
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
          </g>
          ${xTicks.map((idx) => html`
            <text key=${`mx-${idx}`} x=${xScale(idx)} y=${macdYTop + macdInnerH + 16} font-size="10" text-anchor=${idx === visibleStart ? "start" : idx === visibleEnd ? "end" : "middle"} fill="var(--text-subtle)" font-family="var(--font-mono)">${xTickFormatter(timestamps[idx], tickRangeMs)}</text>
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
    ${interactive && html`
      <${RangeBrush}
        timestamps=${timestamps || []}
        values=${overviewValues}
        range=${range}
        onRangeChange=${onRangeChange}
        color=${allSeries[0]?.color || color}
      />
    `}
    </div>
  `;
}

function HeatmapChart({ rows = [], xKey, yKey, valueKey, title = "", height = 220 }) {
  const [hover, setHover] = useState(null);
  const [selected, setSelected] = useState(null);
  const clean = (rows || [])
    .map((row) => ({
      x: Number(row?.[xKey]),
      y: Number(row?.[yKey]),
      value: Number(row?.[valueKey]),
    }))
    .filter((row) => Number.isFinite(row.x) && Number.isFinite(row.y) && Number.isFinite(row.value));
  const xs = [...new Set(clean.map((row) => row.x))].sort((a, b) => a - b);
  const ys = [...new Set(clean.map((row) => row.y))].sort((a, b) => a - b);
  const byKey = new Map(clean.map((row) => [`${row.x}|${row.y}`, row.value]));
  const values = clean.map((row) => row.value);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const w = 560;
  const h = Math.max(180, height);
  const padL = 48, padR = 14, padT = title ? 34 : 16, padB = 36;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const cellW = xs.length ? innerW / xs.length : innerW;
  const cellH = ys.length ? innerH / ys.length : innerH;
  const activeCell = hover || selected;
  function fill(value) {
    if (!Number.isFinite(value)) return "var(--surface-2)";
    const t = max === min ? 0.5 : (value - min) / (max - min);
    const r = Math.round(44 + t * 18);
    const g = Math.round(109 + t * 94);
    const b = Math.round(142 - t * 62);
    return `rgb(${r}, ${g}, ${b})`;
  }
  function cellAtPointer(e) {
    const box = e.currentTarget.getBoundingClientRect();
    const relX = (e.clientX - box.left) / Math.max(box.width, 1);
    const relY = (e.clientY - box.top) / Math.max(box.height, 1);
    const xi = Math.max(0, Math.min(xs.length - 1, Math.floor(relX * xs.length)));
    const yi = Math.max(0, Math.min(ys.length - 1, Math.floor(relY * ys.length)));
    const x = xs[xi];
    const y = ys[yi];
    return { x, y, xi, yi, value: byKey.get(`${x}|${y}`) };
  }
  function cellLabel(cell) {
    if (!cell) return "";
    return `${xKey}: ${cell.x} | ${yKey}: ${cell.y} | ${valueKey}: ${defaultTooltipValue(cell.value)}`;
  }
  function handlePointerMove(e) {
    setHover(cellAtPointer(e));
  }
  function handleClick(e) {
    setSelected(cellAtPointer(e));
  }
  if (!clean.length || xs.length < 1 || ys.length < 1) {
    return html`<div class="field-hint" style=${{ padding: 12 }}>No heatmap rows.</div>`;
  }
  const tooltipW = 236;
  const tooltipX = activeCell ? Math.min(padL + (activeCell.xi + 1) * cellW + 8, w - tooltipW - 8) : 0;
  const tooltipY = activeCell ? Math.max(8, Math.min(padT + activeCell.yi * cellH + 8, h - 82)) : 0;
  return html`
    <svg viewBox=${`0 0 ${w} ${h}`} width="100%" height=${h} role="img" aria-label=${title || valueKey}>
      ${title && html`<text x=${padL} y="18" fill="var(--text)" font-size="12" font-family="var(--font-mono)">${title}</text>`}
      ${ys.map((y, yi) => xs.map((x, xi) => {
        const value = byKey.get(`${x}|${y}`);
        const cell = { x, y, value, xi, yi };
        return html`
          <g key=${`${x}|${y}`}>
            <title>${cellLabel(cell)}</title>
            <rect
              x=${padL + xi * cellW}
              y=${padT + yi * cellH}
              width=${Math.max(cellW - 1, 1)}
              height=${Math.max(cellH - 1, 1)}
              fill=${fill(value)}
            />
          </g>
          ${cellW > 42 && cellH > 22 && Number.isFinite(value) && html`
            <text x=${padL + xi * cellW + cellW / 2} y=${padT + yi * cellH + cellH / 2 + 4}
              text-anchor="middle" font-size="10" fill="#fff" font-family="var(--font-mono)">
              ${defaultTooltipValue(value)}
            </text>
          `}
        `;
      }))}
      ${xs.map((x, xi) => html`
        <text x=${padL + xi * cellW + cellW / 2} y=${h - 14} text-anchor="middle" font-size="10" fill="var(--text-muted)" font-family="var(--font-mono)">${x}</text>
      `)}
      ${ys.map((y, yi) => html`
        <text x=${padL - 8} y=${padT + yi * cellH + cellH / 2 + 4} text-anchor="end" font-size="10" fill="var(--text-muted)" font-family="var(--font-mono)">${y}</text>
      `)}
      ${selected && html`
        <rect
          x=${padL + selected.xi * cellW}
          y=${padT + selected.yi * cellH}
          width=${Math.max(cellW - 1, 1)}
          height=${Math.max(cellH - 1, 1)}
          fill="none"
          stroke="var(--text)"
          stroke-width="1.8"
          pointer-events="none"
        />
      `}
      ${hover && html`
        <rect
          x=${padL + hover.xi * cellW}
          y=${padT + hover.yi * cellH}
          width=${Math.max(cellW - 1, 1)}
          height=${Math.max(cellH - 1, 1)}
          fill="none"
          stroke="var(--accent)"
          stroke-width="1.4"
          pointer-events="none"
        />
      `}
      ${activeCell && html`
        <g transform=${`translate(${tooltipX}, ${tooltipY})`} pointer-events="none">
          <rect width=${tooltipW} height="74" rx="6" fill="var(--surface)" stroke="var(--border-strong)" />
          <text x="10" y="18" font-size="11" fill="var(--text-muted)" font-family="var(--font-mono)">
            ${hover ? "Hover" : "Selected"}
          </text>
          <text x="10" y="36" font-size="11" fill="var(--text)" font-family="var(--font-mono)">${xKey}: ${activeCell.x}</text>
          <text x="10" y="52" font-size="11" fill="var(--text)" font-family="var(--font-mono)">${yKey}: ${activeCell.y}</text>
          <text x="10" y="68" font-size="11" fill="var(--text)" font-family="var(--font-mono)">${valueKey}: ${defaultTooltipValue(activeCell.value)}</text>
        </g>
      `}
      <text x=${padL + innerW / 2} y=${h - 2} text-anchor="middle" font-size="10" fill="var(--text-muted)" font-family="var(--font-mono)">${xKey}</text>
      <text x="12" y=${padT + innerH / 2} text-anchor="middle" font-size="10" fill="var(--text-muted)" font-family="var(--font-mono)" transform=${`rotate(-90 12 ${padT + innerH / 2})`}>${yKey}</text>
      <rect
        x=${padL}
        y=${padT}
        width=${innerW}
        height=${innerH}
        fill="transparent"
        style=${{ cursor: "pointer" }}
        onPointerMove=${handlePointerMove}
        onPointerLeave=${() => setHover(null)}
        onClick=${handleClick}
      />
    </svg>
  `;
}

window.Charts = { LineChart, Sparkline, BarChart, HistogramChart, TradePriceChart, IndicatorChart, HeatmapChart, adaptiveDateLabel, MAX_Y_ZOOM };
