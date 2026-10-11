export function num(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return v.toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${(v * 100).toFixed(digits)}%`;
}

export function signedPct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const text = Math.abs(v * 100).toFixed(digits);
  if (Number(text) === 0) return `${text}%`;
  return `${v > 0 ? "+" : "−"}${text}%`;
}

/** p-values: "< 0.001" below that, three decimals otherwise. */
export function pval(p: number | null | undefined): string {
  if (p === null || p === undefined || Number.isNaN(p)) return "–";
  return p < 0.001 ? "< 0.001" : p.toFixed(3);
}

/** Signed number with a typographic minus. */
export function signed(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}`;
}

export const ARM_LABEL: Record<string, string> = {
  A: "Human only",
  B: "AI recommendation",
  C: "AI + uncertainty + explanation",
};

export const MODEL_LABEL: Record<string, string> = {
  "qwen3-4b": "Qwen3-4B",
  "phi-4-mini": "Phi-4-mini",
};

/** Percentage points with sign. */
export function pp(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(digits)}`;
}

/** Round axis ticks covering [lo, hi]. */
export function niceTicks(lo: number, hi: number, n = 4): number[] {
  const raw = (hi - lo) / n || 1;
  const mag = 10 ** Math.floor(Math.log10(Math.abs(raw)));
  const step = ([1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) ?? 10) * mag;
  const start = Math.floor(lo / step) * step;
  const out: number[] = [start];
  while ((out[out.length - 1] ?? hi) < hi - step * 1e-9) out.push(Number((start + out.length * step).toFixed(10)));
  return out;
}
