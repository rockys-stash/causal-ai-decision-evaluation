from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from declab import analysis
from declab.participants import behave, run_session, sim_config, simulated_chooser
from declab.store import Store


def test_holm_matches_hand_computation() -> None:
    assert analysis.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert analysis.holm([0.5, 0.6]) == [1.0, 1.0]


def test_permutation_test_separates_effect_from_noise() -> None:
    rng = np.random.default_rng(1)
    strata = np.array(["x"] * 20 + ["y"] * 20)
    is_b = np.tile([True, False], 20)
    same = rng.normal(0, 1, 40)
    shifted = same + np.where(is_b, 2.0, 0.0)
    assert analysis.perm_test(same, is_b, strata, 999, rng) > 0.05
    assert analysis.perm_test(shifted, is_b, strata, 999, rng) < 0.01


def test_permutations_stay_within_strata() -> None:
    rng = np.random.default_rng(0)
    strata = np.array(["x"] * 4 + ["y"] * 6)
    is_b = np.array([1, 1, 0, 0, 1, 0, 0, 0, 0, 0], dtype=bool)
    L = analysis._labels_perm(strata, is_b, rng, 50)
    assert (L[:, :4].sum(axis=1) == 2).all() and (L[:, 4:].sum(axis=1) == 1).all()


def test_bootstrap_interval_covers_the_difference() -> None:
    rng = np.random.default_rng(2)
    a, b = rng.normal(0.6, 0.1, 200), rng.normal(0.7, 0.1, 200)
    lo, hi = analysis.boot_ci(a, b, 2000, rng)
    assert lo < b.mean() - a.mean() < hi and lo > 0


def test_cohens_h() -> None:
    assert analysis.cohens_h(0.5, 0.5) == 0
    assert analysis.cohens_h(0.7, 0.6) == pytest.approx(0.2102, abs=1e-3)


def test_behaviour_model_ignores_the_ai_when_it_is_not_shown() -> None:
    p = sim_config()["designs"]["planted"]
    a1 = [behave(p, "A", True, 0.9, False, np.random.default_rng(k))[0] for k in range(200)]
    a2 = [behave(p, "A", True, 0.9, False, np.random.default_rng(k))[0] for k in range(200)]
    assert a1 == a2
    c = [behave(p, "C", True, 0.95, True, np.random.default_rng(k))[0] for k in range(400)]
    assert np.mean(c) > np.mean(a1)  # a confident correct AI pulls arm C towards the right answer


def _sessions(store: Store, client: TestClient, bank: dict[str, Any], n: int, design: str) -> list[dict[str, Any]]:
    cases = {c["id"]: c for c in bank["cases"] + bank["practice"]}
    for i in range(n):
        run_session(client, simulated_chooser(design, cases, np.random.default_rng(i)), "simulated")
    return store.events()


def test_population_analysis_end_to_end(store: Store, client: TestClient, bank: dict[str, Any]) -> None:
    evs = _sessions(store, client, bank, 12, "planted")
    res = analysis.analyse_population(evs, bank, perms=99, boots=99, seed=0)
    assert res["chain_ok"] and res["participants"] == 12 and res["decisions"] == 12 * 24
    assert {a["arm"] for a in res["arms"]} == {"A", "B", "C"}
    assert [c["contrast"] for c in res["primary"]] == ["C−A", "B−A", "C−B"]
    assert all(c["p_holm"] >= c["p"] for c in res["primary"])
    assert {c["outcome"] for c in res["secondary"]} >= {
        "cost",
        "log_seconds",
        "override",
        "appropriate",
        "brier",
        "gap_loan",
    }
    assert set(res["calibration"]) == {"A", "B", "C"}


def test_tampered_log_is_reported(store: Store, client: TestClient, bank: dict[str, Any]) -> None:
    evs = _sessions(store, client, bank, 3, "no_effect")
    evs[5]["data"]["decision"] = "approve" if evs[5]["data"].get("decision") != "approve" else "decline"
    assert not analysis.analyse_population(evs, bank, 9, 9, 0)["chain_ok"]


def test_exclusions(store: Store, client: TestClient, bank: dict[str, Any]) -> None:
    # A person who fails both attention checks, and one who stops early.
    for answer in ("fail", "stop"):
        sid = client.post("/api/sessions", json={"consent": True}).json()["session"]
        k = 0
        while True:
            n = client.get(f"/api/sessions/{sid}/next").json()
            if n["done"] or (answer == "stop" and k == 10):
                break
            it = n["item"]
            pick = (
                it["options"][0]["decision"]
                if it["phase"] != "attention"
                else ("approve" if it["case_id"] == "attention-1" else "decline")
            )
            client.post(
                f"/api/sessions/{sid}/decisions", json={"index": it["index"], "decision": pick, "confidence": 80}
            )
            k += 1
        if answer == "fail":
            client.post(f"/api/sessions/{sid}/survey", json={})
    S, D = analysis.tables(store.events(), bank)
    assert sorted(S["excluded"]) == ["failed both attention checks", "incomplete"]
    assert D.empty


def test_missing_answers_over_the_limit_exclude_a_model_participant(
    store: Store, client: TestClient, bank: dict[str, Any]
) -> None:
    def chooser(item: dict[str, Any], arm: str) -> tuple[str | None, int | None, int | None]:
        return (None, None, 10) if item["index"] % 3 == 0 else (item["options"][0]["decision"], 70, 10)

    run_session(client, chooser, "model", model="qwen3-4b")
    S, _ = analysis.tables(store.events(), bank)
    assert S["excluded"].tolist() == ["over 20% invalid answers"]


def test_run_writes_a_versioned_result(tmp_path: Path, store: Store, client: TestClient, bank: dict[str, Any]) -> None:
    from declab.store import export

    sessions = tmp_path / "sessions"
    _sessions(store, client, bank, 6, "planted")
    export(store.events(), sessions / "simulated-planted.jsonl")
    out = analysis.run(results=tmp_path / "results", quick=True, sessions=sessions)
    names = {p.name for p in out.iterdir()}
    assert {"overview.json", "primary.json", "power.json", "provenance.json"} <= names
    assert (
        not (tmp_path / "results" / "LATEST").exists()
        or (tmp_path / "results" / "LATEST").read_text().strip() == out.name
    )
