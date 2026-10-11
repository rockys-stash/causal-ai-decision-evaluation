import { useCallback, useEffect, useRef, useState } from "react";

/* ---------- types mirrored from the API (src/declab/api.py, analysis.py) ---------- */
export type Arm = "A" | "B" | "C";

export interface Factor {
  field: string;
  label: string;
  value: string;
  weight: number;
  strength: "weak" | "moderate" | "strong";
}

export interface Explanation {
  towards_positive: Factor[];
  towards_negative: Factor[];
  positive_label: string;
  negative_label: string;
}

export interface AiShown {
  decision: string;
  label: string;
  confidence?: number;
  explanation?: Explanation;
}

export interface Item {
  index: number;
  total: number;
  phase: "practice" | "task" | "attention";
  case_id: string;
  domain: string;
  domain_label: string;
  question: string;
  card: { field: string; label: string; value: string }[];
  options: { decision: string; label: string }[];
  ai: AiShown | null;
}

export interface Next {
  done: boolean;
  arm: Arm;
  completed?: boolean;
  item?: Item;
}

export interface StudyInfo {
  arms: Record<Arm, string>;
  cases: number;
  practice: number;
  domains: Record<string, { label: string; question: string }>;
}

export interface Provenance {
  run_id: string;
  commit: string;
  dirty: boolean;
  quick: boolean;
  created_at: string;
  runtime_seconds: number;
  python: string;
  permutations: number;
  bootstrap: number;
  packages: Record<string, string>;
  inputs_sha256: Record<string, string>;
}

export interface PopSummary {
  label: string;
  kind: "simulated" | "model" | "human";
  status: string;
  sessions: number;
  participants: number;
  decisions: number | null;
  chain_ok: boolean | null;
  file: string;
}

export interface Overview {
  populations: Record<string, PopSummary>;
  human_study: string;
  arms: Record<Arm, string>;
  quick: boolean;
}

export interface ArmRow {
  arm: Arm;
  participants: number;
  accuracy: number;
  accuracy_sd: number;
  cost: number;
  median_seconds: number;
  agree: number;
  agree_right: number;
  agree_wrong: number;
  appropriate: number;
  brier: number;
  confidence: number;
  ai_accuracy: number;
  ai_cost: number;
}

export interface Contrast {
  contrast: string;
  outcome: string;
  mean_a?: number | null;
  mean_b?: number | null;
  n_a?: number;
  n_b?: number;
  diff: number | null;
  ci?: [number, number] | null;
  p: number | null;
  p_holm?: number;
  cohens_h?: number;
  error_reduction?: number | null;
  domain?: string;
  groups?: [string, string];
  arm_a?: { gap: number; error_1: number; error_2: number; n_1: number; n_2: number };
  arm_b?: { gap: number; error_1: number; error_2: number; n_1: number; n_2: number };
}

export interface Population extends PopSummary {
  missing_decisions?: number;
  excluded?: { session: string; arm: Arm; excluded: string }[];
  chain?: string;
  models?: string[];
  arms?: ArmRow[];
  primary?: Contrast[];
  gee?: Record<string, { odds_ratio: number; ci: [number, number]; p: number }> | { error: string };
}

export type Primary = Record<string, Population>;
export type Secondary = Record<string, Contrast[] | null>;

export interface Reliance {
  arms: ArmRow[] | null;
  by_domain: { arm: Arm; domain: string; accuracy: number; agree: number; ai_accuracy: number; decisions: number }[] | null;
  by_model: { model: string; arm: Arm; participants: number; accuracy: number; agree: number; appropriate: number; confidence: number; seconds: number }[] | null;
  participants: { session: string; model: string; arm: Arm; n: number; missing: number; accuracy: number; agree: number; appropriate: number; confidence: number; median_seconds: number }[] | null;
}

export interface CalBin {
  bin: [number, number];
  n: number;
  confidence: number | null;
  accuracy: number | null;
}

export type Calibration = Record<string, Record<string, { ece: number; brier: number; mean_confidence: number; accuracy: number; curve: CalBin[] }> | null>;

