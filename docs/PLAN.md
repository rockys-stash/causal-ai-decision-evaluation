# Plan

Written before any data were fetched or any session run; changes made afterwards are in
[DECISIONS](DECISIONS.md). The statistical analysis is fixed separately in
[PREREGISTRATION](PREREGISTRATION.md).

## Question

Does AI assistance improve human decisions, and does showing the AI's calibrated confidence and an
explanation change how people rely on it? A randomized three-arm experiment on business decisions
whose correct answer is known.

| Arm | What the decision-maker sees |
|---|---|
| A. Human only | the case |
| B. AI recommendation | the case and the AI's recommendation |
| C. AI with uncertainty and explanation | the case, the recommendation, the AI's calibrated confidence and the factors behind it |

In every arm the human makes the final decision. The AI deciding alone is reported as a reference,
not as an arm.

## Task bank

Real records with recorded outcomes, from three public datasets (one decision per domain):

| Domain | Data | Decision | Correct when |
|---|---|---|---|
| Loan approval | German credit (Statlog; OpenML 31) | approve or decline the loan | approve ⇔ the applicant was a good credit risk |
| Marketing call | Bank marketing (Moro et al.; OpenML 1461) | call or skip the client | call ⇔ the client subscribed |
| Credit-limit review | Default of credit card clients (Yeh & Lien; OpenML 42477) | keep or reduce the limit | reduce ⇔ the client defaulted next month |

Each dataset is split into training, calibration and test parts; the bank is drawn only from the
test part, with half positive outcomes per domain, and stratified so the AI's accuracy on the bank
equals its accuracy on the balanced test part (no hand-picked hard or easy cases). Columns that
leak the outcome (the bank call's duration) are dropped.

## Platform (Human-AI Decision Experiment Platform)

- **Randomized assignment**: a concealed, seeded, blocked allocation list per participant kind;
  task order and the case sample per participant randomized from a recorded seed.
- **Full session logging**: every event (consent, assignment, task shown, decision, confidence,
  timings, attention checks, survey) appended to a hash-chained log; nothing is updated in place.
- **AI recommender**: per domain, an interpretable logistic model with calibrated probabilities
  (calibration split; prior adjusted to the bank's 50% base rate) and explanations as the largest
  per-case contributions in plain words; a gradient-boosting model reported for comparison.
- **Participant interface**: consent, instructions, practice, the decisions, attention checks, a
  short survey, debrief. **Researcher console**: design, balance of assignment, sessions and their
  logs, results per arm.
- **Statistical pipeline** following the pre-registered plan, generated report.

## Participants and honesty about them

- **Human participants: recruitment is not possible in this environment.** The platform is ready
  for a human study, the study is marked **pending**, and no result is presented as a human result.
- **Simulated dry run**: scripted participants with stated, planted behaviour go through the same
  API, to validate the pipeline (does the analysis recover a planted effect, and hold its error
  rate when there is none?) and to size the human study by simulation. Labelled simulated.
- **Model-participant pilot**: two local open-weights language models (Qwen3-4B-Instruct,
  Phi-4-mini-instruct) take the role of decision-maker through the same API in all three arms.
  These are real logged sessions of model participants, labelled as such; they answer the
  research question for those models, not for people.

Every table, chart and sentence names its participant kind; kinds are never pooled.

## Metrics

Decision accuracy; decision quality (cost-weighted errors, pre-registered cost matrices); error
reduction relative to arm A; time to decision; AI override rate; reliance (agreement with the AI
when it is right and when it is wrong, against arm A's baseline agreement); calibration of the
decision-maker's confidence and of the AI; error differences between applicant subgroups by arm.

## Hypotheses (for human participants; tested on the pilot with the same plan)

- **H1**: accuracy is higher in C than in A.
- **H2**: accuracy is higher in B than in A.
- **H3**: reliance is more appropriate in C than in B (agreement with the AI rises more when the
  AI is right than when it is wrong).
- **H4**: decisions take longer in C than in B.

## Acceptance

All three arms run end-to-end through the platform; the report is generated from the logged
sessions; the study status is stated: human study pending, simulated and model-participant
sessions labelled.
