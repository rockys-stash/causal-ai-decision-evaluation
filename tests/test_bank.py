from __future__ import annotations

import json
from collections import Counter
from typing import Any

from declab.config import domains
from declab.paths import BANK


def test_bank_is_balanced(bank: dict[str, Any]) -> None:
    per = Counter((c["domain"], c["outcome"]) for c in bank["cases"])
    assert set(per.values()) == {20} and len(per) == 6
    assert len({c["id"] for c in bank["cases"]}) == 120
    assert len(bank["practice"]) == 6


def test_ai_fields_are_consistent(bank: dict[str, Any]) -> None:
    for c in bank["cases"]:
        dc = domains()[c["domain"]]
        ai = c["ai"]
        assert 0 < ai["p_positive"] < 1
        assert ai["decision"] == (dc["positive"] if ai["p_positive"] >= 0.5 else dc["negative"])["decision"]
        assert abs(ai["confidence"] - max(ai["p_positive"], 1 - ai["p_positive"])) < 1e-6
        ex = ai["explanation"]
        assert len(ex["towards_positive"]) <= 3 and len(ex["towards_negative"]) <= 3
        assert all(f["weight"] > 0 for f in ex["towards_positive"]) and all(
            f["weight"] < 0 for f in ex["towards_negative"]
        )


def test_the_sensitive_attribute_is_never_shown(bank: dict[str, Any]) -> None:
    for c in bank["cases"]:
        if c["domain"] == "credit_limit":
            assert not any(f["field"] == "sex" or "sex" in f["label"].lower() for f in c["card"])
            assert c["subgroup"] in ("female", "male")


def test_ai_report_matches_the_bank(bank: dict[str, Any]) -> None:
    rep = json.loads((BANK / "ai_report.json").read_text())
    for d, r in rep.items():
        cs = [c for c in bank["cases"] if c["domain"] == d]
        right = [
            c["ai"]["decision"] == (domains()[d]["positive"] if c["outcome"] else domains()[d]["negative"])["decision"]
            for c in cs
        ]
        assert abs(sum(right) / len(cs) - r["bank"]["ai_accuracy"]) < 1e-9
