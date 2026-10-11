"""Run sessions through the platform: the simulated dry run and the model-participant pilot.

Both use the real API in-process (FastAPI's test client), so every session goes through the same
validation, randomization and logging as a person's. Each batch has its own event store under
``var/`` and is exported, hash chain included, to ``data/sessions/<batch>.jsonl``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from fastapi.testclient import TestClient

from declab import bank as bankmod
from declab import design
from declab.api import create_app
from declab.participants import run_session, sim_config, simulated_chooser
from declab.paths import SESSIONS, VAR
from declab.store import Store, export, verify


def _client(store: Store) -> TestClient:
    return TestClient(create_app(store=store, rate_limit=False))


def simulate(design_name: str, out: Path = SESSIONS, var: Path = VAR, per_arm: int | None = None) -> Path:
    cfg = sim_config()
    n = 3 * int(per_arm or cfg["per_arm"])
    db = var / f"simulated-{design_name}.db"
    db.unlink(missing_ok=True)
    store = Store(db)
    bank = bankmod.read()
    cases = {c["id"]: c for c in bank["cases"] + bank["practice"]}
    client = _client(store)
    for i in range(n):
        rng = np.random.default_rng([20261011, i, 0 if design_name == "planted" else 1])
        run_session(client, simulated_chooser(design_name, cases, rng), "simulated", label=f"{design_name}-{i:03d}")
    evs = store.events()
    ok, msg = verify(evs)
    if not ok:
        raise RuntimeError(msg)
    path = out / f"simulated-{design_name}.jsonl"
    export(evs, path)
    return path


def pilot(models: list[str], out: Path = SESSIONS, var: Path = VAR, per_arm: int | None = None) -> Path:
    """Model-participant pilot; resumable (an interrupted batch continues where it stopped)."""
    from declab.llm import ModelParticipant, config

    n = 3 * int(per_arm or config()["pilot_per_arm"])
    store = Store(var / "model-pilot.db")
    client = _client(store)
    calls_path = out / "model-pilot-calls.jsonl"
    out.mkdir(parents=True, exist_ok=True)
    for name in models:
        mp = ModelParticipant(name)
        st = design.stratum_name("model", name)
        while True:
            created = [e for e in store.events() if e["kind"] == "session_created" and e["data"]["stratum"] == st]
            done = {e["session"] for e in store.events() if e["kind"] == "session_completed"}
            open_ = [e for e in created if e["session"] not in done]
            if open_:
                sid, slot = open_[0]["session"], open_[0]["data"]["slot"]
            elif len(created) < n:
                sid, slot = None, len(created)
            else:
                break
            mp.seed, mp.calls = slot, []
            sid = run_session(client, mp.choose, "model", model=name, label=f"{name}-{slot:02d}", session=sid)
            with calls_path.open("a", encoding="utf-8") as f:
                for c in mp.calls:
                    f.write(json.dumps({"session": sid, "model": name, **c}, ensure_ascii=False) + "\n")
            print(f"{name} slot {slot}: done", flush=True)
            export(store.events(), out / "model-pilot.jsonl")
    evs = store.events()
    ok, msg = verify(evs)
    if not ok:
        raise RuntimeError(msg)
    export(evs, out / "model-pilot.jsonl")
    return out / "model-pilot.jsonl"


def summary(path: Path) -> dict[str, Any]:
    from declab.store import read_jsonl

    evs = read_jsonl(path)
    ok, msg = verify(evs)
    return {"file": path.name, "events": len(evs), "chain": msg, "ok": ok}
