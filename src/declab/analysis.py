"""The pre-registered analysis (docs/PREREGISTRATION.md), run on every committed session log.

Each participant kind is analysed separately and never pooled: simulated (planted effects),
simulated (no effect), model participants, and human participants (pending until sessions exist).
The participant is the unit: decisions are summarised per participant, and arms are compared by
randomization tests that permute arm labels among participants (within stratum).
"""

from __future__ import annotations

import json
import math
import os
import platform
import subprocess
import time
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from declab import bank as bankmod
from declab.bank import ece
from declab.config import domains, study
from declab.data import sha256
from declab.participants import sim_config
from declab.paths import BANK, CONFIGS, DOCS, RESULTS, ROOT, SESSIONS
from declab.store import read_jsonl, verify

CONTRASTS = (("C", "A"), ("B", "A"), ("C", "B"))
POPULATIONS = {
    "simulated-planted": {"file": "simulated-planted.jsonl", "label": "Simulated participants, planted effects (dry run)", "kind": "simulated"},
    "simulated-no_effect": {"file": "simulated-no_effect.jsonl", "label": "Simulated participants, no effect (dry run)", "kind": "simulated"},
    "model": {"file": "model-pilot.jsonl", "label": "Model participants (pilot; not people)", "kind": "model"},
    "human": {"file": "human.jsonl", "label": "Human participants", "kind": "human"},
}
SUBGROUP_DOMAINS = ("loan", "credit_limit")  # pre-registered subgroup audits


