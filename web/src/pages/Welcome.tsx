import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHead } from "../components/ui";
import { ApiError, send } from "../lib/api";
import { setSession } from "../lib/session";

export function Welcome() {
  const nav = useNavigate();
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function start() {
    setBusy(true);
    setError("");
    try {
      const r = await send<{ session: string }>("POST", "/api/sessions", { consent: true });
      setSession(r.session);
      nav("/study/task");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setBusy(false);
    }
  }
  return (
    <div className="narrow">
      <PageHead title="A study of business decisions">
        You will see 26 real past cases from three kinds of business decision: whether to approve a loan, whether to call a bank client about a
        savings product, and whether to reduce a credit-card limit. For each, choose what you would decide and say how confident you are.
      </PageHead>
      <section className="panel" aria-labelledby="about-head">
        <div className="panel-head">
          <h2 id="about-head">Before you start</h2>
        </div>
        <div className="panel-body stack small">
          <p>
            Every case really happened, so each decision has a right answer: what the applicant or client actually did. Half of the cases in
            this study went each way. The first two cases are practice and are not scored, and two of the screens are attention checks.
          </p>
          <p>
            Depending on the version of the study you are given, you may also see a recommendation from an AI system. Use it as you see fit. You
            will not be told during the study which answers were right.
          </p>
          <p>
            It takes about 15 minutes. We record your choices, your confidence and how long each decision takes, and a short questionnaire at the
            end. We do not ask for your name or any contact details. You can stop at any time by closing this page.
          </p>
          <div className="check">
            <input id="consent" type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <label htmlFor="consent">I have read this and agree to take part.</label>
          </div>
          {error && (
            <p className="bad" role="alert">
              {error}
            </p>
          )}
          <div>
            <button className="btn primary" type="button" disabled={!consent || busy} onClick={() => void start()}>
              {busy ? "Starting…" : "Start the study"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
