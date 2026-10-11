"""Command line: data, task bank, sessions (simulated dry run, model pilot), analysis, report, server."""

from __future__ import annotations

import argparse
import json
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="declab", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("data", help="download the three datasets and check their SHA-256")
    sub.add_parser("bank", help="fit and calibrate the AI per domain and draw the task bank (data/bank/)")
    s = sub.add_parser("simulate", help="simulated dry run through the API (data/sessions/simulated-<design>.jsonl)")
    s.add_argument("design", choices=["planted", "no_effect"])
    m = sub.add_parser("models", help="download the local models and check their SHA-256")
    m.add_argument("--quiet", action="store_true")
    pl = sub.add_parser("pilot", help="model-participant pilot through the API (resumable; hours on CPU)")
    pl.add_argument("--models", default="qwen3-4b,phi-4-mini")
    sub.add_parser("verify", help="check the hash chain of every committed session log")
    a = sub.add_parser("analyse", help="pre-registered analysis of every session log into results/<UTC>-<sha7>")
    a.add_argument("--results", default=None)
    a.add_argument("--quick", action="store_true", help="fewer permutations and repetitions (checks the pipeline; not a result)")
    sub.add_parser("report", help="render docs/generated/results.md from results/LATEST")
    sv = sub.add_parser("serve", help="serve the platform (participant pages, researcher console, API)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8015)
    sv.add_argument("--store", default=None, help="event store (default var/lab.db)")
    args = p.parse_args(argv)

    if args.cmd == "data":
        from declab.data import fetch

        for k, v in fetch().items():
            print(f"{k}: {v}")
    elif args.cmd == "bank":
        from declab.bank import build

        rep = build()
        print(json.dumps({d: v["bank"] for d, v in rep.items()}, indent=1))
    elif args.cmd == "simulate":
        from declab.runs import simulate, summary

        print(summary(simulate(args.design)))
    elif args.cmd == "models":
        from declab.llm import fetch_models

        for path in fetch_models():
            print(path)
    elif args.cmd == "pilot":
        from declab.runs import pilot, summary

        print(summary(pilot(args.models.split(","))))
    elif args.cmd == "verify":
        from declab.paths import SESSIONS
        from declab.runs import summary

        bad = 0
        for f in sorted(SESSIONS.glob("*.jsonl")):
            if f.name.endswith("-calls.jsonl"):
                continue
            r = summary(f)
            bad += not r["ok"]
            print(f"{r['file']}: {r['chain']}")
        return 1 if bad else 0
    elif args.cmd == "analyse":
        from pathlib import Path

        from declab.analysis import run
        from declab.paths import RESULTS

        print(run(Path(args.results) if args.results else RESULTS, quick=args.quick))
    elif args.cmd == "report":
        from declab.report import render

        print(render())
    elif args.cmd == "serve":
        from pathlib import Path

        import uvicorn

        from declab.api import create_app
        from declab.store import Store

        token = os.environ.get("DECLAB_TOKEN", "")
        if args.host not in ("127.0.0.1", "localhost", "::1") and not token:
            raise SystemExit("refusing to bind a non-loopback address without DECLAB_TOKEN")
        store = Store(Path(args.store)) if args.store else None
        uvicorn.run(create_app(token=token, store=store), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
