import type { CalBin, Contrast } from "../lib/api";
import { pct, pp } from "../lib/format";

/** Horizontal bars as a list: label, bar, value. Readable without the bar. */
export function HBars({
  label,
  rows,
  format,
  max,
}: {
  label: string;
  rows: { key: string; label: string; v: number; note?: string; cls?: string }[];
  format: (v: number) => string;
  max?: number;
}) {
  const m = max ?? Math.max(...rows.map((r) => Math.abs(r.v)), 1e-9);
  return (
    <ul className="hbars" aria-label={label}>
      {rows.map((r) => (
        <li key={r.key} className="hbar">
          <span>{r.label}</span>
          <span className="hbar-track" aria-hidden="true">
            <span className={`hbar-fill ${r.cls ?? ""}`} style={{ width: `${(Math.abs(r.v) / m) * 100}%`, display: "block" }} />
          </span>
          <span className="num">
            {format(r.v)}
            {r.note ? <span className="muted"> · {r.note}</span> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Differences between arms in percentage points, with 95% bootstrap intervals; 0 = no difference. */
export function ContrastPlot({ title, rows, unit = "pp" }: { title: string; rows: Contrast[]; unit?: string }) {
  const W = 760;
  const row = 30;
  const L = 120;
  const R = 150;
  const T = 26;
  const H = T + rows.length * row + 8;
  const ext = Math.max(0.1, ...rows.flatMap((r) => (r.ci ? [Math.abs(r.ci[0]), Math.abs(r.ci[1])] : [Math.abs(r.diff ?? 0)])));
  const lim = Math.ceil(ext * 20) / 20;
  const X = (v: number) => L + ((v + lim) / (2 * lim)) * (W - L - R);
  const step = lim > 0.3 ? 0.1 : 0.05;
  const ticks: number[] = [];
  for (let t = -lim; t <= lim + 1e-9; t += step) ticks.push(Number(t.toFixed(2)));
  return (
    <figure className="chart" style={{ maxWidth: 820 }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${title}. ${rows
          .map((r) => `${r.contrast}: ${pp(r.diff)} ${unit}${r.ci ? ` (95% interval ${pp(r.ci[0])} to ${pp(r.ci[1])})` : ""}`)
          .join("; ")}`}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={X(t)} x2={X(t)} y1={T - 6} y2={H - 4} stroke={t === 0 ? "var(--ink-3)" : "var(--rule)"} strokeDasharray={t === 0 ? "4 3" : undefined} />
            <text x={X(t)} y={T - 10} textAnchor="middle" className="tick">
              {pp(t, 0)}
            </text>
          </g>
        ))}
        {rows.map((r, i) => {
          const y = T + i * row + row / 2;
          const clear = !!r.ci && (r.ci[0] > 0 || r.ci[1] < 0);
          const col = clear ? "var(--accent)" : "var(--ink-3)";
          return (
            <g key={r.contrast}>
              <text x={L - 12} y={y + 4} textAnchor="end" className="flabel">
                {r.contrast}
              </text>
              {r.ci && <line x1={X(r.ci[0])} x2={X(r.ci[1])} y1={y} y2={y} stroke={col} strokeWidth={2} />}
              {r.diff !== null && <circle cx={X(r.diff)} cy={y} r={5} fill={col} />}
              <text x={W - 4} y={y + 4} textAnchor="end" className="tick">
                {pp(r.diff)} {unit}
                {r.ci ? ` [${pp(r.ci[0])}, ${pp(r.ci[1])}]` : ""}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="legend">
        <span>Difference in {unit === "pp" ? "percentage points" : unit}; dashed line = no difference. Coloured: the 95% bootstrap interval excludes 0.</span>
      </figcaption>
    </figure>
  );
}

const ARM_VAR: Record<string, string> = { A: "var(--arm-a)", B: "var(--arm-b)", C: "var(--arm-c)" };
const ARM_DASH: Record<string, string | undefined> = { A: undefined, B: "6 4", C: "2 3" };

/** Reliability diagram: stated confidence against accuracy, per arm; the diagonal is perfect calibration. */
export function CalibrationPlot({ title, curves }: { title: string; curves: Record<string, CalBin[]> }) {
  const S = 300;
  const P = 40;
  const X = (v: number) => P + ((v - 0.5) / 0.5) * (S - P - 24);
  const Y = (v: number) => S - P - v * (S - P - 10);
  const ticks = [0.5, 0.6, 0.7, 0.8, 0.9, 1];
  const yt = [0, 0.25, 0.5, 0.75, 1];
  return (
    <figure className="chart" style={{ maxWidth: 380 }}>
      <svg
        viewBox={`0 0 ${S} ${S}`}
        role="img"
        aria-label={`${title}. ${Object.entries(curves)
          .map(
            ([arm, c]) =>
              `Arm ${arm}: ${c
                .filter((b) => b.n)
                .map((b) => `confidence ${pct(b.confidence)} accuracy ${pct(b.accuracy)} (${b.n})`)
                .join(", ")}`,
          )
          .join(". ")}`}
      >
        {ticks.map((t) => (
          <g key={`x${t}`}>
            <line x1={X(t)} x2={X(t)} y1={Y(0)} y2={Y(1)} stroke="var(--rule)" />
            <text x={X(t)} y={S - P + 16} textAnchor="middle" className="tick">
              {pct(t)}
            </text>
          </g>
        ))}
        {yt.map((t) => (
          <g key={`y${t}`}>
            <line x1={X(0.5)} x2={X(1)} y1={Y(t)} y2={Y(t)} stroke="var(--rule)" />
            <text x={X(0.5) - 6} y={Y(t) + 4} textAnchor="end" className="tick">
              {pct(t)}
            </text>
          </g>
        ))}
        <line x1={X(0.5)} y1={Y(0.5)} x2={X(1)} y2={Y(1)} stroke="var(--ink-3)" strokeDasharray="4 3" />
        {Object.entries(curves).map(([arm, c]) => {
          const pts = c.filter((b) => b.n && b.confidence !== null && b.accuracy !== null);
          const d = pts.map((b, i) => `${i ? "L" : "M"}${X(b.confidence ?? 0).toFixed(1)},${Y(b.accuracy ?? 0).toFixed(1)}`).join("");
          return (
            <g key={arm}>
              <path d={d} fill="none" stroke={ARM_VAR[arm]} strokeWidth={2} strokeDasharray={ARM_DASH[arm]} />
              {pts.map((b) => (
                <circle key={b.bin[0]} cx={X(b.confidence ?? 0)} cy={Y(b.accuracy ?? 0)} r={3.5} fill={ARM_VAR[arm]} />
              ))}
            </g>
          );
        })}
        <text x={(X(0.5) + X(1)) / 2} y={S - 4} textAnchor="middle" className="tick">
          stated confidence
        </text>
        <text x={10} y={(Y(0) + Y(1)) / 2} textAnchor="middle" className="tick" transform={`rotate(-90 10 ${(Y(0) + Y(1)) / 2})`}>
          share correct
        </text>
      </svg>
      <figcaption className="legend">
        {Object.keys(curves).map((arm) => (
          <span key={arm}>
            <svg width="22" height="8" aria-hidden="true">
              <line x1="0" x2="22" y1="4" y2="4" stroke={ARM_VAR[arm]} strokeWidth="2" strokeDasharray={ARM_DASH[arm]} />
            </svg>{" "}
            Arm {arm}
          </span>
        ))}
        <span>dashed grey = perfectly calibrated</span>
      </figcaption>
    </figure>
  );
}

/** Power against participants per arm, one line per contrast, from simulated studies. */
export function PowerCurve({
  title,
  series,
  xs,
  target = 0.8,
}: {
  title: string;
  series: { key: string; label: string; points: { x: number; y: number }[]; dash?: string; colour: string }[];
  xs: number[];
  target?: number;
}) {
  const W = 760;
  const H = 280;
  const L = 50;
  const R = 20;
  const T = 12;
  const B = 40;
  const xMax = Math.max(...xs);
  const X = (v: number) => L + (v / xMax) * (W - L - R);
  const Y = (v: number) => T + (1 - v) * (H - T - B);
  return (
    <figure className="chart" style={{ maxWidth: 820 }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${title}. ${series.map((s) => `${s.label}: ${s.points.map((p) => `${p.x} per arm ${pct(p.y)}`).join(", ")}`).join("; ")}`}
      >
        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={Y(t)} y2={Y(t)} stroke={t === target ? "var(--ink-3)" : "var(--rule)"} strokeDasharray={t === target ? "4 3" : undefined} />
            <text x={L - 6} y={Y(t) + 4} textAnchor="end" className="tick">
              {pct(t)}
            </text>
          </g>
        ))}
        {xs.map((x) => (
          <text key={x} x={X(x)} y={H - 22} textAnchor="middle" className="tick">
            {x}
          </text>
        ))}
        <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle" className="tick">
          participants per arm
        </text>
        {series.map((s) => (
          <g key={s.key}>
            <path
              d={s.points.map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join("")}
              fill="none"
              stroke={s.colour}
              strokeWidth={2}
              strokeDasharray={s.dash}
            />
            {s.points.map((p) => (
              <circle key={p.x} cx={X(p.x)} cy={Y(p.y)} r={3} fill={s.colour} />
            ))}
          </g>
        ))}
      </svg>
      <figcaption className="legend">
        {series.map((s) => (
          <span key={s.key}>
            <svg width="22" height="8" aria-hidden="true">
              <line x1="0" x2="22" y1="4" y2="4" stroke={s.colour} strokeWidth="2" strokeDasharray={s.dash} />
            </svg>{" "}
            {s.label}
          </span>
        ))}
        <span>dashed grey = {pct(target)} power</span>
      </figcaption>
    </figure>
  );
}
