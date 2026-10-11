# Internal review board

Reviewed 2026-10-11 against [REPORT.md](REPORT.md) and the result it cites
(`results/20261011T024226Z-d5953e1`, clean commit `d5953e1`). **Overall: pass, with the human
study pending.**

| Reviewer | Verdict | Required fixes |
|---|---|---|
| Statistics | Pass | Fixed during review: subgroup-gap reading added (D15) |
| Research integrity | Pass, human study pending | None open |
| Engineering | Pass | None open |
| QA | Pass | Fixed during review: four interface defects found by the browser tests |
| Security and privacy | Pass | None open |
| UX | Pass | Fixed during review: survey flashed the wrong form; contrast and landmark issues |
| Release | Pass, human study pending | Recruitment needs ethics approval and a participant pool (D13) |

## Statistics reviewer

- The pre-registration was committed before any session; its two amendments are dated and placed
  before the sessions they affect (A1 before the model pilot, A2 before any human session).
- Every figure in the report is in `docs/generated/results.md`, rendered from the result files;
  the report's derived numbers (planted differences 4.1, 2.3, 1.8 pp) follow from the stated
  expected accuracies.
- Inference is on participants, not decisions; randomization tests permute within stratum; Holm
  over the three primary contrasts and over the secondary family; a GEE on decisions agrees.
- The analysis's error rate (3.0% of 500 null studies) and power curves are reported, and the
  report says plainly that the planted dry run is underpowered for its own accuracy effects and
  that one of three intervals misses its planted value.
- D8 (planted skill lowered after the first dry run) changes only simulated behaviour; the
  analysis was not touched, and the change and its reason are recorded with both commits.
- Fixed during review: the credit-limit gap change (+57.3 pp, Holm p = 0.008) was a raw-gap
  artefact of a "reduce" lean and the arm-A sample's outcome mix; D15 and the report now say so,
  and the human analysis adds within-outcome gaps as exploratory.

## Research integrity reviewer

- Three participant kinds, never pooled: every table, chart, page and sentence names its kind;
  the console has a separate view per population, and "Human participants" shows *pending*.
- Model participants are called a pilot and "not people" in the interface, the README, the report
  and the generated results. Simulated participants are called a dry run used for validation.
- No human result is presented, estimated or implied. The hypotheses are left open for people.
- All 936 model calls are committed (`data/sessions/model-pilot-calls.jsonl`) with seed and reply;
  all were valid on the first attempt.

## Engineering reviewer

- Every participant kind goes through the same HTTP API; the session log is append-only SQLite
  with a SHA-256 chain, exported to JSONL; `declab verify` checks all four logs in CI.
- Allocation lists are generated before the first session from a seeded hash, and their hash is in
  each session's first event, so assignment can be audited.
- The bank is rebuilt from the hash-checked datasets in CI and must match the committed bank byte
  for byte.
- Results are versioned (`results/<UTC>-<sha7>` with config, commit, dirty flag, package versions
  and input hashes); `LATEST` moves only on a clean run.
- ruff, ruff format, mypy strict, ESLint and `tsc`; CI runs unit tests, verification, a smoke
  analysis, the bank rebuild, the web build, `npm audit` and the browser tests.

## QA reviewer

- 40 unit, API, store, design and analysis tests and 28 browser tests pass (`make test`,
  `make test-ui`). Unit tests cover the hash chain and tamper detection, blocked allocation,
  the bank's balance and that sex is never shown, what each arm sees, the API's order and
  validation rules and guards, and the analysis (Holm, permutations within strata, exclusions,
  a tampered log).
- Browser tests cover every console page at desktop and mobile width, the full participant flow in
  an AI arm and the no-AI arm, the population toggle, the pending label, session replay, the arm
  preview, keyboard navigation and axe-core (WCAG 2.1 A/AA and best practice) in both themes,
  including the study's task page.
- Fixed during review: the end-of-study survey briefly showed the no-AI form in AI arms; an
  overview caption duplicated a landmark name; old CSS rules failed colour contrast; a test label
  matched two fields.
- 27 screenshots from the running interface (9 views × desktop, desktop dark, mobile), including a
  real arm-C task page.
- **Fresh clone** (2026-10-11): a new clone of `25eed6b` ran `make setup test lint smoke`, rebuilt
  the bank from the downloaded datasets with no difference, re-ran `make analysis` and
  `make test-ui`, and passed. See the release reviewer for the regenerated report.

## Security and privacy reviewer

- Participant routes address a session by its random 128-bit id and enforce consent, order and
  the item's options; researcher routes, the session browser and non-human sessions need
  `DECLAB_TOKEN` beyond loopback (constant-time comparison); rate limiting and security headers on
  every response.
- No personal data are collected: participants are identified by a random id; the consent page
  states what is logged. The datasets are public and de-identified; sex is used only for the
  subgroup audit and never shown.

## UX reviewer

- The study is one decision per screen with the case, the AI panel for the arm and a confidence
  slider that must be moved; progress is shown; practice cases are marked.
- The console leads with study status, then results, reliance and calibration, sessions with a
  replay of what each participant saw and did, and the design with a live arm preview.

## Release reviewer

- README, PLAN, PREREGISTRATION, DESIGN, DATASET, METRICS, DECISIONS, REPORT and this review are
  present.
- **Human study: pending.** The platform, the sample size (60 per arm) and the analysis are ready;
  running it needs ethics approval and recruitment, which this environment cannot provide.