# ---------- from events to tables ----------
def tables(events: list[dict[str, Any]], bank: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    cases = {c["id"]: c for c in bank["cases"] + bank["practice"]}
    dcfg = domains()
    sess: dict[str, dict[str, Any]] = {}
    timing: dict[tuple[str, int], float] = {}
    rows = []
    for e in events:
        d, s = e["data"], e["session"]
        if e["kind"] == "session_created":
            sess[s] = {"session": s, "kind": d["participant_kind"], "model": d["model"] or "", "stratum": d["stratum"],
                       "arm": d["arm"], "slot": d["slot"], "completed": False, "survey": None}  # fmt: skip
        elif e["kind"] == "decision":
            rows.append({"session": s, **{k: d[k] for k in ("index", "phase", "case", "decision", "confidence", "client_ms")}})
        elif e["kind"] == "timing":
            timing[(s, d["index"])] = d["server_seconds"]
        elif e["kind"] == "survey":
            sess[s]["survey"] = d
        elif e["kind"] == "session_completed":
            sess[s]["completed"] = True
    S = pd.DataFrame(list(sess.values()))
    D = pd.DataFrame(rows)
    if D.empty:
        return S, D
    D["server_seconds"] = [timing.get((s, i), np.nan) for s, i in zip(D["session"], D["index"], strict=True)]
    D = D.merge(S[["session", "kind", "model", "stratum", "arm"]], on="session")
    att = D[D["phase"] == "attention"]
    D = D[D["phase"] == "task"].copy()
    D["domain"] = [cases[c]["domain"] for c in D["case"]]
    D["outcome"] = [cases[c]["outcome"] for c in D["case"]]
    D["ai_p"] = [cases[c]["ai"]["p_positive"] for c in D["case"]]
    D["ai_conf"] = [cases[c]["ai"]["confidence"] for c in D["case"]]
    D["ai_rec"] = [cases[c]["ai"]["decision"] for c in D["case"]]
    D["subgroup"] = [cases[c]["subgroup"] for c in D["case"]]
    pos = {k: v["positive"]["decision"] for k, v in dcfg.items()}
    neg = {k: v["negative"]["decision"] for k, v in dcfg.items()}
    D["right"] = [pos[d] if o else neg[d] for d, o in zip(D["domain"], D["outcome"], strict=True)]
    D["missing"] = D["decision"].isna()
    D["correct"] = (D["decision"] == D["right"]).astype(float).where(~D["missing"])
    D["agree"] = (D["decision"] == D["ai_rec"]).astype(float).where(~D["missing"])
    D["ai_right"] = (D["ai_rec"] == D["right"]).astype(int)
    fp = {k: v["costs"]["false_positive"] for k, v in dcfg.items()}
    fn = {k: v["costs"]["false_negative"] for k, v in dcfg.items()}
    D["cost"] = [np.nan if m else 0.0 if c == r else (fp[d] if c == pos[d] else fn[d])
                 for m, c, r, d in zip(D["missing"], D["decision"], D["right"], D["domain"], strict=True)]  # fmt: skip
    D["ai_cost"] = [0.0 if a == r else (fp[d] if a == pos[d] else fn[d]) for a, r, d in zip(D["ai_rec"], D["right"], D["domain"], strict=True)]
    # Simulated participants do not wait: their time is drawn by the behaviour model and sent as client time.
    D["seconds"] = np.where(D["kind"] == "simulated", D["client_ms"].astype(float) / 1000, D["server_seconds"])
    # Exclusions (PREREGISTRATION)
    S["excluded"] = ""
    S.loc[~S["completed"], "excluded"] = "incomplete"
    if not att.empty:
        want = {"attention-1": "decline", "attention-2": "approve"}
        fails = att.assign(ok=[want.get(c) == d for c, d in zip(att["case"], att["decision"], strict=True)])
        bad = fails.groupby("session")["ok"].sum()
        S.loc[S["session"].isin(bad[bad == 0].index) & (S["excluded"] == ""), "excluded"] = "failed both attention checks"
    miss = D.groupby("session")["missing"].mean()
    S.loc[S["session"].isin(miss[miss > 0.2].index) & (S["excluded"] == ""), "excluded"] = "over 20% invalid answers"
    D = D[D["session"].isin(S.loc[S["excluded"] == "", "session"])]
    return S, D


def participants(D: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (s, st, arm, model), g in D.groupby(["session", "stratum", "arm", "model"]):
        v = g[~g["missing"]]
        r, w = v[v["ai_right"] == 1], v[v["ai_right"] == 0]
        row: dict[str, Any] = {"session": s, "stratum": st, "arm": arm, "model": model, "n": len(v), "missing": int(g["missing"].sum()),
               "accuracy": v["correct"].mean(), "cost": v["cost"].mean(), "log_seconds": np.log(v["seconds"].clip(lower=0.05)).mean(),
               "median_seconds": v["seconds"].median(), "agree": v["agree"].mean(), "override": 1 - v["agree"].mean(),
               "agree_right": r["agree"].mean(), "agree_wrong": w["agree"].mean(),
               "appropriate": r["agree"].mean() - w["agree"].mean(), "brier": ((v["confidence"] / 100 - v["correct"]) ** 2).mean(),
               "confidence": v["confidence"].mean(), "ai_accuracy": v["ai_right"].mean(), "ai_cost": v["ai_cost"].mean()}  # fmt: skip
        for d in SUBGROUP_DOMAINS:
            gd = v[v["domain"] == d]
            for lab in domains()[d]["subgroup"]["labels"]:
                m = gd["subgroup"] == lab
                row[f"err_{d}_{lab}"] = float((1 - gd.loc[m, "correct"]).sum())
                row[f"n_{d}_{lab}"] = int(m.sum())
        rows.append(row)
    return pd.DataFrame(rows)


# ---------- inference ----------
def holm(p: list[float]) -> list[float]:
    order = np.argsort(p)
    out, run = [0.0] * len(p), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(p) - rank) * p[i]))
        out[i] = run
    return out


def _labels_perm(strata: np.ndarray, is_b: np.ndarray, rng: np.random.Generator, n: int) -> np.ndarray:
    """n permutations of the arm labels, shuffled within each stratum."""
    out = np.empty((n, len(is_b)), dtype=bool)
    for k in range(n):
        lab = is_b.copy()
        for s in np.unique(strata):
            idx = np.flatnonzero(strata == s)
            lab[idx] = rng.permutation(lab[idx])
        out[k] = lab
    return out


