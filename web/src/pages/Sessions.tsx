import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AiPanel, CaseCard } from "../components/CaseView";
import { DataTable } from "../components/DataTable";
import { Empty, ErrorOrPending, Loading, PageHead, Segmented } from "../components/ui";
import { type LogBatch, type LogSession, type SessionDetail, useApi } from "../lib/api";
import { ARM_LABEL, MODEL_LABEL, num, pct } from "../lib/format";

const SHORT: Record<string, string> = {
  "model-pilot": "Model pilot",
  "simulated-planted": "Simulated: planted",
  "simulated-no_effect": "Simulated: no effect",
  human: "Human",
};

export function Sessions() {
  const logs = useApi<LogBatch[]>("/api/lab/logs");
  const [batch, setBatch] = useState("model-pilot");
  const list = useApi<LogSession[]>(logs.data?.find((b) => b.batch === batch && b.status === "logged") ? `/api/lab/logs/${batch}/sessions` : null);
  if (logs.loading && !logs.data) return <Loading label="Loading session logs" />;
  if (logs.error) return <ErrorOrPending error={logs.error} retry={logs.retry} what="session logs" command="make pilot" />;
  const b = logs.data?.find((x) => x.batch === batch);
  return (
    <div className="stack">
      <PageHead
        title="Sessions"
        actions={
          <Segmented
            label="Session log"
            options={(logs.data ?? []).map((x) => ({ id: x.batch, label: SHORT[x.batch] ?? x.label, title: x.label }))}
            value={batch}
            onChange={setBatch}
          />
        }
      >
        Every session is an append-only event log; each event carries the SHA-256 of the one before it, so any edit or deletion breaks the chain.
      </PageHead>
      {b && b.status === "pending" ? (
        <Empty title={`${b.label}: pending`}>No sessions have been logged in this population.</Empty>
      ) : (
        b && (
          <section className="panel" aria-labelledby="log-head">
            <div className="panel-head">
              <h2 id="log-head">{b.label}</h2>
              <span className="small">
                {num(b.sessions)} sessions · {num(b.events)} events ·{" "}
                {b.chain_ok ? <span className="ok">✓ chain intact</span> : <span className="bad">✗ {b.chain}</span>}
              </span>
            </div>
            {list.data ? (
              <DataTable
                caption={`Sessions in ${b.label}`}
                rows={list.data}
                rowKey={(r) => r.session}
                columns={[
                  {
                    key: "s",
                    label: "Session",
                    render: (r) => (
                      <Link to={`/lab/sessions/${batch}/${r.session}`} className="mono">
                        {r.session.slice(0, 10)}
                      </Link>
                    ),
                  },
                  { key: "who", label: "Participant", render: (r) => (r.model ? (MODEL_LABEL[r.model] ?? r.model) : r.kind) },
                  { key: "arm", label: "Arm", render: (r) => `${r.arm} · ${ARM_LABEL[r.arm]}` },
                  { key: "d", label: "Decisions", align: "r", render: (r) => `${r.decisions}/${r.items}` },
                  { key: "c", label: "Scored correct", align: "r", render: (r) => num(r.correct) },
                  { key: "done", label: "Completed", render: (r) => (r.completed ? "yes" : "no") },
                ]}
              />
            ) : (
              <Loading label="Loading sessions" rows={4} />
            )}
          </section>
        )
      )}
    </div>
  );
}

interface DecisionData {
  index: number;
  case: string;
  decision: string | null;
  confidence: number | null;
  client_ms: number | null;
  ai_decision: string | null;
  phase: string;
}

