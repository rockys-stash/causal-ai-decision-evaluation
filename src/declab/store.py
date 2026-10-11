"""Append-only, hash-chained event log (SQLite). Nothing is updated in place.

Every event stores the SHA-256 of the previous event and of its own canonical JSON, so any edit,
deletion or reordering breaks the chain (``verify``). Sessions are reconstructed from their events.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(prev: str, event: dict[str, Any]) -> str:
    body = {k: event[k] for k in ("seq", "ts", "session", "kind", "data")}
    return hashlib.sha256((prev + canonical(body)).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


class Store:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, ts TEXT NOT NULL, session TEXT NOT NULL,"
            " kind TEXT NOT NULL, data TEXT NOT NULL, prev TEXT NOT NULL, hash TEXT NOT NULL)"
        )
        self._con.execute("CREATE INDEX IF NOT EXISTS ev_session ON events(session)")

    def append(self, session: str, kind: str, data: dict[str, Any], ts: str | None = None) -> dict[str, Any]:
        with self._lock:
            self._con.execute("BEGIN IMMEDIATE")
            try:
                row = self._con.execute("SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
                seq, prev = (row[0] + 1, row[1]) if row else (1, GENESIS)
                ev = {"seq": seq, "ts": ts or now(), "session": session, "kind": kind, "data": data, "prev": prev}
                ev["hash"] = digest(prev, ev)
                self._con.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (seq, ev["ts"], session, kind, canonical(data), prev, ev["hash"]))  # fmt: skip
                self._con.execute("COMMIT")
            except BaseException:
                self._con.execute("ROLLBACK")
                raise
        return ev

    def _rows(self, sql: str, args: Iterable[Any] = ()) -> Iterator[dict[str, Any]]:
        with self._lock:
            rows = self._con.execute(sql, tuple(args)).fetchall()
        for seq, ts, session, kind, data, prev, h in rows:
            yield {"seq": seq, "ts": ts, "session": session, "kind": kind, "data": json.loads(data), "prev": prev, "hash": h}

    def events(self, session: str | None = None) -> list[dict[str, Any]]:
        if session is None:
            return list(self._rows("SELECT * FROM events ORDER BY seq"))
        return list(self._rows("SELECT * FROM events WHERE session = ? ORDER BY seq", (session,)))

    def sessions_of_kind(self, kind: str) -> list[str]:
        out = [e["session"] for e in self._rows("SELECT * FROM events WHERE kind = 'session_created' ORDER BY seq")
               if e["data"]["participant_kind"] == kind]  # fmt: skip
        return out


def verify(events: list[dict[str, Any]]) -> tuple[bool, str]:
    """Check a full log (in order, starting at the first event): links and hashes."""
    prev = GENESIS
    for i, ev in enumerate(events):
        if ev["seq"] != i + 1:
            return False, f"event {i + 1}: sequence gap (found {ev['seq']})"
        if ev["prev"] != prev:
            return False, f"event {ev['seq']}: link to previous event broken"
        if digest(prev, ev) != ev["hash"]:
            return False, f"event {ev['seq']}: content does not match its hash"
        prev = ev["hash"]
    return True, f"{len(events)} events, chain intact"


def export(events: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(canonical(ev) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