def perm_test(values: np.ndarray, is_b: np.ndarray, strata: np.ndarray, n: int, rng: np.random.Generator) -> float:
    """Two-sided randomization p-value for mean(b) − mean(a) (rows with a missing value dropped)."""
    ok = ~np.isnan(values)
    v, b, s = values[ok], is_b[ok], strata[ok]
    if b.sum() == 0 or (~b).sum() == 0:
        return float("nan")
    obs = v[b].mean() - v[~b].mean()
    L = _labels_perm(s, b, rng, n)
    diffs = (L @ v) / L.sum(axis=1) - ((~L) @ v) / (~L).sum(axis=1)
    return float((np.sum(np.abs(diffs) >= abs(obs) - 1e-12) + 1) / (n + 1))


def boot_ci(a: np.ndarray, b: np.ndarray, n: int, rng: np.random.Generator) -> list[float]:
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return [float("nan"), float("nan")]
    ia, ib = rng.integers(0, len(a), (n, len(a))), rng.integers(0, len(b), (n, len(b)))
    d = b[ib].mean(axis=1) - a[ia].mean(axis=1)
    return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]


def cohens_h(p1: float, p2: float) -> float:
    return float(2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2)))


def contrast(P: pd.DataFrame, col: str, b: str, a: str, perms: int, boots: int, rng: np.random.Generator) -> dict[str, Any]:
    sub = P[P["arm"].isin([a, b])]
    va, vb = sub.loc[sub["arm"] == a, col].to_numpy(float), sub.loc[sub["arm"] == b, col].to_numpy(float)
    out = {"contrast": f"{b}−{a}", "outcome": col, "mean_a": float(np.nanmean(va)) if len(va) else None,
           "mean_b": float(np.nanmean(vb)) if len(vb) else None, "n_a": int((~np.isnan(va)).sum()), "n_b": int((~np.isnan(vb)).sum())}  # fmt: skip
    if out["n_a"] < 2 or out["n_b"] < 2:
        return out | {"diff": None, "ci": None, "p": None}
    out["diff"] = out["mean_b"] - out["mean_a"]
    out["ci"] = boot_ci(va, vb, boots, rng)
    out["p"] = perm_test(sub[col].to_numpy(float), (sub["arm"] == b).to_numpy(), sub["stratum"].to_numpy(), perms, rng)
    return out


def gap_contrast(P: pd.DataFrame, d: str, b: str, a: str, perms: int, rng: np.random.Generator) -> dict[str, Any]:
    """Change in the subgroup error-rate gap between two arms (pooled within arm), randomization p-value."""
    g1, g2 = domains()[d]["subgroup"]["labels"]
    sub = P[P["arm"].isin([a, b])]
    e1, n1 = sub[f"err_{d}_{g1}"].to_numpy(float), sub[f"n_{d}_{g1}"].to_numpy(float)
    e2, n2 = sub[f"err_{d}_{g2}"].to_numpy(float), sub[f"n_{d}_{g2}"].to_numpy(float)
    isb = (sub["arm"] == b).to_numpy()

    def gaps(mask: np.ndarray) -> np.ndarray:  # mask: (k, n) rows in arm b
        m = mask.astype(float)
        gb = (m @ e1) / np.maximum(m @ n1, 1) - (m @ e2) / np.maximum(m @ n2, 1)
        r = 1 - m
        ga = (r @ e1) / np.maximum(r @ n1, 1) - (r @ e2) / np.maximum(r @ n2, 1)
        return np.asarray(gb - ga)

    obs = float(gaps(isb[None, :])[0])
    L = _labels_perm(sub["stratum"].to_numpy(), isb, rng, perms)
    p = float((np.sum(np.abs(gaps(L)) >= abs(obs) - 1e-12) + 1) / (perms + 1))

    def arm_gap(arm: str) -> dict[str, float]:
        s = P[P["arm"] == arm]
        r1, r2 = s[f"err_{d}_{g1}"].sum() / max(s[f"n_{d}_{g1}"].sum(), 1), s[f"err_{d}_{g2}"].sum() / max(s[f"n_{d}_{g2}"].sum(), 1)
        return {"error_1": float(r1), "error_2": float(r2), "gap": float(r1 - r2), "n_1": int(s[f"n_{d}_{g1}"].sum()), "n_2": int(s[f"n_{d}_{g2}"].sum())}

    return {"contrast": f"{b}−{a}", "outcome": f"gap_{d}", "domain": d, "groups": [g1, g2], "diff": obs, "p": p,
            "arm_a": arm_gap(a), "arm_b": arm_gap(b)}  # fmt: skip


