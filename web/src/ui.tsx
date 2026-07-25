import { ReactNode, useState } from "react";
import { ApiError, fmt, Qty } from "./api";

export function Card({ title, children, right }: { title?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="card">
      {(title || right) && (
        <div className="row" style={{ marginBottom: 10 }}>
          {title && <h2 style={{ margin: 0 }}>{title}</h2>}
          <div className="spacer" />
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Num({
  label, value, onChange, step,
}: { label: string; value: number; onChange: (v: number) => void; step?: number }) {
  return (
    <label className="f">
      {label}
      <input
        type="number"
        value={Number.isFinite(value) ? value : ""}
        step={step ?? "any"}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </label>
  );
}

export function Sel({
  label, value, onChange, options,
}: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <label className="f">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map(([v, name]) => (
          <option key={v} value={v}>{name}</option>
        ))}
      </select>
    </label>
  );
}

export function ClassBadge({ cls }: { cls?: string }) {
  if (!cls) return null;
  const eng = cls.toLowerCase() === "engineering";
  return <span className={`badge ${eng ? "eng" : "scr"}`}>{eng ? "Engineering" : "Screening"}</span>;
}

export function KV({ items }: { items: [string, number | string | null | undefined, string?][] }) {
  return (
    <dl className="kv">
      {items.map(([k, v, unit]) => (
        <div key={k} style={{ display: "contents" }}>
          <dt>{k}</dt>
          <dd>
            {typeof v === "number" ? fmt(v) : v ?? "—"}
            {unit && <span className="unit">{unit}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export const q = (x?: Qty | null): [number | null, string] => (x ? [x.value, x.unit] : [null, ""]);

export function Warnings({ list }: { list?: string[] }) {
  if (!list?.length) return null;
  return (
    <div>
      {list.map((w, i) => (
        <div className="warn" key={i}>{w}</div>
      ))}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof ApiError ? `HTTP ${error.status}: ${error.message}` : String(error);
  const gate = error instanceof ApiError && error.status === 409;
  return (
    <div className="error-box">
      {gate && <span className="badge err" style={{ marginRight: 8 }}>Gatekeeper</span>}
      {msg}
    </div>
  );
}

/** Small run-state helper for form screens. */
export function useRun<T>(runner: () => Promise<T>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [data, setData] = useState<T | null>(null);
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await runner());
    } catch (e) {
      setError(e);
      setData(null);
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, data, run };
}

/** Dependency-free SVG line chart (dark instrument-panel styling). */
export function LineChart({
  series, xLabels, unit, height = 300,
}: {
  series: { name: string; values: (number | null)[]; color: string }[];
  xLabels: string[];
  unit?: string;
  height?: number;
}) {
  const width = 860;
  const padL = 58, padR = 130, padT = 18, padB = 40;
  const plotW = width - padL - padR, plotH = height - padT - padB;
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  if (!all.length) return null;
  let yMin = Math.min(...all), yMax = Math.max(...all);
  if (yMax === yMin) yMax = yMin + 1;
  const span = yMax - yMin;
  yMin -= span * 0.08; yMax += span * 0.08;
  const n = xLabels.length;
  const px = (i: number) => padL + (n > 1 ? (plotW * i) / (n - 1) : 0);
  const py = (v: number) => padT + plotH * (1 - (v - yMin) / (yMax - yMin));
  const gridYs = [0, 1, 2, 3, 4].map((k) => yMin + ((yMax - yMin) * k) / 4);
  const step = Math.max(1, Math.floor(n / 6));
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <rect width={width} height={height} fill="#0d1117" rx="8" />
        {gridYs.map((v) => (
          <g key={v}>
            <line x1={padL} y1={py(v)} x2={padL + plotW} y2={py(v)} stroke="#30363d" />
            <text x={padL - 8} y={py(v) + 4} fill="#8b949e" fontSize="11" textAnchor="end">
              {fmt(v, 1)}
            </text>
          </g>
        ))}
        {unit && (
          <text x={padL - 8} y={padT - 4} fill="#8b949e" fontSize="11" textAnchor="end">{unit}</text>
        )}
        {xLabels.map((lb, i) =>
          i % step === 0 ? (
            <text key={i} x={px(i)} y={height - padB + 18} fill="#8b949e" fontSize="11" textAnchor="middle">
              {lb}
            </text>
          ) : null,
        )}
        {series.map((s, si) => {
          const pts = s.values
            .map((v, i) => (v === null ? null : `${px(i).toFixed(1)},${py(v).toFixed(1)}`))
            .filter(Boolean)
            .join(" ");
          const lastIdx = s.values.length - 1;
          const lastVal = s.values[lastIdx];
          return (
            <g key={s.name}>
              <polyline points={pts} fill="none" stroke={s.color} strokeWidth="2.2" />
              {lastVal !== null && <circle cx={px(lastIdx)} cy={py(lastVal)} r="3.2" fill={s.color} />}
              <rect x={padL + plotW + 14} y={padT + 4 + si * 20} width="12" height="12" rx="2" fill={s.color} />
              <text x={padL + plotW + 32} y={padT + 14 + si * 20} fill="#e6edf3" fontSize="12">{s.name}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
