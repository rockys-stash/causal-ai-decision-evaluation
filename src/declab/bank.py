"""Build the task bank: per domain, split, fit and calibrate the AI, and draw 40 test cases.

The bank is drawn from the test part only, 20 cases with each outcome, stratified on whether the AI
is right so that its accuracy on the bank equals its accuracy on the (outcome-balanced) test part.
The result is committed (``data/bank/``) so every session, of every participant kind, sees the
same cases and the same AI output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from declab import ai
from declab.config import domains, study
from declab.data import card, load
from declab.paths import BANK, RAW


def split(df: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    s = study()["split"]
    train, rest = train_test_split(df, train_size=s["train"], stratify=df["outcome"], random_state=seed)
    calib, test = train_test_split(rest, test_size=s["test"] / (s["test"] + s["calibration"]), stratify=rest["outcome"],
                                   random_state=seed)  # fmt: skip
    return train, calib, test


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10, w: np.ndarray | None = None) -> float:
    w = np.ones_like(p) if w is None else w
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    tot = 0.0
    for b in range(bins):
        m = idx == b
        if w[m].sum() > 0:
            tot += w[m].sum() * abs(np.average(y[m], weights=w[m]) - np.average(p[m], weights=w[m]))
    return float(tot / w.sum())


def _metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    """Metrics on the outcome-balanced population: each class weighted to half."""
    w = np.where(y == 1, 0.5 / max(y.mean(), 1e-9), 0.5 / max(1 - y.mean(), 1e-9))
    pred = (p >= 0.5).astype(int)
    tpr, tnr = float(pred[y == 1].mean()), float(1 - pred[y == 0].mean())
    return {"auroc": float(roc_auc_score(y, p)), "accuracy_balanced": (tpr + tnr) / 2, "tpr": tpr, "tnr": tnr,
            "ece_balanced": ece(y, p, 10, w), "brier_balanced": float(np.average((p - y) ** 2, weights=w)),
            "n": len(y), "positives": int(y.sum())}  # fmt: skip


def build(raw: Path = RAW, out: Path = BANK) -> dict[str, Any]:
    cfg = study()
    seed, per, k = int(cfg["seed"]), int(cfg["bank_per_domain"]), int(cfg["explanation_factors"])
    rng = np.random.default_rng(seed)
    cases: list[dict[str, Any]] = []
    practice: list[dict[str, Any]] = []
    report: dict[str, Any] = {}
    for d, dc in domains().items():
        df = load(d, raw)
        train, calib, test = split(df, seed)
        rec = ai.Recommender(d, seed).fit(train, calib)
        p = rec.proba(test)
        y = test["outcome"].to_numpy(int)
        gb = ai.boosting_reference(train, d, seed)
        p_gb = gb.predict_proba(test[[c for c in rec.model.feature_names_in_]])[:, 1]
        m = _metrics(y, p)
        report[d] = {"rows": len(df), "base_rate": float(df["outcome"].mean()), "split": [len(train), len(calib), len(test)],
                     "test": m, "boosting_test_auroc": float(roc_auc_score(y, p_gb)), "model": rec.card()}  # fmt: skip
        right = (p >= 0.5).astype(int) == y
        chosen: list[Any] = []
        half = per // 2
        for outcome, rate in ((1, m["tpr"]), (0, m["tnr"])):
            n_right = round(half * rate)
            for ok, n in ((True, n_right), (False, half - n_right)):
                pool = test.index[(y == outcome) & (right == ok)]
                chosen += list(rng.choice(pool, size=n, replace=False))
        bank = test.loc[chosen]
        rest = test.drop(index=chosen)
        prac = rest.loc[list(rng.choice(rest.index, size=2, replace=False))]
        for kind, frame in (("bank", bank), ("practice", prac)):
            pb, contrib = rec.proba(frame), rec.contributions(frame)
            labels = (dc["positive"]["label"], dc["negative"]["label"])
            for i, (row_key, row) in enumerate(frame.iterrows()):
                row_id: Any = row_key
                pos = bool(pb[i] >= 0.5)
                sg = dc["subgroup"]
                group = (
                    (sg["labels"][0] if row[sg["column"]] < sg["below"] else sg["labels"][1])
                    if "below" in sg
                    else str(row[sg["column"]])
                )
                c = {"id": f"{d}-{'p' if kind == 'practice' else ''}{i + 1:02d}", "domain": d, "source_row": int(row_id),
                     "card": card(d, row), "outcome": int(row["outcome"]), "subgroup": group,
                     "ai": {"decision": dc["positive" if pos else "negative"]["decision"],
                            "label": labels[0] if pos else labels[1],
                            "p_positive": round(float(pb[i]), 4),
                            "confidence": round(float(max(pb[i], 1 - pb[i])), 4),
                            "explanation": ai.explain(rec, contrib.loc[row_id], row, k, labels)}}  # fmt: skip
                (cases if kind == "bank" else practice).append(c)
        bm = [c for c in cases if c["domain"] == d]
        yb = np.array([c["outcome"] for c in bm])
        pbk = np.array([c["ai"]["p_positive"] for c in bm])
        report[d]["bank"] = {"cases": len(bm), "ai_accuracy": float(((pbk >= 0.5).astype(int) == yb).mean()),
                             "ai_ece": ece(yb, pbk, 5), "auroc": float(roc_auc_score(yb, pbk))}  # fmt: skip
    out.mkdir(parents=True, exist_ok=True)
    (out / "bank.json").write_text(
        json.dumps({"cases": cases, "practice": practice}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "ai_report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return report


def read(path: Path = BANK) -> dict[str, Any]:
    return dict(json.loads((path / "bank.json").read_text(encoding="utf-8")))