def gee(D: pd.DataFrame) -> dict[str, Any]:
    """Robustness: logistic GEE, correct ~ arm + domain (+ model), exchangeable within participant."""
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    v = D[~D["missing"]].copy()
    v["correct"] = v["correct"].astype(int)
    if v["arm"].nunique() < 3 or v["session"].nunique() < 6:
        return {}
    f = "correct ~ C(arm, Treatment('A')) + C(domain)" + (" + C(model)" if v["model"].nunique() > 1 else "")
    try:
        m = smf.gee(f, groups="session", data=v, family=sm.families.Binomial(), cov_struct=sm.cov_struct.Exchangeable()).fit()
    except Exception as e:  # noqa: BLE001 - reported, not fatal
        return {"error": str(e)}
    out = {}
    for arm in ("B", "C"):
        k = f"C(arm, Treatment('A'))[T.{arm}]"
        lo, hi = m.conf_int().loc[k]
        out[f"{arm}_vs_A"] = {"odds_ratio": float(np.exp(m.params[k])), "ci": [float(np.exp(lo)), float(np.exp(hi))], "p": float(m.pvalues[k])}
    return out


def calibration(D: pd.DataFrame, bins: int) -> dict[str, Any]:
    out = {}
    for arm, g in D[~D["missing"]].groupby("arm"):
        c, y = g["confidence"].to_numpy(float) / 100, g["correct"].to_numpy(float)
        edges = np.linspace(0.5, 1.0, bins + 1)
        idx = np.clip(np.digitize(c, edges[1:-1]), 0, bins - 1)
        curve = [{"bin": [float(edges[i]), float(edges[i + 1])], "n": int((idx == i).sum()),
                  "confidence": float(c[idx == i].mean()) if (idx == i).any() else None,
                  "accuracy": float(y[idx == i].mean()) if (idx == i).any() else None} for i in range(bins)]  # fmt: skip
        e = sum(b["n"] * abs(b["confidence"] - b["accuracy"]) for b in curve if b["n"]) / max(len(c), 1)
        out[str(arm)] = {"ece": float(e), "brier": float(np.mean((c - y) ** 2)), "mean_confidence": float(c.mean()),
                         "accuracy": float(y.mean()), "curve": curve}  # fmt: skip
    return out


