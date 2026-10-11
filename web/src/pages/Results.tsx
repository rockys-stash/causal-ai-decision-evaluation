import { useState } from "react";
import { ContrastPlot } from "../components/charts";
import { DataTable } from "../components/DataTable";
import { Gate, useTopic } from "../components/Topic";
import { Empty, PageHead, Segmented } from "../components/ui";
import type { Contrast, Primary, Secondary } from "../lib/api";
import { ARM_LABEL, num, pct, pp, pval, signed } from "../lib/format";
import { OUTCOME_LABEL, POP_NOTE, POPS, type PopId } from "../lib/pops";

export function PopPicker({ value, onChange }: { value: PopId; onChange: (v: PopId) => void }) {
  return <Segmented label="Session population" options={POPS.map((p) => ({ id: p.id, label: p.label, title: p.title }))} value={value} onChange={onChange} />;
}

function diffText(c: Contrast) {
  if (c.outcome === "log_seconds") return `${signed(c.diff, 3)} log s`;
  if (c.outcome === "cost") return signed(c.diff, 3);
  if (c.outcome === "brier" || c.outcome === "appropriate") return signed(c.diff, 3);
  return `${pp(c.diff)} pp`;
}

export function Results() {
  const [pop, setPop] = useState<PopId>("model");
  const pr = useTopic<Primary>("primary");
  const sec = useTopic<Secondary>("secondary");
  return (
    <Gate state={pr} title="Results" what="the results">
      {(all) => {
        const p = all[pop];
        const secRows = (sec.data?.[pop] ?? []).filter((c) => !c.outcome.startsWith("gap_"));
        return (
          <div className="stack">
            <PageHead title="Results" actions={<PopPicker value={pop} onChange={setPop} />}>
              Primary outcome: share of the 24 scored decisions that were right. Contrasts are tested by permutation within strata and corrected
              with Holm across the three pairs; intervals are 95% bootstrap intervals over participants.
            </PageHead>
            <p className={pop === "human" ? "callout" : "callout muted-callout"} role="note">
              <strong>{POPS.find((x) => x.id === pop)?.title}.</strong> {POP_NOTE[pop]}
            </p>
            {!p?.arms ? (
              <Empty title="No sessions in this population">Status: pending. Nothing is shown until sessions are logged and analysed.</Empty>
            ) : (
              <>
                <section className="panel" aria-labelledby="arms-head">
                  <div className="panel-head">
                    <h2 id="arms-head">By arm</h2>
                    <span className="muted small">
                      {num(p.participants)} participants · {num(p.decisions)} scored decisions
                      {p.missing_decisions ? ` · ${p.missing_decisions} missing` : ""}
                    </span>
                  </div>
                  <DataTable
                    caption="Outcomes by arm"
                    rows={p.arms}
                    rowKey={(r) => r.arm}
                    columns={[
                      { key: "arm", label: "Arm", render: (r) => `${r.arm} · ${ARM_LABEL[r.arm]}` },
                      { key: "n", label: "Participants", align: "r", render: (r) => num(r.participants) },
                      { key: "acc", label: "Accuracy", align: "r", render: (r) => pct(r.accuracy, 1) },
                      { key: "sd", label: "SD", align: "r", render: (r) => pct(r.accuracy_sd, 1) },
                      { key: "cost", label: "Cost / decision", align: "r", render: (r) => num(r.cost, 3) },
                      { key: "sec", label: "Median seconds", align: "r", render: (r) => num(r.median_seconds, 1) },
                      { key: "conf", label: "Mean confidence", align: "r", render: (r) => `${num(r.confidence, 1)}%` },
                      { key: "ai", label: "AI alone", align: "r", render: (r) => pct(r.ai_accuracy, 1), title: "Accuracy of the AI's recommendation on the same cases" },
                    ]}
                  />
                </section>
                {p.primary && (
                  <section className="panel" aria-labelledby="prim-head">
                    <div className="panel-head">
                      <h2 id="prim-head">Primary contrasts: accuracy</h2>
                    </div>
                    <div className="panel-body stack">
                      <ContrastPlot title="Accuracy differences between arms" rows={p.primary} />
                      <DataTable
                        caption="Primary contrasts with Holm correction"
                        rows={p.primary}
                        rowKey={(r) => r.contrast}
                        columns={[
                          { key: "c", label: "Contrast", render: (r) => r.contrast },
                          { key: "d", label: "Difference", align: "r", render: (r) => `${pp(r.diff)} pp` },
                          { key: "ci", label: "95% interval", align: "r", render: (r) => (r.ci ? `${pp(r.ci[0])} to ${pp(r.ci[1])}` : "–") },
                          { key: "p", label: "p", align: "r", render: (r) => pval(r.p) },
                          { key: "ph", label: "p (Holm)", align: "r", render: (r) => pval(r.p_holm) },
                          { key: "h", label: "Cohen's h", align: "r", render: (r) => signed(r.cohens_h, 2) },
                          { key: "er", label: "Error reduction", align: "r", render: (r) => pct(r.error_reduction), title: "Relative fall in the error rate" },
                        ]}
                      />
                      {p.gee && !("error" in p.gee) && (
                        <p className="small">
                          Robustness (GEE logistic, decisions clustered by participant, domain as covariate):{" "}
                          {Object.entries(p.gee)
                            .map(([k, g]) => `${k.replace("_vs_", " vs ")} odds ratio ${num(g.odds_ratio, 2)} (${num(g.ci[0], 2)}–${num(g.ci[1], 2)}), p ${pval(g.p)}`)
                            .join("; ")}
                          .
                        </p>
                      )}
                      {p.excluded && p.excluded.length > 0 && (
                        <p className="small muted">
                          Excluded under the pre-registered rules: {p.excluded.map((e) => `${e.session.slice(0, 8)} (arm ${e.arm}: ${e.excluded})`).join(", ")}.
                        </p>
                      )}
                    </div>
                  </section>
                )}
                {secRows.length > 0 && (
                  <section className="panel" aria-labelledby="sec-head">
                    <div className="panel-head">
                      <h2 id="sec-head">Secondary outcomes</h2>
                      <span className="muted small">Holm within the secondary family; exploratory</span>
                    </div>
                    <DataTable
                      caption="Secondary contrasts"
                      rows={secRows}
                      rowKey={(r) => `${r.outcome}-${r.contrast}`}
                      columns={[
                        { key: "o", label: "Outcome", render: (r) => OUTCOME_LABEL[r.outcome] ?? r.outcome, wrap: true },
                        { key: "c", label: "Contrast", render: (r) => r.contrast },
                        { key: "m", label: "Means", align: "r", render: (r) => `${num(r.mean_a, 3)} → ${num(r.mean_b, 3)}` },
                        { key: "d", label: "Difference", align: "r", render: (r) => diffText(r) },
                        { key: "ci", label: "95% interval", align: "r", render: (r) => (r.ci ? `${signed(r.ci[0], 3)} to ${signed(r.ci[1], 3)}` : "–") },
                        { key: "ph", label: "p (Holm)", align: "r", render: (r) => pval(r.p_holm) },
                      ]}
                    />
                  </section>
                )}
                <Subgroups pop={pop} />
              </>
            )}
          </div>
        );
      }}
    </Gate>
  );
}

