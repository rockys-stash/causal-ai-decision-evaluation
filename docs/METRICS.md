# Metrics

All metrics are computed per participant, then averaged within arm; tests compare participants,
not decisions. Definitions follow the [pre-registration](PREREGISTRATION.md).

## Primary

| Metric | Definition |
|---|---|
| Accuracy | Share of a participant's 24 scored decisions that match the recorded outcome. Practice cases and attention checks are not scored; missing answers (model participants only) are left out, not counted as errors |

Contrasts C−A, B−A, C−B: difference in mean accuracy (percentage points), 95% bootstrap interval
(participants resampled within arm), randomization p-value (arm labels permuted within stratum),
Holm-adjusted across the three. Effect sizes: Cohen's h, and error reduction
`1 − error(arm) / error(A)`.

Robustness: GEE logistic regression of decision correctness on arm with domain fixed effects
(and model, for the pilot), exchangeable correlation within participant; odds ratios for B and C
against A.

## Secondary (one Holm family)

| Metric | Definition |
|---|---|
| Cost per decision | Mean cost of the participant's decisions under each domain's cost matrix (loan FP 5, FN 1; marketing FP 1, FN 3; credit limit FP 1, FN 4; correct 0) |
| Decision time | Mean log seconds per decision. People and model participants: server time from the item shown to the decision received. Simulated participants: the time the behaviour model reports (D6) |
| Override | Share of decisions that differ from the AI's recommendation; C−B only |
| Appropriate reliance | Agreement with the AI when it was right minus agreement when it was wrong. In arm A the recommendation is computed but not shown: A's value is the baseline from shared judgement |
| Brier score | Mean of (confidence − correct)², confidence on 0.5–1 |
| Subgroup error gap | Error rate in one subgroup minus the other, pooled within arm: loan applicants under 25 vs 25 and over; credit-limit customers female vs male. The contrast is the change in the gap between arms, tested by permuting arms |

## Descriptive

| Metric | Definition |
|---|---|
| Agreement | Share of decisions equal to the AI's recommendation (all arms) |
| ECE | Expected calibration error of stated confidence, 5 equal-width bins on 50–100% |
| AI alone | Accuracy and cost of the AI's recommendation on the same participant-case pairs |
| By domain, by model | Accuracy and agreement per arm within each domain, and per model for the pilot |

## The AI

| Metric | Where |
|---|---|
| Test AUROC, balanced accuracy, TPR, TNR | test split (`ai_report.json`) |
| ECE and Brier on the balanced test split | importance-weighted to a 50% base rate, matching the bank |
| Bank accuracy | the 40 cases per domain |
| Gradient boosting test AUROC | reference only |

## Validation by simulation

Computed with a vectorised copy of the simulated participants' behaviour model (the same formulas,
not through the API), drawing cases from the bank as the design does, and tested with the primary
analysis's permutation test (1,000 permutations per test; Holm over the three contrasts).

| Metric | Definition |
|---|---|
| Expected accuracy | Mean accuracy of 20,000 simulated participants per arm: the planted truth the dry run should recover |
| Type I error | Share of simulated studies of the no-effect design (60 per arm, 500 repetitions) in which any of the three primary contrasts is significant after Holm |
| Power curve | Share of simulated planted-design studies (300 per size) in which each contrast is significant, at 10–120 per arm |
| Power for 6 points | Arm-A participants against participants whose errors are each corrected with the probability that adds 6 points on average; significant when 3 × p < 0.05 (Holm's strictest step, conservative). The smallest size with at least 80% power sets the human sample size |
