"""Participants that take sessions through the platform's HTTP API: simulated, and the session loop.

The simulated participant is a stated behaviour model (``configs/simulation.yaml``); it reads the
true outcome to generate a noisy judgement, which a person could not, and is used only to check the
platform and the analysis. Model participants (local language models) are in ``llm.py`` and use
the same loop.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any, Protocol

import numpy as np
import yaml

from declab.paths import CONFIGS


class Client(Protocol):
    def get(self, url: str, **kw: Any) -> Any: ...
    def post(self, url: str, **kw: Any) -> Any: ...


Chooser = Callable[[dict[str, Any], str], tuple[str | None, int | None, int | None]]


def sim_config() -> dict[str, Any]:
    return dict(yaml.safe_load((CONFIGS / "simulation.yaml").read_text(encoding="utf-8")))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def behave(p: dict[str, Any], arm: str, right_positive: bool, ai_p: float, ai_shown: bool,
           rng: np.random.Generator) -> tuple[bool, int, float]:  # fmt: skip
    """One simulated decision: (chooses positive, confidence 50–100, seconds)."""
    ai_logit = math.log(ai_p / (1 - ai_p))
    own = p["skill"] * (1 if right_positive else -1) + p["shared"] * ai_logit + rng.normal(0, p["noise"])
    belief = _sigmoid(own)
    choice = belief >= 0.5
    ai_pos = ai_p >= 0.5
    if ai_shown and choice != ai_pos:
        conf_ai = max(ai_p, 1 - ai_p)
        switch = p["switch_b"] if arm == "B" else _sigmoid(p["c0"] + p["c1"] * (conf_ai - 0.5))
        if rng.random() < switch:
            choice, belief = ai_pos, ai_p  # adopts the AI's view of the case
    strength = abs(2 * belief - 1)
    conf = int(np.clip(round(50 + 50 * strength + rng.normal(0, p["confidence_noise"])), 50, 100))
    secs = float(p["seconds_median"][arm] * math.exp(rng.normal(0, p["seconds_sigma"])))
    return choice, conf, secs


def simulated_chooser(design: str, cases: dict[str, Any], rng: np.random.Generator) -> Chooser:
    p = sim_config()["designs"][design]

    def choose(item: dict[str, Any], arm: str) -> tuple[str | None, int | None, int | None]:
        case = cases[item["case_id"]]
        pos, neg = item["options"][0]["decision"], item["options"][1]["decision"]
        choice, conf, secs = behave(p, arm, bool(case["outcome"]), case["ai"]["p_positive"], item["ai"] is not None, rng)
        return (pos if choice else neg), conf, int(secs * 1000)

    return choose


def run_session(client: Client, chooser: Chooser, kind: str, headers: dict[str, str] | None = None,
                model: str | None = None, label: str | None = None, session: str | None = None) -> str:  # fmt: skip
    """Take (or resume) one session to completion; returns its id."""
    h = headers or {}
    if session is None:
        r = client.post("/api/sessions", json={"consent": True, "kind": kind, "model": model, "label": label}, headers=h)
        r.raise_for_status()
        session = str(r.json()["session"])
    while True:
        r = client.get(f"/api/sessions/{session}/next", headers=h)
        r.raise_for_status()
        nxt = r.json()
        if nxt["done"]:
            if not nxt["completed"]:
                client.post(f"/api/sessions/{session}/survey", json={}, headers=h).raise_for_status()
            return session
        item = nxt["item"]
        decision, conf, client_ms = chooser(item, nxt["arm"])
        r = client.post(f"/api/sessions/{session}/decisions", headers=h,
                        json={"index": item["index"], "decision": decision, "confidence": conf, "client_ms": client_ms})  # fmt: skip
        r.raise_for_status()
