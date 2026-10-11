import { useState } from "react";
import { CalibrationPlot } from "../components/charts";
import { DataTable } from "../components/DataTable";
import { Gate, useTopic } from "../components/Topic";
import { Empty, PageHead } from "../components/ui";
import type { Calibration, Reliance as RelianceData } from "../lib/api";
import { ARM_LABEL, MODEL_LABEL, num, pct, signed } from "../lib/format";
import { DOMAIN_LABEL, POP_NOTE, POPS, type PopId } from "../lib/pops";
import { PopPicker } from "./Results";

export function Reliance() {
  const [pop, setPop] = useState<PopId>("model");
  const rel = useTopic<Record<string, RelianceData>>("reliance");
  const cal = useTopic<Calibration>("calibration");
  return (
    <Gate state={rel} title="Reliance & calibration" what="reliance">
      {(all) => {
        const r = all[pop];
        const c = cal.data?.[pop];
        return (
          <div className="stack">
            <PageHead title="Reliance & calibration" actions={<PopPicker value={pop} onChange={setPop} />}>
              How decisions follow the AI: agreement when the AI was right and when it was wrong, and whether stated confidence matches accuracy.
            </PageHead>
            <p className="callout muted-callout" role="note">
              <strong>{POPS.find((x) => x.id === pop)?.title}.</strong> {POP_NOTE[pop]}
            </p>
            {!r?.arms ? (
              <Empty title="No sessions in this population">Status: pending.</Empty>
            ) : (
              <>
                <section className="panel" aria-labelledby="rel-head">
                  <div className="panel-head">
                    <h2 id="rel-head">Agreement with the AI</h2>
                  </div>
                  <div className="panel-body stack-sm">
                    <p className="small muted">
                      In arm A nobody sees the AI, so its agreement is the baseline: how often an unaided decision happens to match the AI.
                      Appropriate reliance = agreement when the AI was right minus agreement when it was wrong (1 = follows it exactly when it is
                      right; 0 = no discrimination).
                    </p>
                    <DataTable
                      caption="Agreement with the AI by arm"
                      rows={r.arms}
                      rowKey={(x) => x.arm}
                      columns={[
                        { key: "arm", label: "Arm", render: (x) => `${x.arm} · ${ARM_LABEL[x.arm]}` },
                        { key: "ag", label: "Agree", align: "r", render: (x) => pct(x.agree, 1) },
                        { key: "ar", label: "Agree, AI right", align: "r", render: (x) => pct(x.agree_right, 1) },
                        { key: "aw", label: "Agree, AI wrong", align: "r", render: (x) => pct(x.agree_wrong, 1) },
                        { key: "ap", label: "Appropriate reliance", align: "r", render: (x) => signed(x.appropriate, 3) },
                        { key: "acc", label: "Accuracy", align: "r", render: (x) => pct(x.accuracy, 1) },
                        { key: "ai", label: "AI alone", align: "r", render: (x) => pct(x.ai_accuracy, 1) },
                      ]}
                    />
                  </div>
                </section>
                {c && (
                  <section className="panel" aria-labelledby="cal-head">
                    <div className="panel-head">
                      <h2 id="cal-head">Calibration of participants' confidence</h2>
                    </div>
                    <div className="panel-body grid-2">
                      <CalibrationPlot title="Confidence against accuracy by arm" curves={Object.fromEntries(Object.entries(c).map(([k, v]) => [k, v.curve]))} />
                      <DataTable
                        caption="Calibration by arm"
                        rows={Object.entries(c).map(([arm, v]) => ({ arm, ...v }))}
                        rowKey={(x) => x.arm}
                        columns={[
                          { key: "arm", label: "Arm", render: (x) => x.arm },
                          { key: "mc", label: "Mean confidence", align: "r", render: (x) => pct(x.mean_confidence, 1) },
                          { key: "acc", label: "Accuracy", align: "r", render: (x) => pct(x.accuracy, 1) },
                          { key: "ece", label: "ECE", align: "r", render: (x) => num(x.ece, 3), title: "Expected calibration error, 5 bins" },
                          { key: "b", label: "Brier", align: "r", render: (x) => num(x.brier, 3) },
                        ]}
                      />
                    </div>
                  </section>
                )}
                {r.by_domain && (
                  <section className="panel" aria-labelledby="dom-head">
                    <div className="panel-head">
                      <h2 id="dom-head">By domain</h2>
                    </div>
                    <DataTable
                      caption="Accuracy and agreement by domain and arm"
                      rows={r.by_domain}
                      rowKey={(x) => `${x.domain}-${x.arm}`}
                      columns={[
                        { key: "d", label: "Domain", render: (x) => DOMAIN_LABEL[x.domain] ?? x.domain },
                        { key: "arm", label: "Arm", render: (x) => x.arm },
                        { key: "n", label: "Decisions", align: "r", render: (x) => num(x.decisions) },
                        { key: "acc", label: "Accuracy", align: "r", render: (x) => pct(x.accuracy, 1) },
                        { key: "ag", label: "Agree with AI", align: "r", render: (x) => pct(x.agree, 1) },
                        { key: "ai", label: "AI alone", align: "r", render: (x) => pct(x.ai_accuracy, 1) },
                      ]}
                    />
                  </section>
                )}
                {r.by_model && (
                  <section className="panel" aria-labelledby="mod-head">
                    <div className="panel-head">
                      <h2 id="mod-head">By model</h2>
                    </div>
                    <DataTable
                      caption="Model participants by model and arm"
                      rows={r.by_model}
                      rowKey={(x) => `${x.model}-${x.arm}`}
                      columns={[
                        { key: "m", label: "Model", render: (x) => MODEL_LABEL[x.model] ?? x.model },
                        { key: "arm", label: "Arm", render: (x) => x.arm },
                        { key: "n", label: "Participants", align: "r", render: (x) => num(x.participants) },
                        { key: "acc", label: "Accuracy", align: "r", render: (x) => pct(x.accuracy, 1) },
                        { key: "ag", label: "Agree with AI", align: "r", render: (x) => pct(x.agree, 1) },
                        { key: "ap", label: "Appropriate", align: "r", render: (x) => signed(x.appropriate, 3) },
                        { key: "c", label: "Confidence", align: "r", render: (x) => `${num(x.confidence, 1)}%` },
                        { key: "s", label: "Median seconds", align: "r", render: (x) => num(x.seconds, 1) },
                      ]}
                    />
                  </section>
                )}
              </>
            )}
          </div>
        );
      }}
    </Gate>
  );
}
