import React from 'react';

const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

export default function AnalyticsChart({ spec, rows }) {
  if (!spec || !Array.isArray(rows) || rows.length === 0) return null;
  const type = String(spec.type || 'table').toLowerCase();
  const xKey = spec.x;
  const yKey = spec.y;

  if (type === 'table' || !xKey || !yKey) return null;

  const points = rows
    .map((row) => ({ x: row[xKey], y: num(row[yKey]), series: spec.series ? row[spec.series] : null }))
    .filter((p) => p.y !== null)
    .slice(0, 60);

  if (!points.length) return null;

  const values = points.map((p) => p.y);
  const min = Math.min(0, ...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  if (type === 'bar') {
    return (
      <div className="ws-chart-card">
        <div className="ws-chart-title">{spec.title || 'Chart'}</div>
        <div className="ws-bar-chart" role="img" aria-label={spec.title || 'Bar chart'}>
          {points.map((p, i) => {
            const height = Math.max(4, ((p.y - min) / range) * 100);
            return (
              <div className="ws-bar-item" key={i} title={`${p.x}: ${p.y}`}>
                <div className="ws-bar-value">{p.y.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
                <div className="ws-bar-track"><div className="ws-bar-fill" style={{ height: `${height}%` }} /></div>
                <div className="ws-bar-label">{String(p.x)}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  const width = 760;
  const height = 240;
  const pad = { left: 48, right: 20, top: 20, bottom: 42 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const coords = points.map((p, i) => ({
    x: pad.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW),
    y: pad.top + ((max - p.y) / range) * innerH,
    label: String(p.x),
    value: p.y,
  }));
  const path = coords.map((p, i) => `${i ? 'L' : 'M'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const area = `${path} L ${coords.at(-1).x.toFixed(1)} ${height - pad.bottom} L ${coords[0].x.toFixed(1)} ${height - pad.bottom} Z`;

  return (
    <div className="ws-chart-card">
      <div className="ws-chart-title">{spec.title || 'Chart'}</div>
      <div className="ws-line-chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} className="ws-line-chart" role="img" aria-label={spec.title || 'Line chart'}>
          <line x1={pad.left} y1={height - pad.bottom} x2={width - pad.right} y2={height - pad.bottom} stroke="currentColor" opacity="0.18" />
          {type === 'area' && <path d={area} fill="currentColor" opacity="0.08" />}
          <path d={path} fill="none" stroke="currentColor" strokeWidth="2.5" />
          {coords.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="3.5" fill="currentColor" />)}
          {coords.filter((_, i) => i === 0 || i === coords.length - 1 || i % Math.ceil(coords.length / 5) === 0).map((p, i) => (
            <text key={i} x={p.x} y={height - 18} textAnchor="middle" fontSize="10" fill="currentColor" opacity="0.65">{p.label}</text>
          ))}
        </svg>
      </div>
    </div>
  );
}
