# Dataset

## Case data

Three public datasets, each with a recorded outcome, so every decision in the study has a right
answer. All are from the UCI Machine Learning Repository, licensed CC BY 4.0, fetched as Parquet
from OpenML by URL and checked against the SHA-256 pinned in `configs/study.yaml` (`make data`;
the files are not committed, `data/raw/` is ignored).

| Domain | Dataset | OpenML | Records | Positive outcome (share) | Decision |
|---|---|---|---|---|---|
| Loan approval | Statlog (German Credit Data), Hofmann 1994 | 31 | 1,000 | repaid as agreed (70.0%) | approve / decline |
| Marketing call | Bank Marketing, Moro, Rita & Cortez 2014 | 1461 | 45,211 | subscribed to a term deposit (11.7%) | call / skip |
| Credit-limit review | Default of Credit Card Clients, Yeh & Lien 2009 | 42477 | 30,000 | defaulted the next month (22.1%) | reduce / keep |

**What a case shows.** Each case is one record, shown as a short list of fields in plain words
(`src/declab/data.py`):

- Loan: checking account, duration, amount, purpose, credit history, savings, years in the current
  job, age, housing, job, most valuable property, existing credits (12 fields). The applicant's sex
  and marital status, and foreign-worker status, are not shown or used.
- Marketing: age, job, marital status, education, credit in default, average yearly balance,
  housing loan, personal loan, contacts so far in this campaign, contacts in earlier campaigns,
  earlier campaign result (11 fields). The call's duration, day, month and contact type are
  dropped: duration is only known after the call (it leaks the outcome) and the others describe
  the call, not the client.
- Credit limit: limit, age, education, marital status, repayment status in September, August and
  July, September bill, payments in September and August (10 fields). **Sex is not shown and not
  used by the AI;** it is kept only to measure error gaps between women and men.

The AI uses exactly the fields a participant sees (D4).

## Splits and the case bank

Each dataset is split 60/20/20 into training, calibration and test parts, stratified by outcome
(seed 20261011). The AI is fitted on the training part and calibrated on the calibration part; the
case bank comes only from the test part.

`data/bank/bank.json` (committed) holds 40 cases per domain, 20 with each outcome, plus 2 practice
cases per domain. Within each outcome the cases are drawn so that the share the AI gets right
equals its true-positive or true-negative rate on the test part: the bank is neither easier nor
harder for the AI than the test data. `data/bank/ai_report.json` records the AI's test and bank
performance. Rebuilding the bank from the downloaded data gives a byte-identical file; CI checks
this.

| Domain | AI accuracy on the bank | AI test AUROC | Gradient boosting test AUROC |
|---|---|---|---|
| Loan approval | 72.5% | 0.789 | 0.796 |
| Marketing call | 67.5% | 0.741 | 0.760 |
| Credit-limit review | 70.0% | 0.763 | 0.768 |

## Session logs

`data/sessions/*.jsonl` (committed) are the exported event logs, one JSON event per line with its
hash chain intact:

| File | Population | Sessions |
|---|---|---|
| `simulated-planted.jsonl` | simulated participants, planted effects (dry run) | 180 |
| `simulated-no_effect.jsonl` | simulated participants, no effect (dry run) | 180 |
| `model-pilot.jsonl` | language-model participants (pilot) | 36 |
| `model-pilot-calls.jsonl` | every model call: prompt seed, raw reply, validity, time | – |
| `human.jsonl` | human participants | **pending: none** |

No log contains personal data. Simulated and model sessions are labelled in their first event
(`participant_kind`), and the analysis never pools kinds.

## Licences and citation

- Hofmann, H. (1994). Statlog (German Credit Data). UCI Machine Learning Repository.
  https://doi.org/10.24432/C5NC77
- Moro, S., Rita, P., & Cortez, P. (2014). Bank Marketing. UCI Machine Learning Repository.
  https://doi.org/10.24432/C5K306
- Yeh, I.-C. (2009). Default of Credit Card Clients. UCI Machine Learning Repository.
  https://doi.org/10.24432/C55S3H

All three are CC BY 4.0. The models used as pilot participants are Qwen3-4B-Instruct-2507 (Apache
2.0) and Phi-4-mini-instruct (MIT), as GGUF files pinned by SHA-256 in `configs/models.yaml`.
