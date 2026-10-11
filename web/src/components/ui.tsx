import { type ReactNode, useState } from "react";
import { type ApiError, type Provenance, setToken } from "../lib/api";

export function Skeleton({
  height = 16,
  width = "100%",
}: {
  height?: number;
  width?: number | string;
}) {
  return (
    <div className="skeleton" style={{ height, width }} aria-hidden="true" />
  );
}

export function Loading({
  rows = 5,
  label = "Loading",
}: {
  rows?: number;
  label?: string;
}) {
  return (
    <div className="panel" role="status" aria-live="polite">
      <span className="sr-only">{label}…</span>
      <div className="panel-body stack">
        <Skeleton height={20} width="40%" />
        {Array.from({ length: rows }, (_, i) => (
          <Skeleton key={i} height={26} />
        ))}
      </div>
    </div>
  );
}

/** A 404 from the API means the experiment has not been run: that is an empty state, not an error. */
export function ErrorOrPending({
  error,
  retry,
  what,
  command,
}: {
  error: ApiError;
  retry: () => void;
  what: string;
  command: string;
}) {
  if (error.status === 401) return <TokenForm onSaved={retry} />;
  if (error.status === 404)
    return (
      <Empty title={`No results for ${what} yet`}>
        <p>
          Status: pending. Nothing is drawn until the analysis has run on
          logged sessions. Run:
        </p>
        <pre className="cmd">
          <code>{command}</code>
        </pre>
      </Empty>
    );
  return (
    <div className="state error" role="alert">
      <h2>Could not load {what}</h2>
      <p className="secondary">
        {error.status ? `HTTP ${error.status}: ` : ""}
        {error.message}
      </p>
      <button className="btn" type="button" onClick={retry}>
        Retry
      </button>
    </div>
  );
}

export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="state">
      <h2>{title}</h2>
      {children && <div className="secondary">{children}</div>}
    </div>
  );
}

export function Segmented<T extends string | number>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { id: T; label: string; title?: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={String(o.id)}
          type="button"
          aria-pressed={o.id === value}
          title={o.title}
          onClick={() => onChange(o.id)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function ProvenanceLine({ p }: { p: Provenance }) {
  return (
    <p className="muted small provenance">
      Analysis <code>results/{p.run_id}</code> · commit <code>{p.commit.slice(0, 7)}</code>
      {p.dirty ? " (uncommitted changes)" : ""}
      {p.quick ? " · quick settings, not a result" : ""} · {p.permutations.toLocaleString("en-GB")} permutations · pre-registered plan
    </p>
  );
}

export function PageHead({
  title,
  children,
  actions,
}: {
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {children && <p>{children}</p>}
      </div>
      {actions}
    </div>
  );
}


/** Shown when the server was started with WFINTEL_TOKEN and this tab has no (or a wrong) token. */
export function TokenForm({ onSaved }: { onSaved: () => void }) {
  const [value, setValue] = useState("");
  return (
    <form
      className="state"
      onSubmit={(e) => {
        e.preventDefault();
        setToken(value.trim());
        onSaved();
      }}
    >
      <h2>Access token needed</h2>
      <p className="secondary">
        The researcher console requires the token the server was started with
        (DECLAB_TOKEN). It is kept for this browser tab only.
      </p>
      <div className="field">
        <label htmlFor="token">Token</label>
        <input
          id="token"
          type="password"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <button className="btn primary" type="submit" disabled={!value.trim()}>
          Use token
        </button>
      </div>
    </form>
  );
}

/** Pass/fail shown with a glyph and a word, never by colour alone. */
export function PassMark({ passed }: { passed: boolean | undefined }) {
  if (passed === undefined) return <span className="muted">–</span>;
  return passed ? (
    <span className="ok">✓ pass</span>
  ) : (
    <span className="bad">✗ fail</span>
  );
}
