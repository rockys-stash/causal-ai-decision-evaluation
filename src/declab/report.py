"""Render docs/generated/results.md from an analysis result. Every number comes from the result files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from declab.paths import DOCS, RESULTS

OUTCOME = {"accuracy": "Accuracy", "cost": "Cost per decision", "log_seconds": "Time (log seconds)", "override": "Override rate",
           "appropriate": "Appropriate reliance", "brier": "Confidence Brier score"}  # fmt: skip
ARM = {"A": "A human only", "B": "B AI recommendation", "C": "C AI + uncertainty + explanation"}


def pct(v: float | None, d: int = 1) -> str:
    return "–" if v is None else f"{100 * v:.{d}f}%".replace("-", "−")


def num(v: float | None, d: int = 2) -> str:
    return "–" if v is None else f"{v:,.{d}f}".replace("-", "−")


def pp(v: float | None, d: int = 1) -> str:
    return "–" if v is None else f"{100 * v:+.{d}f}".replace("-", "−")


def pval(p: float | None) -> str:
    return "–" if p is None else "< 0.001" if p < 0.001 else f"{p:.3f}"


def table(head: list[str], rows: list[list[str]]) -> str:
    def numeric(i: int) -> bool:
        return all(re.match(r"^[\d−+<–\[]", r[i]) for r in rows if r[i] != "–")

    align = ["---:" if i and numeric(i) else "---" for i in range(len(head))]
    return "\n".join(
        ["| " + " | ".join(head) + " |", "| " + " | ".join(align) + " |"] + ["| " + " | ".join(r) + " |" for r in rows]
    )


def _ci(c: list[float] | None, scale: float = 100) -> str:
    return "–" if not c else f"{c[0] * scale:+.1f} to {c[1] * scale:+.1f}".replace("-", "−")


def population(
    key: str, v: dict[str, Any], sec: list[dict[str, Any]], cal: dict[str, Any], rel: dict[str, Any]
) -> list[str]:
    L = [f"## {v['label']}", ""]
    if not v.get("participants"):
        L += [
            f"**Status: {v['status']}.** No sessions of this kind have been run"
            + (" (no participants could be recruited in this environment)." if v["kind"] == "human" else "."),
            "",
        ]
        return L
    L += [f"{v['participants']} participants, {v['decisions']:,} analysed decisions"
          + (f", {v['missing_decisions']} invalid model answers recorded as missing" if v.get("missing_decisions") else "")
          + f"; log `{v.get('file', '')}`: {v['chain']}." + (f" Models: {', '.join(v['models'])}." if v.get("models") else ""), ""]  # fmt: skip
    if v.get("excluded"):
        L += [f"Excluded: {len(v['excluded'])} ({', '.join(sorted({e['excluded'] for e in v['excluded']}))}).", ""]
    L += [table(["Arm", "Participants", "Accuracy", "SD", "Cost / decision", "Median s", "AI accuracy (same cases)", "AI cost"],
                [[ARM[a["arm"]], str(a["participants"]), pct(a["accuracy"]), pct(a["accuracy_sd"]), num(a["cost"]), num(a["median_seconds"], 1),
                  pct(a["ai_accuracy"]), num(a["ai_cost"])] for a in v["arms"]]), ""]  # fmt: skip
    L += [
        "**Primary: accuracy** (randomization test, 10,000 permutations within stratum; Holm over three contrasts; 95% bootstrap interval in percentage points).",
        "",
    ]
    L += [table(["Contrast", "Difference (pp)", "95% CI", "Cohen's h", "Error reduction", "p", "p (Holm)"],
                [[c["contrast"], pp(c.get("diff")), _ci(c.get("ci")), num(c.get("cohens_h")), pct(c.get("error_reduction")),
                  pval(c.get("p")), pval(c.get("p_holm"))] for c in v["primary"]]), ""]  # fmt: skip
    g = v.get("gee") or {}
    if g and "error" not in g:
        L += ["Robustness (logistic GEE, exchangeable within participant, domain fixed effects): "
              + "; ".join(f"{k.replace('_vs_', ' vs ')} odds ratio {num(x['odds_ratio'])} ({num(x['ci'][0])}–{num(x['ci'][1])}), p = {pval(x['p'])}" for k, x in g.items()) + ".", ""]  # fmt: skip
    rows = []
    for c in sec:
        if c["outcome"].startswith("gap_"):
            continue
        scale = 100 if c["outcome"] in ("override", "appropriate") else 1
        d = c.get("diff")
        dv = "–" if d is None else (pp(d) if scale == 100 else num(d, 3))
        rows.append(
            [
                OUTCOME[c["outcome"]],
                c["contrast"],
                num(c.get("mean_a"), 3),
                num(c.get("mean_b"), 3),
                dv,
                pval(c.get("p")),
                pval(c.get("p_holm")),
            ]
        )
    L += ["**Secondary** (one family, Holm-corrected together, with the subgroup gaps below).", "",
          table(["Outcome", "Contrast", "First arm", "Second arm", "Difference", "p", "p (Holm)"], rows), ""]  # fmt: skip
    L += [
        "**Reliance.** Agreement with the AI's recommendation when it was right and when it was wrong (in arm A the "
        "recommendation was computed but not shown).",
        "",
    ]
    L += [table(["Arm", "Agree overall", "Agree, AI right", "Agree, AI wrong", "Appropriate reliance", "Mean confidence", "Brier"],
                [[ARM[a["arm"]], pct(a["agree"]), pct(a["agree_right"]), pct(a["agree_wrong"]), pp(a["appropriate"]), num(a["confidence"], 1), num(a["brier"], 3)]
                 for a in v["arms"]]), ""]  # fmt: skip
    if cal:
        L += ["**Calibration of stated confidence**: " + "; ".join(f"{a}: ECE {num(x['ece'], 3)}, mean confidence {pct(x['mean_confidence'])} vs accuracy {pct(x['accuracy'])}"
                                                            for a, x in sorted(cal.items())) + ".", ""]  # fmt: skip
    gaps = [c for c in sec if c["outcome"].startswith("gap_")]
    if gaps:
        L += ["**Subgroup error gaps** (error rate of the first group minus the second, pooled within arm).", ""]
        L += [table(["Domain", "Groups", "Contrast", "Gap, first arm", "Gap, second arm", "Change (pp)", "p", "p (Holm)"],
                    [[c["domain"].replace("_", " "), " vs ".join(c["groups"]), c["contrast"], pp(c["arm_a"]["gap"]), pp(c["arm_b"]["gap"]),
                      pp(c["diff"]), pval(c["p"]), pval(c["p_holm"])] for c in gaps]), ""]  # fmt: skip
    if rel.get("by_model"):
        L += ["**By model** (descriptive).", ""]
        L += [table(["Model", "Arm", "Participants", "Accuracy", "Agree with AI", "Appropriate reliance", "Mean confidence", "Median s"],
                    [[m["model"], m["arm"], str(m["participants"]), pct(m["accuracy"]), pct(m["agree"]), pp(m["appropriate"]), num(m["confidence"], 1),
                      num(m["seconds"], 1)] for m in rel["by_model"]]), ""]  # fmt: skip
    return L


def render(results: Path = RESULTS, out: Path | None = None) -> Path:
    rid = (results / "LATEST").read_text(encoding="utf-8").strip()
    d = results / rid

    def j(name: str) -> Any:
        return json.loads((d / f"{name}.json").read_text(encoding="utf-8"))

    ov, prim, sec, cal, rel, pw, ai, prov = (
        j(n) for n in ("overview", "primary", "secondary", "calibration", "reliance", "power", "ai", "provenance")
    )
    L = ["# Results", "",
         f"Generated by `declab report` from `results/{rid}` (commit `{prov['commit'][:7]}`, {'uncommitted changes' if prov['dirty'] else 'clean tree'}"
         f"{', quick settings' if prov['quick'] else ''}, {prov['runtime_seconds']} s). Do not edit by hand.", "",
         "**Study status.** Human participants: **pending** (none recruited). Every other result is labelled with its participant "
         "kind: simulated participants follow a stated behaviour model; model participants are local language models. Neither is "
         "evidence about people.", ""]  # fmt: skip
    L += [table(["Participants", "Status", "Sessions", "Analysed participants", "Decisions", "Log"],
                [[v["label"], v["status"], str(v["sessions"]), str(v["participants"]), f"{v['decisions']:,}" if v.get("decisions") else "–",
                  f"`{v['file']}`"] for v in ov["populations"].values()]), ""]  # fmt: skip
    L += [
        "## The AI recommender",
        "",
        "Logistic regression per domain, calibrated on a held-out part and shifted to the bank's 50% base rate. Test metrics are "
        "on the outcome-balanced test part; the bank is 40 cases per domain drawn from it.",
        "",
    ]
    L += [table(["Domain", "Records", "Base rate", "Test AUROC", "Boosting AUROC", "Balanced accuracy", "ECE (balanced)", "Bank accuracy", "Bank ECE"],
                [[k.replace("_", " "), f"{x['rows']:,}", pct(x["base_rate"]), num(x["test"]["auroc"], 3), num(x["boosting_test_auroc"], 3),
                  pct(x["test"]["accuracy_balanced"]), num(x["test"]["ece_balanced"], 3), pct(x["bank"]["ai_accuracy"]), num(x["bank"]["ai_ece"], 3)]
                 for k, x in ai.items()]), ""]  # fmt: skip
    for key in ("model", "simulated-planted", "simulated-no_effect", "human"):
        L += population(key, prim[key], sec.get(key) or [], cal.get(key) or {}, rel.get(key) or {})
    ex = pw["expected_accuracy"]
    L += ["## Validation of the analysis by simulation", "",
          f"Expected accuracy under the planted design (20,000 simulated participants per arm): A {pct(ex['planted']['A'])}, "
          f"B {pct(ex['planted']['B'])}, C {pct(ex['planted']['C'])}; under no effect: A {pct(ex['no_effect']['A'])}, B {pct(ex['no_effect']['B'])}, "
          f"C {pct(ex['no_effect']['C'])}.", "",
          f"**False-positive rate.** {pw['type1']['repetitions']} repetitions of the no-effect design with {pw['type1']['per_arm']} per arm "
          f"({pw['permutations_per_test']} permutations each): at least one Holm-significant contrast in {pct(pw['type1']['any_contrast'])} "
          f"(nominal 5% or less).", ""]  # fmt: skip
    L += ["**Power for the planted effects** (share of repetitions with a Holm-significant contrast).", "",
          table(["Per arm", "Repetitions", "C−A", "B−A", "C−B"], [[str(r["per_arm"]), str(r["repetitions"]), pct(r["C−A"], 0), pct(r["B−A"], 0), pct(r["C−B"], 0)]
                                                                for r in pw["curve"]]), ""]  # fmt: skip
    L += ["**Power for a 6-point accuracy difference** (the pre-registered sizing rule).", "",
          table(["Per arm", "Repetitions", "Power"], [[str(r["per_arm"]), str(r["repetitions"]), pct(r["power"], 0)] for r in pw["six_points"]]), "",
          f"Human study size from this rule: **{pw['human_per_arm'] or 'more than the largest size simulated'} per arm**.", ""]  # fmt: skip
    path = out or DOCS / "generated" / "results.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L).rstrip() + "\n", encoding="utf-8")
    return path