function Subgroups({ pop }: { pop: PopId }) {
  const sg = useTopic<Record<string, Contrast[] | null>>("subgroups");
  const rows = sg.data?.[pop];
  if (!rows?.length) return null;
  return (
    <section className="panel" aria-labelledby="sg-head">
      <div className="panel-head">
        <h2 id="sg-head">Fairness: error gaps between subgroups</h2>
      </div>
      <div className="panel-body stack-sm">
        <p className="small muted">
          Gap = error rate in the first group minus the second, within the domain. The contrast asks whether AI advice widens or narrows the gap.
          The subgroups have few cases each, so these intervals are wide.
        </p>
        <DataTable
          caption="Subgroup error gaps by arm"
          rows={rows}
          rowKey={(r) => `${r.outcome}-${r.contrast}`}
          columns={[
            { key: "o", label: "Domain and groups", render: (r) => `${OUTCOME_LABEL[r.outcome] ?? r.outcome}`, wrap: true },
            { key: "c", label: "Contrast", render: (r) => r.contrast },
            { key: "a", label: "Gap, reference arm", align: "r", render: (r) => `${r.contrast.split("−")[1] ?? ""}: ${pp(r.arm_a?.gap)} pp` },
            { key: "b", label: "Gap, compared arm", align: "r", render: (r) => `${r.contrast.split("−")[0] ?? ""}: ${pp(r.arm_b?.gap)} pp` },
            { key: "d", label: "Change", align: "r", render: (r) => `${pp(r.diff)} pp` },
            { key: "ph", label: "p (Holm)", align: "r", render: (r) => pval(r.p_holm) },
          ]}
        />
      </div>
    </section>
  );
}
