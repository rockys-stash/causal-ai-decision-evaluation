import { useTopic } from "../components/Topic";
import { PageHead, ProvenanceLine } from "../components/ui";
import type { Provenance } from "../lib/api";

export function Method() {
  const prov = useTopic<Provenance>("provenance");
  return (
    <div className="stack prose">
      <PageHead title="Method">How the study works, what each population is, and what can and cannot be concluded.</PageHead>
      <section className="panel panel-body stack-sm" aria-labelledby="m-cases">
        <h2 id="m-cases">Cases</h2>
        <p>
          Three public datasets from the UCI Machine Learning Repository (CC BY 4.0), fetched by URL and checked against pinned SHA-256 hashes:
          Statlog German Credit (loan approval), Bank Marketing (whether to call a client about a term deposit) and Default of Credit Card
          Clients (whether to reduce a credit limit). Each record has a known outcome, so every decision has a right answer. 40 cases per domain
          were drawn from the held-out test split, 20 with each outcome, so that the AI's accuracy on them matches its test accuracy.
        </p>
      </section>
      <section className="panel panel-body stack-sm" aria-labelledby="m-arms">
        <h2 id="m-arms">Arms and randomization</h2>
        <p>
          A: the case only. B: the case and the AI's recommendation. C: the recommendation, its calibrated confidence and the factors that pushed
          it each way. Arms are assigned in blocks of six (two of each) within each stratum, from a seeded generator whose allocation list is
          hashed into every session's first event.
        </p>
      </section>
      <section className="panel panel-body stack-sm" aria-labelledby="m-pops">
        <h2 id="m-pops">Populations</h2>
        <ul>
          <li>
            <strong>Human participants: pending.</strong> The study runs in the browser at <code>/study</code>; no person has taken part. Running it
            needs ethics approval and recruitment.
          </li>
          <li>
            <strong>Simulated participants (dry run).</strong> A scripted behaviour model with effects planted on purpose, and a version with no
            effect. They test that the analysis recovers effects that exist and does not find ones that do not. They are not data.
          </li>
          <li>
            <strong>Model participants (pilot).</strong> Two open-weights language models (Qwen3-4B and Phi-4-mini, run locally) answer the same
            screens through the same API. They show that the pipeline works end to end and how these models use AI advice. They are not people.
          </li>
        </ul>
      </section>
      <section className="panel panel-body stack-sm" aria-labelledby="m-int">
        <h2 id="m-int">Integrity</h2>
        <p>
          Every session is an append-only log in which each event carries the hash of the one before it; the analysis refuses a log whose chain
          is broken. The plan and the analysis were committed before any session, and every later change is a dated amendment. Results are
          written to a versioned directory with the commit, settings and package versions.
        </p>
      </section>
      {prov.data && <ProvenanceLine p={prov.data} />}
    </div>
  );
}
