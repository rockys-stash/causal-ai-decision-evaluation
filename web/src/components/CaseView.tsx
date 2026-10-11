import type { AiShown, Item } from "../lib/api";
import { pct } from "../lib/format";

/** The case as a participant sees it: a definition list of the record's fields. */
export function CaseCard({ item }: { item: Item }) {
  return (
    <section className="panel case" aria-labelledby={`case-${item.index}`}>
      <div className="panel-head">
        <h2 id={`case-${item.index}`}>{item.phase === "attention" ? "Attention check" : `${item.domain_label}: the case`}</h2>
        {item.phase === "practice" && <span className="badge">Practice, not scored</span>}
      </div>
      <dl className="case-fields">
        {item.card.map((f) => (
          <div key={f.field}>
            <dt>{f.label}</dt>
            <dd>{f.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function strengthWord(s: string) {
  return s === "strong" ? "●●●" : s === "moderate" ? "●●○" : "●○○";
}

/** What the AI shows in arms B (recommendation) and C (recommendation, calibrated confidence and factors). */
export function AiPanel({ ai }: { ai: AiShown }) {
  const ex = ai.explanation;
  return (
    <section className="panel ai-panel" aria-labelledby="ai-head">
      <div className="panel-head">
        <h2 id="ai-head">AI recommendation</h2>
      </div>
      <div className="panel-body">
        <p className="ai-rec">
          <span className="muted small">The AI recommends</span>
          <strong>{ai.label}</strong>
        </p>
        {ai.confidence !== undefined && (
          <div className="ai-conf">
            <p className="small">
              Confidence: <strong>{pct(ai.confidence)}</strong>
              <span className="muted"> (calibrated: of the cases where the AI says {pct(ai.confidence)}, about that share are right)</span>
            </p>
            <div className="meter" role="img" aria-label={`AI confidence ${pct(ai.confidence)} on a scale from 50% to 100%`}>
              <span style={{ width: `${((ai.confidence - 0.5) / 0.5) * 100}%` }} />
            </div>
            <p className="meter-scale small muted" aria-hidden="true">
              <span>50% (a guess)</span>
              <span>100% (certain)</span>
            </p>
          </div>
        )}
        {ex && (
          <div className="factors">
            {(
              [
                ["towards_positive", ex.positive_label],
                ["towards_negative", ex.negative_label],
              ] as const
            ).map(([key, label]) => (
              <div key={key}>
                <h3 className="small">Pointing to {label}</h3>
                {ex[key].length ? (
                  <ul>
                    {ex[key].map((f) => (
                      <li key={f.field}>
                        <span>
                          {f.label}: <strong>{f.value}</strong>
                        </span>
                        <span className="strength" title={`${f.strength} influence`}>
                          <span aria-hidden="true">{strengthWord(f.strength)}</span>
                          <span className="sr-only">{f.strength} influence</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="small muted">Nothing in this case.</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