export interface Power {
  permutations_per_test: number;
  expected_accuracy: Record<string, Record<Arm, number>>;
  type1: { per_arm: number; repetitions: number; any_contrast: number; by_contrast: Record<string, number> };
  curve: ({ per_arm: number; repetitions: number } & Record<string, number>)[];
  six_points: { per_arm: number; repetitions: number; power: number }[];
  human_per_arm: number | null;
}

export interface AiDomain {
  rows: number;
  base_rate: number;
  split: [number, number, number];
  test: { auroc: number; accuracy_balanced: number; tpr: number; tnr: number; ece_balanced: number; brier_balanced: number; n: number; positives: number };
  boosting_test_auroc: number;
  bank: { cases: number; ai_accuracy: number; ai_ece: number; auroc: number };
  model: { c: number };
}

export type AiReport = Record<string, AiDomain>;

export interface LogBatch {
  batch: string;
  label: string;
  status: "logged" | "pending";
  sessions: number;
  completed?: number;
  events: number;
  chain_ok?: boolean;
  chain?: string;
}

export interface LogSession {
  session: string;
  kind: string;
  model: string | null;
  label: string | null;
  arm: Arm;
  slot: number;
  started: string;
  decisions: number;
  correct: number;
  items: number;
  completed: boolean;
}

export interface LogEvent {
  seq: number;
  ts: string;
  session: string;
  kind: string;
  data: Record<string, unknown>;
  prev: string;
  hash: string;
}

export interface SessionDetail {
  events: LogEvent[];
  items: Item[];
  outcomes: Record<string, { right: string; ai: string } | null>;
}

export interface BankCase {
  id: string;
  domain: string;
  outcome: number;
  subgroup: string;
  card: { field: string; label: string; value: string }[];
  ai: { decision: string; label: string; p_positive: number; confidence: number; explanation: Explanation };
}

export interface Bank {
  cases: BankCase[];
  practice: BankCase[];
}

/* ---------- fetching ---------- */
export class ApiError extends Error {
  constructor(
    public url: string,
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const cache = new Map<string, unknown>();

const TOKEN_KEY = "decision-lab-token";

/** The researcher token for a server started with DECLAB_TOKEN, kept for this browser tab only. */
export function getToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(token: string): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: the token is not remembered */
  }
  cache.clear();
}

function headers(): Record<string, string> {
  const t = getToken();
  return t ? { Accept: "application/json", Authorization: `Bearer ${t}` } : { Accept: "application/json" };
}

export async function getJson<T>(url: string): Promise<T> {
  if (cache.has(url)) return cache.get(url) as T;
  let res: Response;
  try {
    res = await fetch(url, { headers: headers() });
  } catch {
    throw new ApiError(url, 0, "The Decision Lab server could not be reached.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(url, res.status, detail);
  }
  const data = (await res.json()) as T;
  cache.set(url, data);
  return data;
}

export interface ApiState<T> {
  data: T | undefined;
  error: ApiError | undefined;
  loading: boolean;
  retry: () => void;
}

export function useApi<T>(url: string | null): ApiState<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<ApiError | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(url !== null);
  const [nonce, setNonce] = useState(0);
  const current = useRef(url);

  useEffect(() => {
    current.current = url;
    if (url === null) {
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(undefined);
    getJson<T>(url)
      .then((d) => {
        if (alive && current.current === url) setData(d);
      })
      .catch((e: unknown) => {
        if (alive && current.current === url)
          setError(e instanceof ApiError ? e : new ApiError(url, 0, String(e)));
      })
      .finally(() => {
        if (alive && current.current === url) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [url, nonce]);

  const retry = useCallback(() => {
    if (url) cache.delete(url);
    setNonce((n) => n + 1);
  }, [url]);

  return { data, error, loading, retry };
}

export const result = (name: string) => `/api/lab/results/${name}`;

/** Participant calls: never cached, JSON in and out. */
export async function send<T>(method: "GET" | "POST", url: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: body === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(url, 0, "The study server could not be reached. Check your connection and try again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const b = (await res.json()) as { detail?: unknown };
      if (typeof b.detail === "string") detail = b.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(url, res.status, detail);
  }
  return (await res.json()) as T;
}
