"""HTTP API of the experiment platform: the participant flow and the researcher console.

Participant routes (``/api/sessions``): create a session (consent, randomized arm), get the next
item, submit a decision, submit the closing survey. A session is addressed by its random id, which
only its participant holds. Every step is an event in the hash-chained log; the server, not the
client, stamps the time a case is shown and the time a decision arrives.

Researcher routes (``/api/lab``): study design, assignment balance, sessions and their event logs,
the task bank with outcomes, the analysis results. With ``DECLAB_TOKEN`` set they need
``Authorization: Bearer <token>``; so does creating a session for a non-human participant kind.
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from declab import bank as bankmod
from declab import design
from declab.config import domains, study
from declab.paths import RESULTS, ROOT, SESSIONS, VAR
from declab.store import Store, read_jsonl, verify

_RUN = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-z]{4,40}$")
_SID = re.compile(r"^[0-9a-f]{32}$")
RESULT_TOPICS = (
    "overview",
    "primary",
    "secondary",
    "reliance",
    "calibration",
    "subgroups",
    "power",
    "ai",
    "provenance",
)
KINDS = ("human", "simulated", "model")
LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}
BATCHES = {"model-pilot": "Model participants (pilot)", "simulated-planted": "Simulated, planted effects (dry run)",
           "simulated-no_effect": "Simulated, no effect (dry run)", "human": "Human participants"}  # fmt: skip


def _right(case: dict[str, Any]) -> str:
    d = domains()[case["domain"]]
    return str(d["positive"]["decision"] if case["outcome"] else d["negative"]["decision"])


class RateLimiter:
    """Token bucket per client address."""

    def __init__(self, rate: float, burst: int) -> None:
        self.rate, self.burst = rate, burst
        self._b: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._b.get(key, (float(self.burst), now))
            tokens = min(self.burst, tokens + (now - last) * self.rate)
            ok = tokens >= 1
            self._b[key] = (tokens - 1 if ok else tokens, now)
            if len(self._b) > 10_000:
                self._b = dict(list(self._b.items())[-5_000:])
            return ok


def _bearer(request: Request) -> str:
    return request.headers.get("authorization", "").removeprefix("Bearer ").strip()


class Guard(BaseHTTPMiddleware):
    def __init__(self, app: Any, token: str, limiter: RateLimiter | None) -> None:
        super().__init__(app)
        self.token, self.limiter = token, limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path.startswith("/api"):
            client = request.client.host if request.client else "unknown"
            if self.limiter and not self.limiter.allow(client):
                return JSONResponse({"detail": "rate limit exceeded"}, status_code=429, headers={"Retry-After": "1"})
            if request.method not in ("GET", "HEAD") and not path.startswith("/api/sessions"):
                return JSONResponse({"detail": "method not allowed"}, status_code=405)
            if int(request.headers.get("content-length") or 0) > 16_384:
                return JSONResponse({"detail": "request too large"}, status_code=413)
            if (
                path.startswith("/api/lab")
                and self.token
                and not hmac.compare_digest(_bearer(request).encode(), self.token.encode())
            ):
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = (
            "no-store" if path.startswith("/api") else response.headers.get("Cache-Control", "")
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response


class NewSession(BaseModel):
    consent: bool
    kind: Literal["human", "simulated", "model"] = "human"
    model: str | None = Field(default=None, max_length=40, pattern=r"^[a-z0-9.\-]+$")
    label: str | None = Field(default=None, max_length=60)


class Decision(BaseModel):
    index: int = Field(ge=0, le=100)
    decision: str | None = Field(default=None, max_length=20)  # None: no valid answer (model participants only)
    confidence: int | None = Field(default=None, ge=50, le=100)
    client_ms: int | None = Field(default=None, ge=0, le=86_400_000)


class Survey(BaseModel):
    trust: int | None = Field(default=None, ge=1, le=7)
    usefulness: int | None = Field(default=None, ge=1, le=7)
    comment: str = Field(default="", max_length=1000)


def _attention(n: str) -> dict[str, Any]:
    """An attention check: an instruction in place of a case, with one right answer."""
    loan = domains()["loan"]
    want = loan["negative"] if n.endswith("1") else loan["positive"]
    return {"domain": "loan", "id": n, "attention": True, "want": want["decision"],
            "card": [{"field": "note", "label": "Attention check",
                      "value": f"This is not a real case. Please choose “{want['label']}” and set confidence to 100%."}]}  # fmt: skip


class Lab:
    """Session state, rebuilt from the event log."""

    def __init__(self, store: Store, bank: dict[str, Any]) -> None:
        self.store, self.bank = store, bank
        self.cases = {c["id"]: c for c in bank["cases"] + bank["practice"]}
        self._lock = threading.Lock()

    def create(self, body: NewSession) -> dict[str, Any]:
        st = design.stratum_name(body.kind, body.model)
        with self._lock:
            slot = sum(1 for e in self.store.events() if e["kind"] == "session_created" and e["data"]["stratum"] == st)
            arm = design.allocation(st)[slot]
            items = design.plan(self.bank, st, slot, attention=body.kind == "human")
            sid = secrets.token_hex(16)
            self.store.append(sid, "session_created", {
                "participant_kind": body.kind, "model": body.model, "label": body.label, "stratum": st, "slot": slot,
                "arm": arm, "allocation_sha256": design.allocation_hash(st), "items": items,
                "consent": True, "study_seed": study()["seed"],
            })  # fmt: skip
        return {"session": sid, "arm": arm, "items": len(items)}

    def state(self, sid: str) -> dict[str, Any]:
        evs = self.store.events(sid)
        if not evs or evs[0]["kind"] != "session_created":
            raise HTTPException(404, "no such session")
        s = dict(evs[0]["data"])
        s["shown"] = {e["data"]["index"]: e["ts"] for e in evs if e["kind"] == "item_shown"}
        s["decided"] = {e["data"]["index"] for e in evs if e["kind"] == "decision"}
        s["completed"] = any(e["kind"] == "session_completed" for e in evs)
        return s

    def item(self, s: dict[str, Any], i: int) -> dict[str, Any]:
        it = s["items"][i]
        case = _attention(it["case"]) if it["phase"] == "attention" else self.cases[it["case"]]
        dc = domains()[case["domain"]]
        out: dict[str, Any] = {
            "index": i, "total": len(s["items"]), "phase": it["phase"], "case_id": case["id"], "domain": case["domain"],
            "domain_label": dc["label"], "question": dc["question"], "card": case["card"],
            "options": [{"decision": dc["positive"]["decision"], "label": dc["positive"]["label"]},
                        {"decision": dc["negative"]["decision"], "label": dc["negative"]["label"]}],
            "ai": None,
        }  # fmt: skip
        if it["phase"] != "attention" and s["arm"] in ("B", "C"):
            a = case["ai"]
            out["ai"] = {"decision": a["decision"], "label": a["label"]}
            if s["arm"] == "C":
                out["ai"] |= {"confidence": a["confidence"], "explanation": a["explanation"]}
        return out


def create_app(token: str = "", store: Store | None = None, bank: dict[str, Any] | None = None,
               results: Path | None = None, static_dir: Path | None = None, rate_limit: bool = True,
               sessions: Path | None = None) -> FastAPI:  # fmt: skip
    st = store or Store(VAR / "lab.db")
    sessions_dir = (sessions or SESSIONS).resolve()
    log_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
    lab = Lab(st, bank or bankmod.read())
    res = (results or RESULTS).resolve()
    static = (static_dir or ROOT / "web" / "dist").resolve()
    app = FastAPI(title="declab", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(Guard, token=token, limiter=RateLimiter(rate=20.0, burst=60) if rate_limit else None)
    app.state.lab = lab

    def sess(sid: str) -> dict[str, Any]:
        if not _SID.match(sid):
            raise HTTPException(404, "no such session")
        return lab.state(sid)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/study")
    def public_study() -> dict[str, Any]:
        cfg = study()
        return {"arms": {k: v["label"] for k, v in cfg["arms"].items()}, "cases": cfg["cases_per_participant"],
                "practice": cfg["practice_cases"], "domains": {k: {"label": v["label"], "question": v["question"]}
                                                                for k, v in cfg["domains"].items()}}  # fmt: skip

    @app.post("/api/sessions")
    def new_session(body: NewSession, request: Request) -> dict[str, Any]:
        if not body.consent:
            raise HTTPException(400, "consent is required to take part")
        if body.kind != "human":
            client = request.client.host if request.client else ""
            allowed = hmac.compare_digest(_bearer(request).encode(), token.encode()) if token else client in LOOPBACK
            if not allowed:
                raise HTTPException(403, "only the researcher can start simulated or model sessions")
            if body.kind == "model" and not body.model:
                raise HTTPException(400, "model sessions name their model")
        return lab.create(body)

    @app.get("/api/sessions/{sid}/next")
    def next_item(sid: str) -> dict[str, Any]:
        s = sess(sid)
        pending = [i for i in range(len(s["items"])) if i not in s["decided"]]
        if not pending:
            return {"done": True, "completed": s["completed"], "arm": s["arm"]}
        i = pending[0]
        if i not in s["shown"]:
            it = s["items"][i]
            st.append(sid, "item_shown", {"index": i, "phase": it["phase"], "case": it["case"]})
        return {"done": False, "arm": s["arm"], "item": lab.item(s, i)}

    @app.post("/api/sessions/{sid}/decisions")
    def decide(sid: str, body: Decision) -> dict[str, Any]:
        s = sess(sid)
        if s["completed"]:
            raise HTTPException(409, "session already completed")
        if body.index in s["decided"] or body.index not in s["shown"]:
            raise HTTPException(409, "this item is not awaiting a decision")
        item = lab.item(s, body.index)
        if body.decision is None:
            if s["participant_kind"] != "model":
                raise HTTPException(400, "a decision is required")
        elif body.decision not in {o["decision"] for o in item["options"]} or body.confidence is None:
            raise HTTPException(400, "choose one of the options and give a confidence")
        shown = datetime.fromisoformat(s["shown"][body.index])
        ev = st.append(sid, "decision", {"index": body.index, "phase": item["phase"], "case": item["case_id"],
                                         "decision": body.decision, "confidence": body.confidence,
                                         "client_ms": body.client_ms, "ai_decision": (item["ai"] or {}).get("decision")})  # fmt: skip
        seconds = (datetime.fromisoformat(ev["ts"]) - shown).total_seconds()
        st.append(sid, "timing", {"index": body.index, "server_seconds": round(seconds, 3)})
        return {"recorded": True, "remaining": len(s["items"]) - len(s["decided"]) - 1}

    @app.post("/api/sessions/{sid}/survey")
    def survey(sid: str, body: Survey) -> dict[str, Any]:
        s = sess(sid)
        if len(s["decided"]) < len(s["items"]):
            raise HTTPException(409, "finish the decisions first")
        if s["completed"]:
            raise HTTPException(409, "session already completed")
        st.append(sid, "survey", body.model_dump())
        st.append(sid, "session_completed", {"decisions": len(s["decided"])})
        return {"completed": True, "code": sid[:8].upper()}

    # ---------- researcher console ----------
    @app.get("/api/lab/overview")
    def lab_overview() -> dict[str, Any]:
        evs = st.events()
        created = [e for e in evs if e["kind"] == "session_created"]
        done = {e["session"] for e in evs if e["kind"] == "session_completed"}
        counts: dict[str, dict[str, dict[str, int]]] = {}
        for e in created:
            d = e["data"]
            c = counts.setdefault(d["stratum"], {a: {"started": 0, "completed": 0} for a in design.ARMS})
            c[d["arm"]]["started"] += 1
            c[d["arm"]]["completed"] += e["session"] in done
        ok, msg = verify(evs)
        return {"strata": counts, "events": len(evs), "chain_ok": ok, "chain": msg, "store": Path(st.path).name,
                "allocation_sha256": {s: design.allocation_hash(s) for s in counts}}  # fmt: skip

    @app.get("/api/lab/sessions")
    def lab_sessions() -> list[dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for e in st.events():
            if e["kind"] == "session_created":
                d = e["data"]
                out[e["session"]] = {"session": e["session"], "kind": d["participant_kind"], "model": d["model"], "arm": d["arm"],
                                     "slot": d["slot"], "started": e["ts"], "decisions": 0, "items": len(d["items"]), "completed": False}  # fmt: skip
            elif e["kind"] == "decision" and e["session"] in out:
                out[e["session"]]["decisions"] += 1
            elif e["kind"] == "session_completed" and e["session"] in out:
                out[e["session"]]["completed"] = True
        return list(out.values())

    @app.get("/api/lab/sessions/{sid}/events")
    def lab_events(sid: str) -> list[dict[str, Any]]:
        if not _SID.match(sid):
            raise HTTPException(404, "no such session")
        return st.events(sid)

    @app.get("/api/lab/bank")
    def lab_bank() -> dict[str, Any]:
        return lab.bank

    @app.get("/api/lab/design")
    def lab_design() -> dict[str, Any]:
        return {"study": study(), "allocation_preview": {s: design.allocation(s, 12) for s in ("human", "simulated")}}

    def batch_events(batch: str) -> list[dict[str, Any]]:
        if batch not in BATCHES:
            raise HTTPException(404, "unknown session log")
        f = sessions_dir / f"{batch}.jsonl"
        if not f.is_file():
            raise HTTPException(404, "this session log does not exist yet")
        key = (batch, f.stat().st_mtime_ns)
        if key not in log_cache:
            log_cache.clear()
            log_cache[key] = read_jsonl(f)
        return log_cache[key]

    @app.get("/api/lab/logs")
    def lab_logs() -> list[dict[str, Any]]:
        out = []
        for b, label in BATCHES.items():
            f = sessions_dir / f"{b}.jsonl"
            if not f.is_file():
                out.append({"batch": b, "label": label, "status": "pending", "sessions": 0, "events": 0})
                continue
            evs = batch_events(b)
            ok, msg = verify(evs)
            out.append({"batch": b, "label": label, "status": "logged", "sessions": sum(e["kind"] == "session_created" for e in evs),
                        "completed": sum(e["kind"] == "session_completed" for e in evs), "events": len(evs), "chain_ok": ok, "chain": msg})  # fmt: skip
        return out

    @app.get("/api/lab/logs/{batch}/sessions")
    def lab_log_sessions(batch: str) -> list[dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for e in batch_events(batch):
            if e["kind"] == "session_created":
                d = e["data"]
                out[e["session"]] = {"session": e["session"], "kind": d["participant_kind"], "model": d["model"], "label": d["label"],
                                     "arm": d["arm"], "slot": d["slot"], "started": e["ts"], "decisions": 0, "correct": 0,
                                     "items": len(d["items"]), "completed": False}  # fmt: skip
            elif e["kind"] == "decision" and e["session"] in out:
                r = out[e["session"]]
                r["decisions"] += 1
                c = lab.cases.get(e["data"]["case"])
                if c and e["data"]["phase"] == "task" and e["data"]["decision"] == _right(c):
                    r["correct"] += 1
            elif e["kind"] == "session_completed" and e["session"] in out:
                out[e["session"]]["completed"] = True
        return list(out.values())

    @app.get("/api/lab/logs/{batch}/sessions/{sid}")
    def lab_log_session(batch: str, sid: str) -> dict[str, Any]:
        if not _SID.match(sid):
            raise HTTPException(404, "no such session")
        evs = [e for e in batch_events(batch) if e["session"] == sid]
        if not evs:
            raise HTTPException(404, "no such session")
        created = evs[0]["data"]
        state = {"arm": created["arm"], "items": created["items"]}
        items = [lab.item(state, i) for i in range(len(created["items"]))]
        outcomes = {c["id"]: {"right": _right(c), "ai": c["ai"]["decision"]} for c in lab.cases.values()}
        return {"events": evs, "items": items, "outcomes": {i["case_id"]: outcomes.get(i["case_id"]) for i in items}}

    @app.get("/api/lab/preview/{arm}/{case_id}")
    def lab_preview(arm: str, case_id: str) -> dict[str, Any]:
        if arm not in design.ARMS or case_id not in lab.cases:
            raise HTTPException(404, "unknown arm or case")
        return lab.item({"arm": arm, "items": [{"phase": "task", "case": case_id}]}, 0)

    def run_dir() -> Path:
        m = res / "LATEST"
        if not m.is_file():
            raise HTTPException(404, "no analysis result yet (make analysis)")
        rid = m.read_text(encoding="utf-8").strip()
        if not _RUN.match(rid) or not (res / rid / "provenance.json").is_file():
            raise HTTPException(404, "no analysis result yet (make analysis)")
        return res / rid

    @app.get("/api/lab/results/{topic}")
    def lab_results(topic: str) -> Any:
        if topic not in RESULT_TOPICS:
            raise HTTPException(404, "unknown topic")
        p = run_dir() / f"{topic}.json"
        if not p.is_file():
            raise HTTPException(404, f"{topic} missing from the result")
        return json.loads(p.read_text(encoding="utf-8"))

    @app.get("/api/{rest:path}")
    def api_404(rest: str) -> Response:
        return JSONResponse({"detail": "not found"}, status_code=404)

    @app.get("/{rest:path}")
    def spa(rest: str) -> Response:
        if not static.exists():
            return JSONResponse({"detail": "interface not built (npm --prefix web run build)"}, status_code=404)
        candidate = (static / rest).resolve()
        if rest and candidate.is_file() and candidate.is_relative_to(static):
            return FileResponse(candidate)
        return FileResponse(static / "index.html")

    return app
