"""The AI recommender: an interpretable logistic model per domain, calibrated, with per-case explanations.

Fitted on the training part (regularisation by cross-validated log loss), calibrated by Platt
scaling on the calibration part, then shifted to the task bank's 50% base rate (Bayes' rule on the
odds), so that a stated confidence of 70% means about 70% right on the bank. The explanation of a
case is each field's contribution to the log-odds (coefficient × the case's deviation from the
training mean), summed over a field's indicator columns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from declab.data import Field, fields

C_GRID = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0)


def _signed_log(x: Any) -> Any:
    return np.sign(x) * np.log1p(np.abs(x))


def _pre(flds: list[Field]) -> ColumnTransformer:
    num = [f.column for f in flds if f.kind == "num" and not f.log]
    lognum = [f.column for f in flds if f.kind == "num" and f.log]
    cat = [f.column for f in flds if f.kind == "cat"]
    parts: list[tuple[str, Any, list[str]]] = [
        ("num", StandardScaler(), num),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat),
    ]
    if lognum:
        parts.insert(
            1,
            (
                "log",
                Pipeline(
                    [
                        ("log", FunctionTransformer(_signed_log, feature_names_out="one-to-one")),
                        ("sc", StandardScaler()),
                    ]
                ),
                lognum,
            ),
        )
    return ColumnTransformer(parts, sparse_threshold=0.0, verbose_feature_names_out=False)


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


@dataclass
class Recommender:
    domain: str
    seed: int
    model: Pipeline = field(init=False)
    platt: tuple[float, float] = (1.0, 0.0)
    prior_logit: float = 0.0
    c: float = 1.0
    cv: list[dict[str, float]] = field(default_factory=list)
    means: np.ndarray = field(init=False)

    def fit(self, train: pd.DataFrame, calib: pd.DataFrame) -> Recommender:
        flds = fields(self.domain)
        X, y = train[[f.column for f in flds]], train["outcome"].to_numpy(int)
        folds = StratifiedKFold(5, shuffle=True, random_state=self.seed)
        best = (np.inf, 1.0)
        for c in C_GRID:
            m = Pipeline([("pre", _pre(flds)), ("lr", LogisticRegression(C=c, max_iter=5000))])
            p = cross_val_predict(m, X, y, cv=folds, method="predict_proba")[:, 1]
            ll = float(log_loss(y, p))
            self.cv.append({"c": c, "log_loss": ll, "auroc": float(roc_auc_score(y, p))})
            best = min(best, (ll, c))
        self.c = best[1]
        self.model = Pipeline([("pre", _pre(flds)), ("lr", LogisticRegression(C=self.c, max_iter=5000))]).fit(X, y)
        self.means = np.asarray(self.model.named_steps["pre"].transform(X)).mean(axis=0)
        z = self.model.decision_function(calib[[f.column for f in flds]])
        pl = LogisticRegression(C=1e6, max_iter=1000).fit(z.reshape(-1, 1), calib["outcome"].to_numpy(int))
        self.platt = (float(pl.coef_[0, 0]), float(pl.intercept_[0]))
        base = float(np.concatenate([y, calib["outcome"].to_numpy(int)]).mean())
        self.prior_logit = float(np.log(base / (1 - base)))
        return self

    def logit(self, df: pd.DataFrame, balanced: bool = True) -> np.ndarray:
        z = self.model.decision_function(df[[f.column for f in fields(self.domain)]])
        a, b = self.platt
        out = a * z + b
        return out - self.prior_logit if balanced else out

    def proba(self, df: pd.DataFrame, balanced: bool = True) -> np.ndarray:
        return 1 / (1 + np.exp(-self.logit(df, balanced)))

    def contributions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Per-case contribution of each field to the calibrated log-odds of the positive decision."""
        pre = self.model.named_steps["pre"]
        Xt = np.asarray(pre.transform(df[[f.column for f in fields(self.domain)]]))
        w = self.model.named_steps["lr"].coef_[0] * self.platt[0]
        names = list(pre.get_feature_names_out())
        out = {}
        for f in fields(self.domain):
            idx = [i for i, n in enumerate(names) if n == f.column or n.startswith(f.column + "_")]
            out[f.column] = ((Xt[:, idx] - self.means[idx]) * w[idx]).sum(axis=1)
        return pd.DataFrame(out, index=df.index)

    def card(self) -> dict[str, Any]:
        lr = self.model.named_steps["lr"]
        names = list(self.model.named_steps["pre"].get_feature_names_out())
        return {"c": self.c, "cv": self.cv, "platt": list(self.platt), "prior_logit": self.prior_logit,
                "coefficients": {n: float(v) for n, v in zip(names, lr.coef_[0], strict=True)}}  # fmt: skip


def boosting_reference(train: pd.DataFrame, domain: str, seed: int) -> Pipeline:
    flds = fields(domain)
    m = Pipeline([("pre", _pre(flds)), ("clf", HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05,
                                                                              max_depth=4, random_state=seed))])  # fmt: skip
    return m.fit(train[[f.column for f in flds]], train["outcome"].to_numpy(int))


def strength(v: float) -> str:
    a = abs(v)
    return "strong" if a >= 1.0 else "moderate" if a >= 0.4 else "weak"


def explain(
    rec: Recommender, row_contrib: pd.Series, row: pd.Series, k: int, labels: tuple[str, str]
) -> dict[str, Any]:
    """The k fields pushing most towards each decision, in the participant's words."""
    from declab.data import fmt

    by = {f.column: f for f in fields(rec.domain)}
    s = row_contrib.sort_values()

    def item(col: str, v: float) -> dict[str, Any]:
        f = by[col]
        return {
            "field": col,
            "label": f.label,
            "value": fmt(f, row[col]),
            "weight": round(float(v), 3),
            "strength": strength(v),
        }

    pos = [item(str(c), v) for c, v in s[::-1].items() if v > 0][:k]
    neg = [item(str(c), v) for c, v in s.items() if v < 0][:k]
    return {"towards_positive": pos, "towards_negative": neg, "positive_label": labels[0], "negative_label": labels[1]}
