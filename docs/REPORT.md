# Experimental report: does AI assistance improve decisions?

Numbers are quoted from [generated/results.md](generated/results.md), rendered from
`results/20261011T024226Z-d5953e1` (clean commit `d5953e1`). The analysis follows the
[pre-registration](PREREGISTRATION.md), committed before any session; departures are amendments
A1–A2 there and decisions in [DECISIONS](DECISIONS.md).

**Read this first.** The question is about people, and **the human study is pending**: no person
has taken part. This report has three kinds of evidence, never pooled:

1. **Model participants (pilot; not people).** Two local open-weights language models made the
   decisions through the same API people use. The results describe how those models used AI
   advice. They say nothing about human decisions.
2. **Simulated participants (dry runs).** Scripted participants whose behaviour was planted. They
   test whether the analysis finds planted effects and stays quiet when there are none.
3. **Simulation-based validation**: the error rate and power of the analysis, from repeated
   simulated studies, which also set the human study's size.

## 1. Set-up

**Task bank.** Three decisions on real records with recorded outcomes: approve a loan (German
credit, 1,000 records), call a bank client (Bank marketing, 45,211), reduce a credit limit
(Default of credit card clients, 30,000). Each participant decides 24 scored cases (8 per domain)
plus 2 practice cases, sampled from 40 test cases per domain with half of each outcome.

**The AI.** Per domain, a logistic regression on exactly the fields people see, Platt-calibrated
on a held-out part and shifted to the bank's 50% base rate. It is as good as a tuned
gradient-boosting reference (test AUROC 0.789 vs 0.796; 0.741 vs 0.760; 0.763 vs 0.768) and was
right on 72.5%, 67.5% and 70.0% of the bank cases, with calibration error 0.18 (loans, 40 cases),
0.07 and 0.04. Arm C's explanation names the three fields that pushed the decision most each way,
in words with a strength, never as numbers (D6).

**Design.** Blocked randomization in blocks of six per stratum; outcomes per participant; arms
compared by a randomization test within stratum (10,000 permutations), Holm over the three
contrasts, 95% bootstrap intervals; a GEE logistic model on decisions as a robustness check.

## 2. Model-participant pilot (not people)

36 participants (Qwen3-4B-Instruct and Phi-4-mini-instruct, 6 per arm each, amendment A1), 864
scored decisions. All 936 model calls returned a valid reply on the first attempt, so no decision
is missing; the hash chain of the 2,916 logged events is intact.

| Arm | Accuracy | AI alone, same cases | Agree with AI | Appropriate reliance | Mean confidence | Brier | Median s |
|---|---:|---:|---:|---:|---:|---:|---:|
| A human only | 54.9% | 67.7% | 54.5% | +8.0 | 88.1 | 0.363 | 6.2 |
| B AI recommendation | 54.2% | 68.1% | 67.4% | −4.8 | 89.3 | 0.366 | 6.5 |
| C AI + uncertainty + explanation | 58.7% | 70.1% | 76.0% | −3.9 | 81.8 | 0.286 | 8.5 |

**Accuracy (primary).** C−A +3.8 pp (−2.1 to +9.4), Holm p = 0.639; B−A −0.7 pp (−8.0 to +6.6),
p = 0.922; C−B +4.5 pp (−3.1 to +11.8), p = 0.639. The GEE agrees (C vs A odds ratio 1.17,
0.96–1.43). The pilot shows no accuracy benefit from AI assistance, and in every arm the models
were worse than the AI alone by 11–14 points.

**Why advice did not help.** Shown the recommendation, the models agreed with it more (54.5% →
67.4% → 76.0%), but as often when the AI was wrong as when it was right: appropriate reliance
(agreement when right minus when wrong) is negative in B and C. Qwen3-4B mostly followed the AI
(86–90% agreement in B and C) and gained a few points; Phi-4-mini largely ignored it and has
strong leanings of its own (it approved 8% of loans and chose "reduce" for 86% of credit limits).
Following a 70%-accurate AI 90% of the time, but not selectively, cannot add much.

