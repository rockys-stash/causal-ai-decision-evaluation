import { Link } from "react-router-dom";
import { HBars } from "../components/charts";
import { DataTable } from "../components/DataTable";
import { Gate, useTopic } from "../components/Topic";
import { PageHead, ProvenanceLine } from "../components/ui";
import type { Overview as OverviewData, Primary, Provenance } from "../lib/api";
import { ARM_LABEL, num, pct, pp, pval } from "../lib/format";
import { POP_NOTE, POPS, type PopId } from "../lib/pops";

export function Overview() {
  const ov = useTopic<OverviewData>("overview");
  const pr = useTopic<Primary>("primary");
  const prov = useTopic<Provenance>("provenance");
  return (
    <Gate state={ov} title="Overview" what="the overview">
      {(o) => (
        <div className="stack">
          <PageHead title="Does AI advice improve business decisions?">
            A randomized experiment with three arms: people decide alone (A), with an AI recommendation (B), or with the recommendation plus its
            calibrated confidence and the factors behind it (C). Each participant makes 24 decisions on real past cases with known outcomes.
          </PageHead>
          <div className="callout" role="note">
            <strong>Human study: pending.</strong> No person has taken part yet. Everything below comes from simulated participants (dry runs that
            test the analysis) and a pilot with language-model participants. Neither is evidence about how people decide.
          </div>
          <section className="panel" aria-labelledby="pop-head">
            <div className="panel-head">
              <h2 id="pop-head">Session populations</h2>
            </div>
            <DataTable
              caption="Populations, sessions and log status"
              rows={POPS.map((p) => ({ id: p.id as PopId, ...o.populations[p.id] }))}
              rowKey={(r) => r.id}
              columns={[
                { key: "label", label: "Population", render: (r) => r.label, wrap: true },
                { key: "status", label: "Status", render: (r) => (r.status === "pending" ? <span className="pill-status pending">pending</span> : r.status) },
                { key: "sessions", label: "Sessions", align: "r", render: (r) => num(r.sessions) },
                { key: "decisions", label: "Scored decisions", align: "r", render: (r) => num(r.decisions) },
                { key: "chain", label: "Log chain", render: (r) => (r.chain_ok === null ? "–" : r.chain_ok ? <span className="ok">✓ intact</span> : <span className="bad">✗ broken</span>) },
              ]}
            />
          </section>
          {pr.data && (
            <div className="grid-2">
              {(["model", "simulated-planted"] as const).map((id) => {
                const p = pr.data?.[id];
                if (!p?.arms) return null;
                const ca = p.primary?.find((c) => c.contrast === "C−A");
                return (
                  <section key={id} className="panel" aria-labelledby={`h-${id}`}>
                    <div className="panel-head">
                      <h2 id={`h-${id}`}>Accuracy by arm: {POPS.find((x) => x.id === id)?.label.toLowerCase()}</h2>
                    </div>
                    <div className="panel-body stack-sm">
                      <HBars
                        label={`Accuracy by arm, ${id}`}
                        max={1}
                        format={(v) => pct(v, 1)}
                        rows={p.arms.map((a) => ({
                          key: a.arm,
                          label: `${a.arm} · ${ARM_LABEL[a.arm]}`,
                          v: a.accuracy,
                          note: `${a.participants} participants`,
                          cls: `arm-${a.arm.toLowerCase()}`,
                        }))}
                      />
                      {ca && (
                        <p className="small">
                          C − A: <strong>{pp(ca.diff)} percentage points</strong> (95% interval {pp(ca.ci?.[0])} to {pp(ca.ci?.[1])}), Holm-adjusted p ={" "}
                          {pval(ca.p_holm)}. AI alone on these cases: {pct(p.arms[0]?.ai_accuracy, 1)}.
                        </p>
                      )}
                      <p className="small muted">{POP_NOTE[id]}</p>
                    </div>
                  </section>
                );
              })}
            </div>
          )}
          <p>
            <Link to="/lab/results">All results with intervals and corrections</Link> · <Link to="/lab/design">Design and power</Link> ·{" "}
            <Link to="/study">Open the participant study</Link>
          </p>
          {prov.data && <ProvenanceLine p={prov.data} />}
        </div>
      )}
    </Gate>
  );
}
