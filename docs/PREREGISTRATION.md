# Pre-registered analysis plan

Fixed before any session of any participant kind was run. The commit that adds this file is the
registration; any later change is an amendment at the end of this file, dated, with its reason,
and the analysis code reports which version it follows.

## Design

- Between-subjects, three arms: **A** human only; **B** AI recommendation; **C** AI
  recommendation with calibrated confidence and explanation.
- Assignment: blocked randomization (block size 6, two of each arm) from a seeded allocation list,
  separately for each participant kind (human, simulated, model) and, for model participants, for
  each model. The list is generated before the first session and hashed; the hash is logged.
- Each participant decides **24 cases**: 8 per domain, 4 with each outcome, drawn at random from
  the bank of 120 (40 per domain) and shown in random order. Two practice cases (not analysed)
  and, for humans, two attention checks.
- Each decision: a binary choice and a confidence from 50% to 100%.

## Outcomes

**Primary**: decision accuracy, the share of a participant's 24 decisions that match the recorded
outcome.

**Secondary** (one family, Holm-corrected together):

1. Decision cost per decision, from the cost matrices below.
2. Time to decision (server-measured seconds from case shown to decision received; log scale).
3. Override rate: share of decisions that differ from the AI's recommendation (B and C).
4. Appropriate reliance: P(agree with AI | AI right) − P(agree with AI | AI wrong), per
   participant. In arm A the AI's recommendation is computed but not shown, giving the baseline
   agreement a participant would have by chance of judgement alone.
5. Confidence calibration: expected calibration error (5 equal-width bins) and Brier score of the
   stated confidence.
6. Subgroup error gap: difference in error rate between applicant subgroups (loan: age < 25 vs
   ≥ 25; credit limit: female vs male), per arm.

**Cost matrices** (relative costs, chosen before the data were seen): loan, approving a bad risk 5,
declining a good one 1 (the Statlog dataset's documented matrix); marketing call, skipping a
subscriber 3, calling a non-subscriber 1; credit limit, keeping the limit of a defaulter 4,
reducing a non-defaulter's 1. Correct decisions cost 0.

## Analysis

- **Unit**: the participant (decisions are nested in participants).
- **Primary test**: for each contrast C−A, B−A and C−B, a randomization test of the difference in
  mean participant accuracy: arm labels permuted among the participants of the two arms (within
  model, for model participants), 10,000 permutations, two-sided. Holm correction over the three
  contrasts; α = 0.05.
- **Effect sizes**: difference in mean accuracy in percentage points with a 95% bootstrap interval
  (participants resampled within arm, 5,000 resamples), Cohen's h, and the relative error
  reduction 1 − error(arm) / error(A).
- **Robustness**: logistic regression of decision correctness on arm with domain fixed effects,
  fitted by GEE with exchangeable correlation within participant (statsmodels). Reported, not used
  for the decision on hypotheses.
- **Secondary tests**: randomization tests as above on participant-level values; Holm over the
  secondary family; H4 is outcome 2 for C vs B; H3 is outcome 4 for C vs B.
- **AI reference**: the AI's accuracy and cost on the same participant-case pairs, and its
  calibration on the full bank.

## Exclusions and missing data

- Human participants who fail both attention checks are excluded; incomplete sessions are excluded
  from the primary analysis and counted.
- Model participants: an answer that cannot be parsed is retried up to 3 times with a new seed; if
  still invalid it is recorded as missing. A model participant with more than 20% missing
  decisions is excluded. Missing decisions are not counted as errors in accuracy, and the count is
  reported.
- Simulated participants: no exclusions.

## Sample size

- **Simulated dry run**: 60 participants per arm with planted effects, and 60 per arm with no
  effects (to check the false-positive rate); 500 repetitions of the null design to estimate the
  test's type I error; a power curve for 10–120 participants per arm.
- **Model-participant pilot**: 5 participants per arm per model (2 models, 30 participants, 720
  decisions); a pilot, not powered for small effects.
- **Human study**: the number per arm is set from the simulated power curve to detect a
  6-percentage-point accuracy difference with 80% power, and recorded as an amendment before the
  first human session.

## What would change the conclusions

Results for one participant kind are never generalised to another. A significant model-pilot
effect says how those models used the AI; it is not evidence about people.

## Amendments

**A1 (2026-10-11, before any model-participant session).** Model-participant pilot size: 6 per
arm per model (18 per model, 36 in all, 864 analysed decisions) instead of 5. With blocks of 6,
5 per arm cannot be reached with balanced arms; three complete blocks per model can. The
model-participant answer format is fixed as JSON with the decision and an integer confidence.

**A2 (2026-10-11, before any human session).** Human sample size: **60 participants per arm (180
in all, 4,320 scored decisions)**, after exclusions. Set by the pre-registered rule from the
simulated power analysis in `results/20261011T024226Z-d5953e1` (power for a 6-point accuracy
difference: 63% at 40 per arm, 86% at 60). Recruitment continues until 60 complete, non-excluded
sessions per arm; with blocked allocation, the last block is completed. The same analysis applies
unchanged. Caveat recorded with the amendment: the power analysis rests on simulated participants
whose skill and spread are assumptions; if the first 30 human participants' accuracy SD, pooled
across arms without looking at arm differences, exceeds the simulated 8–11 points, the size will
be re-derived from it and recorded as A3; no arm comparison is computed before the final size.
