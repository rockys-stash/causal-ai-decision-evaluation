from __future__ import annotations

import contextlib
from typing import Any

import numpy as np
from fastapi.testclient import TestClient

from declab import llm
from declab.participants import run_session, simulated_chooser
from declab.store import Store


def _item(client: TestClient, arm: str) -> dict[str, Any]:
    for _ in range(6):
        sid = client.post("/api/sessions", json={"consent": True, "kind": "model", "model": "qwen3-4b"}).json()[
            "session"
        ]
        n = client.get(f"/api/sessions/{sid}/next").json()
        if n["arm"] == arm:
            return dict(n["item"])
    raise AssertionError(arm)


def test_model_prompt_shows_exactly_what_the_arm_shows(client: TestClient) -> None:
    a, b, c = (llm.render(_item(client, x)) for x in "ABC")
    assert "AI recommendation" not in a
    assert "AI recommendation" in b and "confidence" not in b.split("AI recommendation")[1].split("Question")[0].lower()
    assert "AI confidence" in c and "Factors pointing to" in c
    assert "Question:" in a and "Answer as JSON" in a


def test_reply_schema_allows_only_the_options(client: TestClient) -> None:
    it = _item(client, "A")
    s = llm.schema(it)
    assert s["properties"]["decision"]["enum"] == [o["decision"] for o in it["options"]]
    assert s["required"] == ["decision", "confidence"]


def test_models_are_pinned() -> None:
    cfg = llm.config()
    assert set(cfg["models"]) == {"qwen3-4b", "phi-4-mini"}
    assert all(len(m["sha256"]) == 64 for m in cfg["models"].values())


def test_interrupted_session_resumes(client: TestClient, store: Store, bank: dict[str, Any]) -> None:
    cases = {c["id"]: c for c in bank["cases"] + bank["practice"]}
    calls = {"n": 0}
    base = simulated_chooser("planted", cases, np.random.default_rng(0))

    def flaky(item: dict[str, Any], arm: str) -> tuple[str | None, int | None, int | None]:
        calls["n"] += 1
        if calls["n"] == 8:
            raise KeyboardInterrupt
        return base(item, arm)

    with contextlib.suppress(KeyboardInterrupt):
        run_session(client, flaky, "simulated")
    sid = store.events()[0]["session"]
    run_session(client, base, "simulated", session=sid)
    kinds = [e["kind"] for e in store.events(sid)]
    assert kinds.count("decision") == 26 and kinds[-1] == "session_completed"
    assert len({e["data"]["index"] for e in store.events(sid) if e["kind"] == "decision"}) == 26
