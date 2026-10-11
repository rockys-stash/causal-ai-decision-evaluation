from __future__ import annotations

import itertools
import json
from pathlib import Path

from declab.store import GENESIS, Store, export, read_jsonl, verify


def _filled(tmp_path: Path) -> Store:
    s = Store(tmp_path / "e.db")
    for i in range(5):
        s.append(f"s{i % 2}", "decision", {"index": i, "decision": "approve"})
    return s


def test_chain_links_and_verifies(tmp_path: Path) -> None:
    evs = _filled(tmp_path).events()
    assert [e["seq"] for e in evs] == [1, 2, 3, 4, 5]
    assert evs[0]["prev"] == GENESIS
    assert all(b["prev"] == a["hash"] for a, b in itertools.pairwise(evs))
    assert verify(evs) == (True, "5 events, chain intact")


def test_edit_is_detected(tmp_path: Path) -> None:
    evs = _filled(tmp_path).events()
    evs[2]["data"]["decision"] = "decline"
    ok, msg = verify(evs)
    assert not ok and "event 3" in msg and "hash" in msg


def test_deletion_and_reordering_are_detected(tmp_path: Path) -> None:
    evs = _filled(tmp_path).events()
    assert not verify(evs[:2] + evs[3:])[0]
    assert not verify([evs[1], evs[0], *evs[2:]])[0]


def test_rehashing_one_event_still_breaks_the_next_link(tmp_path: Path) -> None:
    from declab.store import digest

    evs = _filled(tmp_path).events()
    evs[1]["data"]["decision"] = "decline"
    evs[1]["hash"] = digest(evs[1]["prev"], evs[1])
    ok, msg = verify(evs)
    assert not ok and "event 3" in msg


def test_sessions_filter_and_export_roundtrip(tmp_path: Path) -> None:
    s = _filled(tmp_path)
    assert [e["data"]["index"] for e in s.events("s1")] == [1, 3]
    export(s.events(), tmp_path / "out" / "log.jsonl")
    back = read_jsonl(tmp_path / "out" / "log.jsonl")
    assert back == s.events() and verify(back)[0]
    assert json.loads((tmp_path / "out" / "log.jsonl").read_text().splitlines()[0])["seq"] == 1


def test_store_persists_across_connections(tmp_path: Path) -> None:
    _filled(tmp_path)
    again = Store(tmp_path / "e.db")
    again.append("s9", "x", {})
    assert verify(again.events())[0] and len(again.events()) == 6