def analyse_population(events: list[dict[str, Any]], bank: dict[str, Any], perms: int, boots: int, seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    S, D = tables(events, bank)
    ok, chain = verify(events)
    res: dict[str, Any] = {"sessions": int(len(S)), "chain_ok": ok, "chain": chain,
                           "excluded": S.loc[S["excluded"] != "", ["session", "arm", "excluded"]].to_dict(orient="records") if len(S) else []}  # fmt: skip
    if D.empty:
        return res | {"participants": 0}
    P = participants(D)
    res["participants"] = int(len(P))
    res["decisions"] = int((~D["missing"]).sum())
    res["missing_decisions"] = int(D["missing"].sum())
    res["models"] = sorted(m for m in P["model"].unique() if m)
    arms = []
    for arm, g in P.groupby("arm"):
        arms.append({"arm": arm, "participants": len(g), "accuracy": float(g["accuracy"].mean()), "accuracy_sd": float(g["accuracy"].std()),
                     "cost": float(g["cost"].mean()), "median_seconds": float(np.exp(g["log_seconds"].mean())),
                     "agree": float(g["agree"].mean()), "agree_right": float(g["agree_right"].mean()), "agree_wrong": float(g["agree_wrong"].mean()),
                     "appropriate": float(g["appropriate"].mean()), "brier": float(g["brier"].mean()), "confidence": float(g["confidence"].mean()),
                     "ai_accuracy": float(g["ai_accuracy"].mean()), "ai_cost": float(g["ai_cost"].mean())})  # fmt: skip
    res["arms"] = arms
    acc = {a["arm"]: a["accuracy"] for a in arms}
    prim = [contrast(P, "accuracy", b, a, perms, boots, rng) for b, a in CONTRASTS]
    ph = holm([c["p"] if c["p"] is not None else 1.0 for c in prim])
    for c, h in zip(prim, ph, strict=True):
        b, a = c["contrast"].split("−")
        c["p_holm"] = h
        if c["diff"] is not None:
            c["cohens_h"] = cohens_h(acc[b], acc[a])
            c["error_reduction"] = 1 - (1 - acc[b]) / (1 - acc[a]) if acc[a] < 1 else None
    res["primary"] = prim
    sec = [contrast(P, "cost", b, a, perms, boots, rng) for b, a in CONTRASTS]
    sec += [contrast(P, "log_seconds", b, a, perms, boots, rng) for b, a in CONTRASTS]
    sec += [contrast(P, "override", "C", "B", perms, boots, rng)]
    sec += [contrast(P, "appropriate", b, a, perms, boots, rng) for b, a in CONTRASTS]
    sec += [contrast(P, "brier", b, a, perms, boots, rng) for b, a in CONTRASTS]
    sec += [gap_contrast(P, d, b, a, perms, rng) for d in SUBGROUP_DOMAINS for b, a in CONTRASTS]
    sh = holm([c["p"] if c.get("p") is not None and not math.isnan(c["p"]) else 1.0 for c in sec])
    for c, h in zip(sec, sh, strict=True):
        c["p_holm"] = h
    res["secondary"] = sec
    res["gee"] = gee(D)
    res["calibration"] = calibration(D, int(study()["analysis"]["ece_bins"]))
    res["by_domain"] = (D[~D["missing"]].groupby(["arm", "domain"]).agg(accuracy=("correct", "mean"), agree=("agree", "mean"),
                        ai_accuracy=("ai_right", "mean"), decisions=("correct", "size")).reset_index().to_dict(orient="records"))  # fmt: skip
    if len(res["models"]) > 1:
        res["by_model"] = (P.groupby(["model", "arm"]).agg(participants=("session", "size"), accuracy=("accuracy", "mean"),
                           agree=("agree", "mean"), appropriate=("appropriate", "mean"), confidence=("confidence", "mean"),
                           seconds=("median_seconds", "median")).reset_index().to_dict(orient="records"))  # fmt: skip
    res["participant_table"] = P[["session", "model", "arm", "n", "missing", "accuracy", "agree", "appropriate", "confidence",
                                  "median_seconds"]].to_dict(orient="records")  # fmt: skip
    return res


# ---------- simulation: error rate, power, planted truth ----------
def _sim_arrays(bank: dict[str, Any]) -> dict[str, Any]:
    cs = bank["cases"]
    return {"domain": np.array([c["domain"] for c in cs]), "outcome": np.array([c["outcome"] for c in cs]),
            "ai_p": np.array([c["ai"]["p_positive"] for c in cs])}  # fmt: skip


def simulate_accuracy(p: dict[str, Any], arm: str, idx: np.ndarray, A: dict[str, Any], rng: np.random.Generator) -> np.ndarray:
    """Vectorised form of ``participants.behave`` (same formulas): correctness of each decision in idx (n, 24)."""
    y, ap = A["outcome"][idx], A["ai_p"][idx]
    ai_logit = np.log(ap / (1 - ap))
    own = p["skill"] * np.where(y == 1, 1, -1) + p["shared"] * ai_logit + rng.normal(0, p["noise"], idx.shape)
    choice = own >= 0
    ai_pos = ap >= 0.5
    if arm != "A":
        conf_ai = np.maximum(ap, 1 - ap)
        sw = p["switch_b"] if arm == "B" else 1 / (1 + np.exp(-(p["c0"] + p["c1"] * (conf_ai - 0.5))))
        flip = (choice != ai_pos) & (rng.random(idx.shape) < sw)
        choice = np.where(flip, ai_pos, choice)
    return np.asarray((choice == (y == 1)).astype(float))


def _draw_cases(n: int, A: dict[str, Any], rng: np.random.Generator) -> np.ndarray:
    per = int(study()["cases_per_participant"]) // 6
    groups = [np.flatnonzero((A["domain"] == d) & (A["outcome"] == o)) for d in domains() for o in (1, 0)]
    return np.stack([np.concatenate([rng.choice(g, per, replace=False) for g in groups]) for _ in range(n)])


def power(bank: dict[str, Any], quick: bool, seed: int) -> dict[str, Any]:
    cfg = sim_config()
    A = _sim_arrays(bank)
    rng = np.random.default_rng(seed)
    perms = 200 if quick else 1000
    out: dict[str, Any] = {"permutations_per_test": perms}
    # planted truth: expected arm accuracy from a large number of simulated participants
    truth = {}
    for design in ("planted", "no_effect"):
        idx = _draw_cases(20000, A, rng)
        truth[design] = {arm: float(simulate_accuracy(cfg["designs"][design], arm, idx, A, rng).mean()) for arm in "ABC"}
    out["expected_accuracy"] = truth

    def one(design: str, n: int) -> list[float]:
        accs = {arm: simulate_accuracy(cfg["designs"][design], arm, _draw_cases(n, A, rng), A, rng).mean(axis=1) for arm in "ABC"}
        ps = []
        for b, a in CONTRASTS:
            v = np.concatenate([accs[a], accs[b]])
            isb = np.r_[np.zeros(n, bool), np.ones(n, bool)]
            ps.append(perm_test(v, isb, np.zeros(2 * n), perms, rng))
        return holm(ps)

    reps0 = 50 if quick else int(cfg["no_effect_repetitions"])
    n0 = int(cfg["per_arm"])
    rej = np.array([[p < 0.05 for p in one("no_effect", n0)] for _ in range(reps0)])
    out["type1"] = {"per_arm": n0, "repetitions": reps0, "any_contrast": float(rej.any(axis=1).mean()),
                    "by_contrast": {f"{b}−{a}": float(r) for (b, a), r in zip(CONTRASTS, rej.mean(axis=0), strict=True)}}  # fmt: skip
    reps = 30 if quick else int(cfg["power_repetitions"])
    curve = []
    for n in cfg["power_per_arm"]:
        r = np.array([[p < 0.05 for p in one("planted", int(n))] for _ in range(reps)])
        curve.append({"per_arm": int(n), "repetitions": reps,
                      **{f"{b}−{a}": float(v) for (b, a), v in zip(CONTRASTS, r.mean(axis=0), strict=True)}})  # fmt: skip
    out["curve"] = curve
    # The pre-registered sizing rule: 80% power for a 6-point accuracy difference between two arms. Arm A's simulated
    # participants against the same participants with 6 points more accuracy (each error corrected with the probability
    # that adds 0.06 on average), tested exactly as the primary contrasts are.
    pa = cfg["designs"]["no_effect"]
    base = truth["no_effect"]["A"]
    fix = 0.06 / (1 - base)
    six = []
    for n in cfg["power_per_arm"]:
        hits = 0
        for _ in range(reps):
            a = simulate_accuracy(pa, "A", _draw_cases(int(n), A, rng), A, rng)
            b = simulate_accuracy(pa, "A", _draw_cases(int(n), A, rng), A, rng)
            b = np.where((b == 0) & (rng.random(b.shape) < fix), 1.0, b)
            v = np.concatenate([a.mean(axis=1), b.mean(axis=1)])
            p = perm_test(v, np.r_[np.zeros(int(n), bool), np.ones(int(n), bool)], np.zeros(2 * int(n)), perms, rng)
            hits += min(1.0, 3 * p) < 0.05  # Holm's most stringent step over three contrasts
        six.append({"per_arm": int(n), "repetitions": reps, "power": hits / reps})
    out["six_points"] = six
    ok = [r["per_arm"] for r in six if r["power"] >= 0.8]
    out["human_per_arm"] = min(ok) if ok else None
    return out


# ---------- run ----------
def git_commit() -> tuple[str, bool]:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "src", "configs", "data"], cwd=ROOT,
                                    capture_output=True, text=True, check=True).stdout.strip())  # fmt: skip
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "0000000", True
    return sha, dirty