export function SessionReplay() {
  const { batch = "", sid = "" } = useParams();
  const s = useApi<SessionDetail>(`/api/lab/logs/${batch}/sessions/${sid}`);
  const [i, setI] = useState(0);
  if (s.loading && !s.data) return <Loading label="Loading the session" />;
  if (s.error) return <ErrorOrPending error={s.error} retry={s.retry} what="this session" command="make pilot" />;
  if (!s.data) return null;
  const { events, items, outcomes } = s.data;
  const created = events[0]?.data as { arm: string; model: string | null; participant_kind: string; stratum: string } | undefined;
  const decisions = new Map<number, DecisionData>();
  for (const e of events) if (e.kind === "decision") decisions.set((e.data as unknown as DecisionData).index, e.data as unknown as DecisionData);
  const item = items[i];
  const d = decisions.get(i);
  const out = item ? outcomes[item.case_id] : null;
  const right = out?.right;
  const label = (dec: string | null | undefined) => item?.options.find((o) => o.decision === dec)?.label ?? dec ?? "no answer";
  return (
    <div className="stack">
      <PageHead title={`Session ${sid.slice(0, 10)}`}>
        {created?.model ? (MODEL_LABEL[created.model] ?? created.model) : created?.participant_kind} · arm {created?.arm} ({ARM_LABEL[created?.arm ?? ""]}) ·{" "}
        {events.length} events · <Link to="/lab/sessions">all sessions</Link>
      </PageHead>
      <ol className="strip" aria-label="Decisions in this session">
        {items.map((it, k) => {
          const dk = decisions.get(k);
          const o = outcomes[it.case_id];
          const ok = it.phase === "task" && o && dk ? dk.decision === o.right : null;
          return (
            <li key={k}>
              <button
                type="button"
                className={`cell-tick ${ok === true ? "ok" : ok === false ? "bad" : ""} ${k === i ? "current" : ""}`}
                aria-current={k === i ? "step" : undefined}
                aria-label={`Decision ${k + 1}, ${it.phase}${ok === null ? "" : ok ? ", right" : ", wrong"}`}
                onClick={() => setI(k)}
              >
                {k + 1}
              </button>
            </li>
          );
        })}
      </ol>
      {item && (
        <>
          <div className={item.ai ? "task-grid" : "task-grid single"}>
            <CaseCard item={item} />
            {item.ai && <AiPanel ai={item.ai} />}
          </div>
          <section className="panel" aria-labelledby="dec-head">
            <div className="panel-head">
              <h2 id="dec-head">What happened</h2>
              <span className="muted small">{item.phase}</span>
            </div>
            <dl className="kv panel-body">
              <dt>Decision</dt>
              <dd>{label(d?.decision)}</dd>
              <dt>Confidence</dt>
              <dd>{d?.confidence != null ? `${d.confidence}%` : "–"}</dd>
              <dt>Time on screen</dt>
              <dd>{d?.client_ms != null ? `${num(d.client_ms / 1000, 1)} s` : "–"}</dd>
              <dt>Right answer</dt>
              <dd>{right ? label(right) : item.phase === "attention" ? "attention check" : "–"}</dd>
              <dt>AI recommended</dt>
              <dd>{out?.ai ? `${label(out.ai)}${item.ai ? "" : " (not shown in this arm)"}` : "–"}</dd>
              <dt>Result</dt>
              <dd>{right && d ? (d.decision === right ? <span className="ok">✓ right</span> : <span className="bad">✗ wrong</span>) : "–"}</dd>
            </dl>
          </section>
        </>
      )}
      <details className="panel panel-body">
        <summary>Event log ({events.length} events, hash-chained)</summary>
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Event log">
          <table>
            <caption className="sr-only">Event log</caption>
            <thead>
              <tr>
                <th scope="col" className="num">
                  Seq
                </th>
                <th scope="col">Time</th>
                <th scope="col">Event</th>
                <th scope="col">Hash</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.seq}>
                  <td className="num">{e.seq}</td>
                  <td className="mono small">{e.ts.slice(11, 19)}</td>
                  <td>{e.kind}</td>
                  <td className="mono small">{e.hash.slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="small muted">Accuracy in this session: {pct(items.filter((it, k) => it.phase === "task" && decisions.get(k)?.decision === outcomes[it.case_id]?.right).length / Math.max(1, items.filter((it) => it.phase === "task").length), 1)}.</p>
    </div>
  );
}
