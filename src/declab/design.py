"""Randomization: concealed blocked allocation per stratum, and each participant's cases and order.

Everything is derived from the study seed and the stratum name, so the allocation list exists
before the first session and can be regenerated and checked afterwards; its hash is logged with
every assignment. Participants never see it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

from declab.config import study

ARMS = ("A", "B", "C")


def _rng(*parts: object) -> np.random.Generator:
    h = hashlib.sha256(json.dumps([study()["seed"], *parts]).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "big"))


def allocation(stratum: str, n: int = 600) -> list[str]:
    """Blocked list: every block of ``block_size`` holds each arm equally often, in random order."""
    size = int(study()["block_size"])
    rng = _rng("allocation", stratum)
    out: list[str] = []
    while len(out) < n:
        block = [a for a in ARMS for _ in range(size // len(ARMS))]
        rng.shuffle(block)
        out += block
    return out[:n]


def allocation_hash(stratum: str) -> str:
    return hashlib.sha256(",".join(allocation(stratum)).encode()).hexdigest()


def plan(bank: dict[str, Any], stratum: str, slot: int, attention: bool) -> list[dict[str, Any]]:
    """The ordered items of one participant: practice, then 24 cases (with attention checks for humans)."""
    cfg = study()
    rng = _rng("cases", stratum, slot)
    per_domain = int(cfg["cases_per_participant"]) // len(cfg["domains"])
    chosen: list[str] = []
    for d in cfg["domains"]:
        for outcome in (1, 0):
            pool = sorted(c["id"] for c in bank["cases"] if c["domain"] == d and c["outcome"] == outcome)
            chosen += list(rng.choice(pool, size=per_domain // 2, replace=False))
    rng.shuffle(chosen)
    practice = [c["id"] for c in bank["practice"]]
    rng.shuffle(practice)
    items: list[dict[str, Any]] = [{"phase": "practice", "case": c} for c in practice[: int(cfg["practice_cases"])]]
    tasks = [{"phase": "task", "case": c} for c in chosen]
    if attention:
        n = int(cfg["attention_checks"])
        positions = sorted(int(p) for p in rng.choice(np.arange(4, len(tasks) - 2), size=n, replace=False))
        for j, pos in enumerate(reversed(positions)):
            tasks.insert(pos, {"phase": "attention", "case": f"attention-{n - j}"})
    return items + tasks


def stratum_name(kind: str, model: str | None) -> str:
    return f"model:{model}" if kind == "model" else kind