def _clean(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 6)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def write(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(_clean(obj), indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def run(results: Path = RESULTS, quick: bool = False, sessions: Path = SESSIONS) -> Path:
    t0 = time.perf_counter()
    cfg = study()["analysis"]
    perms, boots = (1000, 1000) if quick else (int(cfg["permutations"]), int(cfg["bootstrap"]))
    bank = bankmod.read()
    pops: dict[str, Any] = {}
    for key, meta in POPULATIONS.items():
        f = sessions / meta["file"]
        base = {"label": meta["label"], "kind": meta["kind"], "file": f"data/sessions/{meta['file']}"}
        if not f.exists():
            pops[key] = base | {"status": "pending", "sessions": 0, "participants": 0}
            continue
        r = analyse_population(read_jsonl(f), bank, perms, boots, seed=int(study()["seed"]))
        pops[key] = base | {"status": "complete" if r.get("participants") else "no sessions"} | r
    pw = power(bank, quick, seed=int(study()["seed"]) + 1)
    sha, dirty = git_commit()
    rid = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{sha[:7]}"
    out = results / rid
    out.mkdir(parents=True, exist_ok=False)
    keys_primary = ("label", "kind", "status", "file", "sessions", "participants", "decisions", "missing_decisions", "excluded", "chain_ok",
                    "chain", "models", "arms", "primary", "gee")  # fmt: skip
    write(out / "overview.json", {"populations": {k: {kk: v.get(kk) for kk in ("label", "kind", "status", "sessions", "participants",
                                                                         "decisions", "chain_ok", "file")} for k, v in pops.items()},
                                  "human_study": "pending" if pops["human"]["status"] == "pending" else pops["human"]["status"],
                                  "arms": {k: v["label"] for k, v in study()["arms"].items()}, "quick": quick})  # fmt: skip
    write(out / "primary.json", {k: {kk: v.get(kk) for kk in keys_primary} for k, v in pops.items()})
    write(out / "secondary.json", {k: v.get("secondary") for k, v in pops.items()})
    write(out / "reliance.json", {k: {"arms": v.get("arms"), "by_domain": v.get("by_domain"), "by_model": v.get("by_model"),
                                      "participants": v.get("participant_table")} for k, v in pops.items()})  # fmt: skip
    write(out / "calibration.json", {k: v.get("calibration") for k, v in pops.items()})
    write(out / "subgroups.json", {k: [c for c in (v.get("secondary") or []) if str(c.get("outcome", "")).startswith("gap_")] for k, v in pops.items()})
    write(out / "power.json", pw)
    write(out / "ai.json", json.loads((BANK / "ai_report.json").read_text(encoding="utf-8")))
    files = [*sorted((ROOT / "src" / "declab").glob("*.py")), *sorted(CONFIGS.glob("*.yaml")), BANK / "bank.json",
             *sorted(sessions.glob("*.jsonl")), DOCS / "PREREGISTRATION.md"]  # fmt: skip
    write(out / "provenance.json", {
        "run_id": rid, "commit": sha, "dirty": dirty, "quick": quick, "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "runtime_seconds": round(time.perf_counter() - t0, 1), "python": platform.python_version(), "cpus": os.cpu_count(),
        "permutations": perms, "bootstrap": boots,
        "packages": {p: metadata.version(p) for p in ("numpy", "pandas", "scipy", "scikit-learn", "statsmodels", "fastapi")},
        "inputs_sha256": {str(f.relative_to(ROOT)): sha256(f) for f in files if f.exists()},
        "preregistration_amendments": (DOCS / "PREREGISTRATION.md").read_text(encoding="utf-8").count("**A"),
    })  # fmt: skip
    if (not dirty and not quick) or results != RESULTS:
        (results / "LATEST").write_text(rid + "\n", encoding="utf-8")
    return out
