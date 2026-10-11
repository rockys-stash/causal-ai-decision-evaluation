import { useState } from "react";
import { AiPanel, CaseCard } from "../components/CaseView";
import { PowerCurve } from "../components/charts";
import { DataTable } from "../components/DataTable";
import { useTopic } from "../components/Topic";
import { Loading, PageHead, Segmented } from "../components/ui";
import { type AiReport, type Arm, type Bank, type Item, type Power, useApi } from "../lib/api";
import { ARM_LABEL, num, pct } from "../lib/format";
import { DOMAIN_LABEL } from "../lib/pops";

function Preview() {
  const bank = useApi<Bank>("/api/lab/bank");
  const [arm, setArm] = useState<Arm>("C");
  const [caseId, setCaseId] = useState("loan-01");
  const item = useApi<Item>(`/api/lab/preview/${arm}/${caseId}`);
  return (
    <section className="panel" aria-labelledby="prev-head">
      <div className="panel-head">
        <h2 id="prev-head">What each arm sees</h2>
        <Segmented label="Arm" options={(["A", "B", "C"] as const).map((a) => ({ id: a, label: `${a} · ${ARM_LABEL[a]}` }))} value={arm} onChange={setArm} />
      </div>
      <div className="panel-body stack">
        <div className="controls">
          <label htmlFor="case-pick">Case</label>
          <select id="case-pick" value={caseId} onChange={(e) => setCaseId(e.target.value)}>
            {(bank.data?.cases ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.id} · {DOMAIN_LABEL[c.domain] ?? c.domain}
              </option>
            ))}
          </select>
        </div>
        {item.data ? (
          <>
            <h3 className="question small-q">{item.data.question}</h3>
            <div className={item.data.ai ? "task-grid" : "task-grid single"}>
              <CaseCard item={item.data} />
              {item.data.ai && <AiPanel ai={item.data.ai} />}
            </div>
          </>
        ) : (
          <Loading label="Loading the preview" rows={4} />
        )}
        <p className="small muted">
          Every arm sees the same fields. Arm B adds the recommendation; arm C adds its calibrated confidence and the three strongest factors on
          each side, from the same logistic model. The case order is randomized per participant.
        </p>
      </div>
    </section>
  );
}

const SERIES = [
  { key: "C−A", label: "C − A", colour: "var(--arm-c)" },
  { key: "B−A", label: "B − A", colour: "var(--arm-b)", dash: "6 4" },
  { key: "C−B", label: "C − B", colour: "var(--ink-3)", dash: "2 3" },
];

function PowerPanel() {
  const pw = useTopic<Power>("power");
  if (!pw.data) return null;
  const p = pw.data;
  const xs = p.curve.map((c) => c.per_arm);
  return (
    <section className="panel" aria-labelledby="pow-head">
      <div className="panel-head">
        <h2 id="pow-head">Validation by simulation and power</h2>
      </div>
      <div className="panel-body stack">
        <p className="small">
          Type I error with no effect: {pct(p.type1.any_contrast, 1)} of {num(p.type1.repetitions)} simulated studies ({p.type1.per_arm} per arm) found any
          significant contrast after Holm (nominal 5%). Expected accuracy under the planted design: A {pct(p.expected_accuracy.planted?.A, 1)}, B{" "}
          {pct(p.expected_accuracy.planted?.B, 1)}, C {pct(p.expected_accuracy.planted?.C, 1)}.
        </p>
        <PowerCurve
          title="Power to detect the planted effects"
          xs={xs}
          series={SERIES.map((s) => ({ ...s, points: p.curve.map((c) => ({ x: c.per_arm, y: Number(c[s.key] ?? 0) })) }))}
        />
        <p className="small">
          Power for a 6-percentage-point accuracy gain:{" "}
          {p.six_points.map((s) => `${s.per_arm} per arm ${pct(s.power)}`).join(", ")}.{" "}
          {p.human_per_arm ? (
            <strong>The human study needs {p.human_per_arm} participants per arm ({p.human_per_arm * 3} in all).</strong>
          ) : (
            "None of the simulated sizes reached 80%."
          )}
        </p>
      </div>
    </section>
  );
}

function AiPanelReport() {
  const ai = useTopic<AiReport>("ai");
  if (!ai.data) return null;
  return (
    <section className="panel" aria-labelledby="ai-rep-head">
      <div className="panel-head">
        <h2 id="ai-rep-head">The AI</h2>
      </div>
      <div className="panel-body stack-sm">
        <p className="small muted">
          One logistic regression per domain, regularization chosen by cross-validated log loss, then Platt-scaled on a separate calibration split.
          Gradient boosting is fitted only as a reference for how much accuracy the interpretable model gives up.
        </p>
        <DataTable
          caption="AI performance by domain"
          rows={Object.entries(ai.data).map(([d, v]) => ({ d, ...v }))}
          rowKey={(r) => r.d}
          columns={[
            { key: "d", label: "Domain", render: (r) => DOMAIN_LABEL[r.d] ?? r.d },
            { key: "rows", label: "Records", align: "r", render: (r) => num(r.rows) },
            { key: "auc", label: "Test AUROC", align: "r", render: (r) => num(r.test.auroc, 3) },
            { key: "gb", label: "Boosting AUROC", align: "r", render: (r) => num(r.boosting_test_auroc, 3) },
            { key: "bacc", label: "Bank accuracy", align: "r", render: (r) => pct(r.bank.ai_accuracy, 1), title: "On the 40 study cases in this domain" },
            { key: "ece", label: "Test ECE", align: "r", render: (r) => num(r.test.ece_balanced, 3) },
          ]}
        />
      </div>
    </section>
  );
}

export function Design() {
  return (
    <div className="stack">
      <PageHead title="Design">
        Pre-registered before any session: three arms between subjects, blocked randomization within each stratum, 24 scored cases per
        participant.
      </PageHead>
      <Preview />
      <section className="panel" aria-labelledby="prereg-head">
        <div className="panel-head">
          <h2 id="prereg-head">Pre-registered analysis</h2>
        </div>
        <dl className="kv panel-body">
          <dt>Primary outcome</dt>
          <dd>Participant accuracy over the 24 scored cases (8 per domain, 4 with each outcome).</dd>
          <dt>Tests</dt>
          <dd>C − A, B − A, C − B by permutation of arm labels within strata (10,000 permutations), Holm correction across the three.</dd>
          <dt>Effect sizes</dt>
          <dd>Difference in percentage points with a 5,000-resample bootstrap interval, Cohen's h, relative error reduction.</dd>
          <dt>Robustness</dt>
          <dd>GEE logistic regression on decisions, clustered by participant, with domain as a covariate.</dd>
          <dt>Secondary</dt>
          <dd>Cost under each domain's error costs, decision time, override (C − B), appropriate reliance, Brier score, subgroup error gaps.</dd>
          <dt>Exclusions</dt>
          <dd>People failing both attention checks or not finishing; model participants with more than 20% unanswered decisions.</dd>
        </dl>
      </section>
      <PowerPanel />
      <AiPanelReport />
    </div>
  );
}
