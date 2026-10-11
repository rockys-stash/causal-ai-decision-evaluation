"""The three public datasets, fetched and hash-checked, and turned into decision cases.

Each domain keeps only the information a decision-maker would have before deciding, labelled in
plain words. The same fields go to the participant and to the AI, so the AI knows nothing the
participant cannot see. Columns that leak the outcome (the marketing call's duration) or that
record the call itself (day, month, contact type) are dropped; sex is kept only to audit errors.
"""

from __future__ import annotations

import hashlib
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from declab.config import study
from declab.paths import RAW


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(raw: Path = RAW) -> dict[str, Path]:
    """Download any missing dataset and verify every file against its pinned SHA-256."""
    raw.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, d in study()["datasets"].items():
        path = raw / f"{name}.parquet"
        if not path.exists():
            tmp = path.with_suffix(".part")
            with urllib.request.urlopen(d["url"], timeout=120) as r, tmp.open("wb") as f:
                shutil.copyfileobj(r, f)
            tmp.replace(path)
        if sha256(path) != d["sha256"]:
            raise ValueError(f"{path.name}: SHA-256 does not match configs/study.yaml; delete it and run `make data`")
        out[name] = path
    return out


@dataclass(frozen=True)
class Field:
    column: str
    label: str
    kind: str  # "num" (shown as a number) or "cat"
    unit: str = ""
    log: bool = False  # model the number on a log scale (money amounts)


# ---------- loan approval: Statlog German credit ----------
LOAN_FIELDS = [
    Field("checking", "Checking account", "cat"),
    Field("duration", "Loan duration", "num", "months"),
    Field("amount", "Loan amount", "num", "DM", log=True),
    Field("purpose", "Purpose", "cat"),
    Field("history", "Credit history", "cat"),
    Field("savings", "Savings", "cat"),
    Field("employment", "Years in current job", "cat"),
    Field("age", "Age", "num", "years"),
    Field("housing", "Housing", "cat"),
    Field("job", "Job", "cat"),
    Field("property", "Most valuable property", "cat"),
    Field("existing_credits", "Existing credits at this bank", "num"),
]
_CHECKING = {"<0": "overdrawn", "0<=X<200": "under 200 DM", ">=200": "200 DM or more", "no checking": "no checking account"}
_SAVINGS = {"<100": "under 100 DM", "100<=X<500": "100–500 DM", "500<=X<1000": "500–1,000 DM", ">=1000": "1,000 DM or more",
            "no known savings": "none known"}  # fmt: skip
_EMPLOYMENT = {"unemployed": "unemployed", "<1": "under 1 year", "1<=X<4": "1–4 years", "4<=X<7": "4–7 years", ">=7": "7 years or more"}
_HISTORY = {"critical/other existing credit": "critical account or credits elsewhere", "existing paid": "existing credits paid on time",
            "delayed previously": "payments delayed in the past", "no credits/all paid": "no credits taken, or all paid back",
            "all paid": "all credits at this bank paid back"}  # fmt: skip
_JOB = {"unemp/unskilled non res": "unemployed or unskilled (non-resident)", "unskilled resident": "unskilled",
        "skilled": "skilled employee", "high qualif/self emp/mgmt": "highly qualified, self-employed or manager"}  # fmt: skip
_PROPERTY = {"real estate": "real estate", "life insurance": "building society savings or life insurance", "car": "car or other",
             "no known property": "none known"}  # fmt: skip
_HOUSING = {"own": "owns", "rent": "rents", "for free": "lives for free"}


def _loan(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "checking": df["checking_status"].astype(str).map(_CHECKING),
        "duration": df["duration"].astype(int),
        "amount": df["credit_amount"].astype(float).round().astype(int),
        "purpose": df["purpose"].astype(str).str.replace("/", " or ", regex=False),
        "history": df["credit_history"].astype(str).map(_HISTORY),
        "savings": df["savings_status"].astype(str).map(_SAVINGS),
        "employment": df["employment"].astype(str).map(_EMPLOYMENT),
        "age": df["age"].astype(int),
        "housing": df["housing"].astype(str).map(_HOUSING),
        "job": df["job"].astype(str).map(_JOB),
        "property": df["property_magnitude"].astype(str).map(_PROPERTY),
        "existing_credits": df["existing_credits"].astype(int),
        "sex": df["personal_status"].astype(str).str.split().str[0],
        "outcome": (df["class"].astype(str) == "good").astype(int),  # 1 = approve was right
    })  # fmt: skip


