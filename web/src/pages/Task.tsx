import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AiPanel, CaseCard } from "../components/CaseView";
import { Loading } from "../components/ui";
import { ApiError, type Next, send } from "../lib/api";
import { getSession } from "../lib/session";

export function Task() {
  const nav = useNavigate();
  const sid = getSession();
  const [next, setNext] = useState<Next | null>(null);
  const [choice, setChoice] = useState("");
  const [conf, setConf] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const shownAt = useRef(0);

  const load = useCallback(async () => {
    setError("");
    try {
      const n = await send<Next>("GET", `/api/sessions/${sid}/next`);
      if (n.done) {
        nav("/study/done");
        return;
      }
      setNext(n);
      setChoice("");
      setConf(null);
      shownAt.current = performance.now();
      window.scrollTo({ top: 0 });
      document.getElementById("main")?.focus({ preventScroll: true });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, [sid, nav]);

  useEffect(() => {
    if (sid) void load();
  }, [sid, load]);

  if (!sid)
    return (
      <div className="state">
        <h2>No study session in this tab</h2>
        <p className="secondary">
          <Link to="/study">Start from the beginning</Link>.
        </p>
      </div>
    );
  if (error && !next)
    return (
      <div className="state error" role="alert">
        <h2>Something went wrong</h2>
        <p className="secondary">{error}</p>
        <button className="btn" type="button" onClick={() => void load()}>
          Try again
        </button>
      </div>
    );
  if (!next?.item) return <Loading label="Loading the next case" rows={6} />;
  const it = next.item;

  async function submit() {
    if (!choice || conf === null) return;
    setBusy(true);
    try {
      await send("POST", `/api/sessions/${sid}/decisions`, {
        index: it.index,
        decision: choice,
        confidence: conf,
        client_ms: Math.round(performance.now() - shownAt.current),
      });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="task">
      <div className="progress-row">
        <p className="small muted" aria-live="polite">
          Decision {it.index + 1} of {it.total}
        </p>
        <div className="progress" role="progressbar" aria-label="Progress" aria-valuemin={0} aria-valuemax={it.total} aria-valuenow={it.index}>
          <span style={{ width: `${(it.index / it.total) * 100}%` }} />
        </div>
      </div>
      <h1 className="question">{it.question}</h1>
      <div className={it.ai ? "task-grid" : "task-grid single"}>
        <CaseCard item={it} />
        {it.ai && <AiPanel ai={it.ai} />}
      </div>
      <form
        className="panel decide"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <fieldset>
          <legend>Your decision</legend>
          <div className="choices">
            {it.options.map((o) => (
              <label key={o.decision} className={choice === o.decision ? "choice selected" : "choice"}>
                <input type="radio" name="decision" value={o.decision} checked={choice === o.decision} onChange={() => setChoice(o.decision)} />
                {o.label}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="confidence">
          <label htmlFor="conf">
            How confident are you that your decision is right?{" "}
            <strong>{conf === null ? "move the slider" : `${conf}%`}</strong>
          </label>
          <input
            id="conf"
            type="range"
            min={50}
            max={100}
            step={5}
            value={conf ?? 75}
            className={conf === null ? "unset" : ""}
            aria-valuetext={conf === null ? "not set" : `${conf} percent`}
            onChange={(e) => setConf(Number(e.target.value))}
            onClick={(e) => setConf(Number((e.target as HTMLInputElement).value))}
          />
          <p className="meter-scale small muted" aria-hidden="true">
            <span>50% (a guess)</span>
            <span>100% (certain)</span>
          </p>
        </div>
        {error && (
          <p className="bad small" role="alert">
            {error}
          </p>
        )}
        <button className="btn primary" type="submit" disabled={!choice || conf === null || busy}>
          {busy ? "Saving…" : "Confirm and continue"}
        </button>
      </form>
    </div>
  );
}
