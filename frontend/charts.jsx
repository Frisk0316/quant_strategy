// Tiny SVG chart primitives — no third-party libs.
/* global React */

const { useMemo } = React;

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

function LineChart({ series, height = 220, mode = "line", color = "var(--accent)", showAxes = true, yDomain }) {
  // series: [{ values: number[], color, label }]
  const w = 1000, h = height;
  const padL = 44, padR = 12, padT = 12, padB = 24;
  const innerW = w - padL - padR, innerH = h - padT - padB;

  const all = series.flatMap((s) => s.values);
  const yMin = yDomain ? yDomain[0] : Math.min(...all);
  const yMax = yDomain ? yDomain[1] : Math.max(...all);
  const yPad = (yMax - yMin) * 0.05 || 0.01;
  const y0 = yMin - yPad, y1 = yMax + yPad;

  const xN = series[0]?.values.length || 1;
  const xScale = (i) => padL + (i / (xN - 1)) * innerW;
  const yScale = (v) => padT + (1 - (v - y0) / (y1 - y0)) * innerH;

  const ticks = 4;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) => y0 + (i / ticks) * (y1 - y0));

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="none" style={{ display: "block" }}>
      {showAxes && yTicks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={w - padR} y1={yScale(t)} y2={yScale(t)} stroke="var(--border)" strokeDasharray="2 4" />
          <text x={padL - 8} y={yScale(t) + 3} fontSize="10" textAnchor="end" fill="var(--text-subtle)" fontFamily="var(--font-mono)">
            {Math.abs(t) > 100 ? t.toFixed(0) : t.toFixed(2)}
          </text>
        </g>
      ))}
      {series.map((s, si) => {
        const ds = downsample(s.values, 240);
        const pts = ds.map(([i, v]) => [xScale(i), yScale(v)]);
        const stroke = s.color || color;
        const d = mode === "step" ? stepFromPoints(pts) : lineFromPoints(pts);
        return (
          <g key={si}>
            {mode === "area" && <path d={areaFromPoints(pts, yScale(y0))} fill={stroke} opacity="0.12" />}
            <path d={d} fill="none" stroke={stroke} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
          </g>
        );
      })}
    </svg>
  );
}

function Sparkline({ values, color = "var(--accent)", height = 36, mode = "line" }) {
  const w = 200, h = height;
  const padT = 4, padB = 4;
  const yMin = Math.min(...values), yMax = Math.max(...values);
  const yPad = (yMax - yMin) * 0.08 || 0.001;
  const y0 = yMin - yPad, y1 = yMax + yPad;
  const ds = downsample(values, 80);
  const pts = ds.map(([i, v], k) => [
    (k / (ds.length - 1)) * w,
    padT + (1 - (v - y0) / (y1 - y0)) * (h - padT - padB),
  ]);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="none" style={{ display: "block" }}>
      {mode === "area" && <path d={areaFromPoints(pts, h - padB)} fill={color} opacity="0.14" />}
      <path d={mode === "step" ? stepFromPoints(pts) : lineFromPoints(pts)} fill="none" stroke={color} strokeWidth="1.4" />
    </svg>
  );
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
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="none" style={{ display: "block" }}>
      <line x1={padL} x2={w - padR} y1={yScale(0)} y2={yScale(0)} stroke="var(--border-strong)" />
      {threshold != null && (
        <line x1={padL} x2={w - padR} y1={yScale(threshold)} y2={yScale(threshold)} stroke="var(--warn)" strokeDasharray="3 4" />
      )}
      {values.map((v, i) => {
        const y = yScale(Math.max(v, 0));
        const yEnd = yScale(Math.min(v, 0));
        const fill = v < 0 ? "var(--loss)" : color;
        return (
          <rect key={i} x={xScale(i)} y={y} width={barW} height={Math.max(yEnd - y, 1)} fill={fill} rx="1.5" opacity={v < 0 ? 0.8 : 0.9} />
        );
      })}
      {labels && labels.map((l, i) => (
        <text key={i} x={xScale(i) + barW / 2} y={h - 8} fontSize="10" textAnchor="middle" fill="var(--text-subtle)" fontFamily="var(--font-mono)">{l}</text>
      ))}
    </svg>
  );
}

function HistogramChart({ values, bins = 24, height = 140, color = "var(--accent)" }) {
  const min = Math.min(...values), max = Math.max(...values);
  const step = (max - min) / bins || 1;
  const counts = new Array(bins).fill(0);
  values.forEach((v) => {
    const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / step)));
    counts[idx]++;
  });
  return <BarChart values={counts} height={height} color={color} labels={null} />;
}

window.Charts = { LineChart, Sparkline, BarChart, HistogramChart };