# ---------- marketing call: bank marketing (OpenML names the columns V1..V16) ----------
MARKETING_FIELDS = [
    Field("age", "Age", "num", "years"),
    Field("job", "Job", "cat"),
    Field("marital", "Marital status", "cat"),
    Field("education", "Education", "cat"),
    Field("default", "Credit in default", "cat"),
    Field("balance", "Average yearly balance", "num", "EUR"),
    Field("housing", "Housing loan", "cat"),
    Field("loan", "Personal loan", "cat"),
    Field("campaign", "Contacts in this campaign so far", "num"),
    Field("previous", "Contacts in earlier campaigns", "num"),
    Field("poutcome", "Earlier campaign result", "cat"),
]
_POUTCOME = {"unknown": "not contacted before", "failure": "did not subscribe", "other": "other", "success": "subscribed"}


def _marketing(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "age": df["V1"].astype(int),
        "job": df["V2"].astype(str).str.replace("-", " ", regex=False).str.replace(".", "", regex=False),
        "marital": df["V3"].astype(str),
        "education": df["V4"].astype(str),
        "default": df["V5"].astype(str),
        "balance": df["V6"].astype(float).round().astype(int),
        "housing": df["V7"].astype(str),
        "loan": df["V8"].astype(str),
        "campaign": (df["V13"].astype(int) - 1).clip(lower=0),  # contacts before the call being decided
        "previous": df["V15"].astype(int),
        "poutcome": df["V16"].astype(str).map(_POUTCOME),
        "outcome": (df["Class"].astype(str) == "2").astype(int),  # 1 = calling was right
    })  # fmt: skip


# ---------- credit-limit review: default of credit card clients (OpenML x1..x23) ----------
CREDIT_FIELDS = [
    Field("limit", "Credit limit", "num", "NT$", log=True),
    Field("age", "Age", "num", "years"),
    Field("education", "Education", "cat"),
    Field("marriage", "Marital status", "cat"),
    Field("status_sep", "Repayment in September", "cat"),
    Field("status_aug", "Repayment in August", "cat"),
    Field("status_jul", "Repayment in July", "cat"),
    Field("bill_sep", "Bill in September", "num", "NT$"),
    Field("paid_sep", "Paid in September", "num", "NT$"),
    Field("paid_aug", "Paid in August", "num", "NT$"),
]
_EDU = {1: "graduate school", 2: "university", 3: "high school"}
_MAR = {1: "married", 2: "single"}


def _status(v: float) -> str:
    k = int(v)
    if k <= -2:
        return "no balance to pay"
    if k == -1:
        return "paid in full"
    if k == 0:
        return "paid the minimum"
    return f"{k} month{'s' if k > 1 else ''} late"


def _credit(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "limit": df["x1"].astype(float).round().astype(int),
        "age": df["x5"].astype(int),
        "education": df["x3"].astype(int).map(_EDU).fillna("other or unknown"),
        "marriage": df["x4"].astype(int).map(_MAR).fillna("other or unknown"),
        "status_sep": df["x6"].map(_status),
        "status_aug": df["x7"].map(_status),
        "status_jul": df["x8"].map(_status),
        "bill_sep": df["x12"].astype(float).round().astype(int),
        "paid_sep": df["x18"].astype(float).round().astype(int),
        "paid_aug": df["x19"].astype(float).round().astype(int),
        "sex": df["x2"].astype(int).map({1: "male", 2: "female"}),
        "outcome": (df["y"].astype(int) == 1).astype(int),  # 1 = reducing was right
    })  # fmt: skip


DOMAINS: dict[str, tuple[str, list[Field], Any]] = {
    "loan": ("credit-g", LOAN_FIELDS, _loan),
    "marketing": ("bank-marketing", MARKETING_FIELDS, _marketing),
    "credit_limit": ("credit-default", CREDIT_FIELDS, _credit),
}


def fields(domain: str) -> list[Field]:
    return DOMAINS[domain][1]


def load(domain: str, raw: Path = RAW) -> pd.DataFrame:
    """One row per record with its display fields, the outcome and (where audited) sex; indexed by source row."""
    dataset, flds, build = DOMAINS[domain]
    df = build(pd.read_parquet(raw / f"{dataset}.parquet"))
    missing = [f.column for f in flds if df[f.column].isna().any()]
    if missing:
        raise ValueError(f"{domain}: unmapped values in {missing}")
    df.index = pd.RangeIndex(len(df), name="row")
    return df


def fmt(f: Field, v: Any) -> str:
    """A field value as the participant reads it."""
    if f.kind == "num":
        n = int(v) if float(v).is_integer() else float(v)
        s = f"{n:,}".replace("-", "−")
        return f"{s} {f.unit}".strip()
    return str(v)


def card(domain: str, row: pd.Series) -> list[dict[str, str]]:
    return [{"field": f.column, "label": f.label, "value": fmt(f, row[f.column])} for f in fields(domain)]

