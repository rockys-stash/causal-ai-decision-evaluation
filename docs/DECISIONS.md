# Decisions

Choices made during the build that the [plan](PLAN.md) and the
[pre-registration](PREREGISTRATION.md) did not fix, with the reason for each. Changes to the
pre-registered analysis itself are amendments in the pre-registration (A1, A2).

**D1. Dataset hashes pinned from the first download.** OpenML publishes no checksum for its Parquet
files. The SHA-256 of each file at the first download (2026-10-11) is pinned in
`configs/study.yaml`; every later download is checked against it and refused on a mismatch.

**D2. Arm B is a person with the AI's recommendation, not the AI deciding alone.** The question is
whether AI *assistance* improves *human* decisions, so a person makes the final decision in every
arm. The AI's own accuracy on the same cases is reported as a reference ("AI alone") in every
table.

**D3. One decision per case, not decide-then-revise.** A two-step protocol (decide, see the AI,
revise) would measure switching directly, but it changes arm A's task and makes arms B and C see
the AI after committing to an answer. A single decision keeps the three arms identical except for
what is shown. Reliance is measured against arm A's agreement with the (unseen) AI, which is the
agreement shared judgement produces on its own.

**D4. The AI uses exactly the fields people see.** Otherwise a gain from the AI could come from
information people never had. Fields that describe the bank call rather than the client, and the
call duration (known only after the call, so it leaks the outcome), are dropped. Sex is neither
shown nor used; it is kept only for the credit-limit subgroup audit. In the loan data, the field
that combines sex and marital status and the foreign-worker flag are not used.

**D5. Bank at a 50% base rate, AI calibrated to it, and participants told so.** Real base rates
differ by domain (70%, 12%, 22%); at those rates "always approve" or "always skip" would score
well and accuracy would mean little. Each domain's bank has 20 cases of each outcome, the AI's
probabilities are shifted to a 50% prior after Platt scaling so its stated confidence is calibrated
on the bank, and the instructions say half the cases went each way. Within each outcome the cases
are drawn so the AI is right as often as on the test split (no easier or harder cases for the AI).

**D6. Explanations as signed contributions in words.** Arm C shows the three fields that pushed the
AI's decision most each way, as "field: value" with a strength (weak, moderate, strong for
|contribution| below 0.4, below 1.0, from 1.0 on the calibrated log-odds scale, relative to the
average applicant). No numbers or coefficients are shown: the study tests a plain-language
explanation, the form a deployed tool would use.

**D7. Simulated participants' decision time is their reported time.** Simulated sessions run in
milliseconds; their time comes from the behaviour model, sent as the client's time. People and
model participants use the server's time from the item shown to the decision received.

**D8. Planted dry-run parameters changed after the first dry run.** With the first parameters
(skill 0.55, commit `626519a`) the simulated people were more accurate than the AI (about 76% against 70%), so AI
advice made the planted arms *worse*: a valid test of the pipeline, but not of the planted effect
the study is designed for. Skill was lowered to 0.3 (expected accuracy A 65.6%, B 67.9%, C 69.7%)
and both dry runs were rerun (commit `e59cbae`). The analysis plan was not changed, and the
parameters only drive simulated participants, not model participants or people; simulated sessions are validation
data, never results, and the report says the dry run recovers effects that were planted.

**D9. Six-point sizing: errors corrected at random, Holm approximated by 3p.** The pre-registered
rule asks for 80% power for a 6-point accuracy difference. The alternative is arm-A simulated
participants with each error corrected with the probability that adds 6 points on average, and
significance needs 3 × p < 0.05, the strictest Holm step; this is conservative.

**D10. Model participants get no attention checks or survey.** Attention checks guard against
inattentive people; the pre-registration places them for humans only. A model's trust rating would
not mean what a person's does, so model sessions post an empty survey to complete.

**D11. Pilot participants are local open-weights models.** At the user's direction the portfolio
uses no paid model API (2026-10-09). Qwen3-4B-Instruct-2507 and Phi-4-mini-instruct, the models
already used in this portfolio, run on CPU with llama.cpp. Replies are constrained to JSON with the
item's two options; temperature 0.7 so participants of one model differ; each participant's seed
is its slot. The two models are separate strata (A1) and are never pooled with any other kind.

**D12. Model participants' time is compute time.** Server seconds for a model participant measure
inference on a shared CPU, which other jobs slowed by varying amounts. The time outcome is reported
for the pilot but says nothing about deliberation.

**D13. Human study pending.** Recruiting people needs ethics approval and a participant pool, which
this environment does not have. The platform runs the study end to end in a browser (tested), the
human population is shown as pending everywhere, and the sample size is fixed in advance from the
simulated power curve (A2). No result is described as a human result.

**D14. Code formatting during the pilot.** `ruff format` and type annotations were applied while the
pilot was running (commit `646bb06`). They change layout and type hints only; the running process
had loaded the earlier code, and the tests pass on both.

**D15. Subgroup gaps reported as pre-registered, with how to read them.** The pre-registered gap is
a raw difference in error rates. Each participant sees a random sample of cases, so the outcome mix
of a subgroup differs between arms, and a participant who leans towards one answer makes more
errors in whichever subgroup has more cases of the other outcome. In the model pilot, arm A's model
participants chose "reduce" for 82–92% of credit-limit cases, and the men in arm A's samples had
mostly paid (20% defaulted): that, not the sex of the customer (which is never shown), makes the
large arm-A gap. The report says so next to the table. For the human study, gaps in
false-positive and false-negative rates within outcome will be reported as an exploratory
addition, recorded with A2's analysis unchanged.

**D16. The rebuilt bank is compared exactly for cases and with a tolerance for fitted numbers.**
CI rebuilds the bank from the downloaded datasets. On GitHub's runners the cases, outcomes and
recommendations (`bank.json`) were identical, but fitted coefficients in `ai_report.json` differed
in the 13th–14th significant digit, from the machine's floating-point libraries. CI now requires
`bank.json` to match byte for byte and compares `ai_report.json` with a relative tolerance of
1e-9 (`scripts/compare_bank.py`).