**Secondary outcomes.** Decisions took longer in C than in A and B (Holm p = 0.002): more text to
read, and for model participants the time is compute time (D12). Confidence was badly calibrated
everywhere (about 88% stated against 55% right; ECE 0.33 / 0.35 / 0.23) and best in C, where the
Brier score fell by 0.076 against A (Holm p = 0.008): seeing the AI's stated confidence lowered
the models' own. Override (C−B −8.7 pp, Holm p = 0.095), cost per decision and appropriate
reliance show no significant differences.

**Subgroup gaps.** The credit-limit error gap between female and male customers changes by
+57.3 pp from A to C (Holm p = 0.008). This is not about sex, which is never shown: arm A's
participants chose "reduce" for most cases, and the men in arm A's samples had mostly paid (20%
defaulted), so a "reduce" lean produced many errors among men. The raw gap mixes a participant's
lean with each subgroup's outcome mix (D15); the human analysis adds gaps within outcome as an
exploratory addition.

**Hypotheses on the pilot.** H1 (C > A in accuracy): not supported. H2 (B > A): not supported.
H3 (more appropriate reliance in C than B): not supported (+0.9, p = 1.0). H4 (C slower than B):
supported. None of this transfers to people.

## 3. Simulated dry runs (validation)

Each run has 60 simulated participants per arm (4,320 decisions) through the same API.

**No planted effect.** Accuracy 65.7%, 64.0%, 65.5%; every primary and secondary contrast has
Holm p ≥ 0.78. The analysis raises no false alarm here.

**Planted effects** (expected accuracy A 65.6%, B 67.9%, C 69.7%; planted shifts in time,
override and reliance). Observed 68.1%, 65.8%, 69.0%. The intervals for C−A (+0.9, −2.6 to +4.3;
planted +4.1) and C−B (+3.3, +0.1 to +6.5; planted +1.8) contain the planted value; B−A (−2.4,
−6.0 to +1.5; planted +2.3) misses it, and arm A happened to draw 2.5 points above its
expectation. No accuracy contrast is significant, which matches the simulated power at this size
(41% for C−A). The planted secondary effects are all recovered at Holm p = 0.002: C slower than A
and B, B faster than A, less override in C than B, and agreement with the AI rising more when the
AI is wrong than right (appropriate reliance +31.6 → +9.4 / +9.6).

D8 records that the planted skill was lowered after the first dry run (simulated people were more
accurate than the AI, so advice could only hurt); the analysis was not changed.

## 4. Error rate and power

- **False positives**: in 500 simulated studies with no effect and 60 per arm, at least one
  Holm-significant accuracy contrast appeared in 3.0% (nominal ≤ 5%).
- **Power for the planted effects** (C−A, +4.1 pp): 41% at 60 per arm, 80% at 120.
- **Power for a 6-point difference** (the pre-registered sizing rule): 63% at 40, 86% at 60,
  94% at 80. **Human study: 60 per arm** (A2), with a check on the first 30 participants' pooled
  spread before any arm comparison (A3 rule).

## 5. Conclusions

- The platform runs all three arms end to end for every participant kind, and the report is
  generated from real logged sessions with intact hash chains.
- For two small open-weights models, AI advice did not improve decisions: they followed it more
  but not selectively, and stayed far below the AI alone. Showing uncertainty and an explanation
  made them less overconfident and slower, not more accurate.
- The analysis holds its error rate and recovers planted effects of the size it is powered for.
  Planted accuracy effects of 2–4 points need about 120 per arm.

## 6. Limitations

- **No human data.** Every substantive claim about people waits for the human study.
- Model participants are a pilot of the pipeline and of model behaviour; their time is compute
  time, and they skip attention checks and the survey (D10).
- Simulated results depend on the stated behaviour model; their power and spread are assumptions,
  which is why A2 carries a re-sizing rule.
- 40 cases per domain make the AI's bank calibration noisy (loan ECE 0.18 on 40 cases against
  0.07 on the full balanced test split).
- Subgroup gaps compare raw error rates and are confounded by outcome mix within small samples
  (D15).
