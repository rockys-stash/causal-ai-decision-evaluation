from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from declab.api import create_app
from declab.store import Store, verify


def _human(client: TestClient) -> str:
    r = client.post("/api/sessions", json={"consent": True})
    assert r.status_code == 200
    return str(r.json()["session"])


def _answer_all(client: TestClient, sid: str, pick: int = 0) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []
    while True:
        n = client.get(f"/api/sessions/{sid}/next").json()
        if n["done"]:
            return seen
        it = n["item"]
        seen.append(it)
        r = client.post(f"/api/sessions/{sid}/decisions",
                        json={"index": it["index"], "decision": it["options"][pick]["decision"], "confidence": 70, "client_ms": 1200})  # fmt: skip
        assert r.status_code == 200, r.text


def test_consent_is_required(client: TestClient) -> None:
    assert client.post("/api/sessions", json={"consent": False}).status_code == 400


def test_full_human_session_is_logged_and_chained(client: TestClient, store: Store) -> None:
    sid = _human(client)
    items = _answer_all(client, sid)
    assert len(items) == 28 and sum(i["phase"] == "attention" for i in items) == 2
    assert (
        client.post(f"/api/sessions/{sid}/survey", json={"trust": 5, "usefulness": 4}).json()["code"] == sid[:8].upper()
    )
    final = client.get(f"/api/sessions/{sid}/next").json()
    assert final["done"] and final["completed"]
    kinds = [e["kind"] for e in store.events(sid)]
    assert kinds[0] == "session_created" and kinds[-1] == "session_completed"
    assert kinds.count("decision") == kinds.count("timing") == kinds.count("item_shown") == 28
    assert verify(store.events())[0]


def test_what_each_arm_sees(client: TestClient) -> None:
    seen: dict[str, dict[str, Any]] = {}
    for _ in range(6):
        sid = _human(client)
        n = client.get(f"/api/sessions/{sid}/next").json()
        seen[n["arm"]] = n["item"]
    assert set(seen) == {"A", "B", "C"}
    assert seen["A"]["ai"] is None
    assert set(seen["B"]["ai"]) == {"decision", "label"}
    assert {"confidence", "explanation"} <= set(seen["C"]["ai"])
    # the same fields for every arm
    for it in seen.values():
        assert {"card", "options", "question"} <= set(it)


def test_order_and_validation_are_enforced(client: TestClient) -> None:
    sid = _human(client)
    assert (
        client.post(
            f"/api/sessions/{sid}/decisions", json={"index": 3, "decision": "approve", "confidence": 70}
        ).status_code
        == 409
    )
    it = client.get(f"/api/sessions/{sid}/next").json()["item"]
    bad = client.post(
        f"/api/sessions/{sid}/decisions", json={"index": it["index"], "decision": "maybe", "confidence": 70}
    )
    assert bad.status_code == 400
    assert (
        client.post(f"/api/sessions/{sid}/decisions", json={"index": it["index"], "decision": None}).status_code == 400
    )
    assert (
        client.post(
            f"/api/sessions/{sid}/decisions",
            json={"index": it["index"], "decision": it["options"][0]["decision"], "confidence": 40},
        ).status_code
        == 422
    )
    ok = client.post(
        f"/api/sessions/{sid}/decisions",
        json={"index": it["index"], "decision": it["options"][0]["decision"], "confidence": 60},
    )
    assert ok.status_code == 200
    again = client.post(
        f"/api/sessions/{sid}/decisions",
        json={"index": it["index"], "decision": it["options"][1]["decision"], "confidence": 60},
    )
    assert again.status_code == 409
    assert client.post(f"/api/sessions/{sid}/survey", json={}).status_code == 409


def test_unknown_and_malformed_sessions(client: TestClient) -> None:
    assert client.get("/api/sessions/../../etc/next").status_code == 404
    assert client.get("/api/sessions/" + "0" * 32 + "/next").status_code == 404


def test_model_participants_may_fail_to_answer(client: TestClient) -> None:
    r = client.post("/api/sessions", json={"consent": True, "kind": "model", "model": "qwen3-4b"})
    sid = r.json()["session"]
    it = client.get(f"/api/sessions/{sid}/next").json()["item"]
    assert (
        client.post(f"/api/sessions/{sid}/decisions", json={"index": it["index"], "decision": None}).status_code == 200
    )
    assert client.post("/api/sessions", json={"consent": True, "kind": "model"}).status_code == 400


def test_only_the_researcher_starts_non_human_sessions(store: Store, bank: dict[str, Any], tmp_path: Path) -> None:
    app = create_app(token="s3cret", store=store, bank=bank, results=tmp_path, static_dir=tmp_path, rate_limit=False)
    c = TestClient(app)
    assert c.post("/api/sessions", json={"consent": True, "kind": "simulated"}).status_code == 403
    assert (
        c.post(
            "/api/sessions", json={"consent": True, "kind": "simulated"}, headers={"Authorization": "Bearer s3cret"}
        ).status_code
        == 200
    )
    assert c.post("/api/sessions", json={"consent": True}).status_code == 200  # people need no token
    assert c.get("/api/lab/overview").status_code == 401
    assert c.get("/api/lab/overview", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/api/lab/overview", headers={"Authorization": "Bearer s3cret"}).json()["chain_ok"]


def test_guard_rules_and_headers(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.headers["X-Frame-Options"] == "DENY" and "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"
    assert client.post("/api/lab/overview").status_code == 405
    big = client.post(
        "/api/sessions", content=b"{" + b" " * 20_000 + b"}", headers={"content-type": "application/json"}
    )
    assert big.status_code == 413
    assert client.get("/api/lab/results/../../etc").status_code == 404
    assert client.get("/api/lab/results/overview").status_code == 404  # no analysis yet: pending, not an error


def test_rate_limit(store: Store, bank: dict[str, Any], tmp_path: Path) -> None:
    c = TestClient(create_app(store=store, bank=bank, results=tmp_path, static_dir=tmp_path))
    codes = [c.get("/api/health").status_code for _ in range(80)]
    assert 429 in codes


def test_preview_and_logs(client: TestClient) -> None:
    p = client.get("/api/lab/preview/C/loan-01").json()
    assert p["ai"]["explanation"] and p["case_id"] == "loan-01"
    assert client.get("/api/lab/preview/D/loan-01").status_code == 404
    logs = client.get("/api/lab/logs").json()
    assert {b["batch"] for b in logs} >= {"human", "model-pilot"} and all(b["status"] == "pending" for b in logs)
    assert client.get("/api/lab/logs/nope/sessions").status_code == 404
