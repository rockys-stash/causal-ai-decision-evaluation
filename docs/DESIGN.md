# Design

## Overview

```
UCI datasets ──► declab data (SHA-256) ──► declab bank: fit + calibrate the AI per domain,
                                            draw 40 test cases per domain ──► data/bank/bank.json
                                                                                  │
 people (browser /study)  ─┐                                                      ▼
 simulated participants   ─┼──► HTTP API (FastAPI) ──► randomization ──► hash-chained event log (SQLite)
 model participants (LLM) ─┘        │                                             │ export
                                    │                                             ▼
 researcher console (/lab) ◄────────┘                        data/sessions/<population>.jsonl
                                                                                  │
                                    declab analyse (pre-registered) ◄─────────────┘
                                          │
                     results/<UTC>-<sha7>/*.json ──► declab report ──► docs/generated/results.md
```

Every participant kind goes through the **same HTTP API**: people in the browser, simulated
participants and language models through an HTTP client. Nothing about a session is computed
outside the log: what was shown, when, what was decided and how long it took are all events.

## Components (`src/declab/`)

| Module | Role |
|---|---|
| `data.py` | Download and hash-check the datasets; map raw columns to readable fields; render a case |
| `ai.py` | The recommender: logistic regression (C by cross-validated log loss), Platt scaling on the calibration split, prior shift to a 50% base rate, per-field contributions and the explanation |
| `bank.py` | Splits, AI fit and evaluation, stratified draw of the case bank, `ai_report.json` |
| `design.py` | Blocked allocation per stratum from a seeded generator, its hash, each participant's case plan |
| `store.py` | Append-only SQLite log; each event carries the SHA-256 of the previous one; `verify`, export |
| `api.py` | Participant routes, researcher routes, committed-log browser, results; guard middleware |
| `participants.py` | Behaviour model of simulated participants; the session runner shared by simulated and model participants |
| `llm.py` | Model participants: the item rendered as text, schema-constrained JSON reply, retries, call log |
| `runs.py` | Simulated dry runs and the resumable model pilot, each in its own store, exported to `data/sessions/` |
| `analysis.py` | Tables from events, exclusions, participant summaries, permutation tests, bootstrap, Holm, GEE, calibration, simulation-based error rate and power |
| `report.py` | `docs/generated/results.md` from the latest result |

## Randomization

The allocation for a stratum (human; simulated; `model:<name>`) is a list of blocks of six, two of
each arm, shuffled by a generator seeded with SHA-256 of the study seed and the stratum. The list
exists before the first session; its hash goes into every session's first event, so the allocation
can be regenerated and checked afterwards. A participant's slot is the number of sessions already
created in their stratum (under a lock), and the slot also seeds their case sample, case order and
attention-check positions. Participants never see their arm or the allocation.

## A session

1. `POST /api/sessions` with consent → `session_created` (kind, stratum, slot, arm, allocation
   hash, the full item plan). People need no account; simulated and model sessions need the
   researcher token, or a loopback client when no token is set.
2. `GET /api/sessions/{id}/next` → the next undecided item, logging `item_shown` the first time.
   The item carries only what the participant's arm sees.
3. `POST /api/sessions/{id}/decisions` → `decision` (choice, confidence, client time) and
   `timing` (server seconds from shown to received). Items must be decided in order and once.
4. `POST /api/sessions/{id}/survey` → `survey`, `session_completed`, and a completion code.

A session can be resumed from any point (the state is rebuilt from its events), which is how an
interrupted model pilot continues.

## The log

Each event is `{seq, ts, session, kind, data, prev, hash}` where `hash = SHA-256(prev +
canonical JSON of seq, ts, session, kind, data)`. Editing, deleting or reordering any event breaks
the chain from that point; `declab verify` checks every committed log, and the analysis reports
the chain status of each population and refuses nothing silently.

## Security

- Researcher routes (`/api/lab/*`) require `Authorization: Bearer <DECLAB_TOKEN>` when the token is
  set; `declab serve` refuses to bind a non-loopback address without it.
- Only `/api/sessions` accepts POST; bodies over 16 KB are refused; every API client is rate
  limited; session ids are 128-bit random and validated before use; result topics and log batches
  come from fixed lists.
- Security headers (CSP without inline scripts, no framing, no referrer, `no-store` on the API).
- No personal data is asked for: no name, no email; the free-text comment is limited to 1,000
  characters and the consent page says what is recorded.

## Interface (`web/`)

React 18, TypeScript, Vite; Geist fonts; light and dark themes.

- **Participant study** (`/study`): consent, 28 screens (2 practice, 24 cases, 2 attention checks),
  a decision as two large options, a confidence slider that must be moved, progress, and a short
  survey (trust and usefulness only for arms that saw the AI), then a completion code. No
  navigation to the console and nothing that reveals other arms.
- **Researcher console** (`/lab`): overview of the populations, results per population with
  intervals and corrections, reliance and calibration, a browser of committed logs with a
  screen-by-screen session replay and the raw hash chain, the design with a live preview of what
  each arm sees for any case, power, and method.

Every console view names its population, and the human population is shown as pending.

## Model participants

Qwen3-4B-Instruct-2507 (Q4_0) and Phi-4-mini-instruct (Q4_K_M) run locally with llama.cpp on CPU
(2 threads, context 2,048, temperature 0.7). Each sees the same item as a person in its arm,
rendered as text (`llm.render`), with a system prompt equivalent to the consent page's
instructions, and must answer with JSON constrained to the item's two options and an integer
confidence. Invalid replies are retried with a new seed up to three more times, then recorded as
missing. Each call (seed, raw reply, validity, time) is logged in `model-pilot-calls.jsonl`. The
participant's seed is its slot, so participants of one model differ in seed as well as cases.

## Reproducibility

`results/<UTC>-<sha7>/` holds every result file and `provenance.json` (commit, dirty flag, quick
flag, settings, package versions, SHA-256 of every input log and the bank). `results/LATEST` moves
only for a run on a clean commit with full settings. CI rebuilds the bank from the downloaded data
and checks it is byte-identical, verifies every log's chain and runs a quick analysis.
