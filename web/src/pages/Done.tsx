import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loading, PageHead } from "../components/ui";
import { ApiError, type Next, send } from "../lib/api";
import { getSession, setSession } from "../lib/session";

function Scale({ id, label, value, onChange }: { id: string; label: string; value: number | null; onChange: (v: number) => void }) {
  return (
    <fieldset className="scale">
      <legend>{label}</legend>
      <div className="scale-row">
        {[1, 2, 3, 4, 5, 6, 7].map((v) => (
          <label key={v} className={value === v ? "choice selected" : "choice"}>
            <input type="radio" name={id} value={v} checked={value === v} onChange={() => onChange(v)} />
            {v}
          </label>
        ))}
      </div>
      <p className="meter-scale scale-ends small muted">
        <span>1 = not at all</span>
        <span>7 = completely</span>
      </p>
    </fieldset>
  );
}

export function Done() {
  const sid = getSession();
  const [arm, setArm] = useState<string>("");
  const [trust, setTrust] = useState<number | null>(null);
  const [useful, setUseful] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    if (!sid) return;
    send<Next>("GET", `/api/sessions/${sid}/next`)
      .then((n) => setArm(n.arm))
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [sid]);
  if (!sid && !code)
    return (
      <div className="state">
        <h2>No study session in this tab</h2>
        <p className="secondary">
          <Link to="/study">Start from the beginning</Link>.
        </p>
      </div>
    );
  if (code)
    return (
      <div className="narrow">
        <PageHead title="Thank you">Your answers are saved. Your completion code is shown below.</PageHead>
        <p className="code-box">
          <code>{code}</code>
        </p>
        <p className="secondary small">
          In this study, every case came from a public dataset of past decisions, and the right answer was what actually happened. Some
          participants saw an AI recommendation and some did not; the study compares how accurate decisions are in each version.
        </p>
      </div>
    );
  if (!arm && !error) return <Loading label="Loading" rows={3} />;
  const ai = arm === "B" || arm === "C";
  return (
    <div className="narrow">
      <PageHead title="Nearly done">All decisions are saved. A few questions to finish.</PageHead>
      <form
        className="panel panel-body stack"
        onSubmit={(e) => {
          e.preventDefault();
          send<{ code: string }>("POST", `/api/sessions/${sid}/survey`, { trust, usefulness: useful, comment })
            .then((r) => {
              setCode(r.code);
              setSession("");
            })
            .catch((err: unknown) => setError(err instanceof ApiError ? err.message : String(err)));
        }}
      >
        {ai && <Scale id="trust" label="How much did you trust the AI's recommendations?" value={trust} onChange={setTrust} />}
        {ai && <Scale id="useful" label="How useful were they for your decisions?" value={useful} onChange={setUseful} />}
        <div className="field-col">
          <label htmlFor="comment">Anything you would like to tell us (optional)</label>
          <textarea id="comment" maxLength={1000} rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
        </div>
        {error && (
          <p className="bad small" role="alert">
            {error}
          </p>
        )}
        <div>
          <button className="btn primary" type="submit" disabled={ai && (trust === null || useful === null)}>
            Finish
          </button>
        </div>
      </form>
    </div>
  );
}
