"""Capture screenshots of the researcher console and the participant study.

Usage: uv run python scripts/screenshots.py [--out docs/screenshots] [--results results]
Needs the built interface (npm --prefix web run build), Chromium for Playwright and an analysis
result. Participant screens are taken in a throwaway event store, so no session is recorded.
"""

from __future__ import annotations

import argparse
import socket
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

import uvicorn
from playwright.sync_api import ViewportSize, sync_playwright

from declab.api import create_app
from declab.store import Store

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS: dict[str, ViewportSize] = {
    "desktop": {"width": 1440, "height": 900},
    "mobile": {"width": 390, "height": 844},
}
CONSOLE = [
    ("overview", "/lab/overview"),
    ("results", "/lab/results"),
    ("reliance", "/lab/reliance"),
    ("sessions", "/lab/sessions"),
    ("design", "/lab/design"),
    ("method", "/lab/method"),
]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _settle(page: Any) -> None:
    page.locator("h1").first.wait_for(timeout=30000)
    page.wait_for_load_state("networkidle")
    if page.locator(".skeleton").count():
        page.locator(".skeleton").first.wait_for(state="detached", timeout=30000)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "screenshots")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp())
    app = create_app(store=Store(tmp / "lab.db"), results=args.results, rate_limit=False)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    args.out.mkdir(parents=True, exist_ok=True)

    def shot(page: Any, name: str, vp: str, scheme: str) -> None:
        out = args.out / f"{name}-{vp}{'-dark' if scheme == 'dark' else ''}.png"
        page.screenshot(path=str(out), full_page=vp == "desktop")
        print(out)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for vp, size in VIEWPORTS.items():
            for scheme in ("light", "dark"):
                if vp == "mobile" and scheme == "dark":
                    continue
                ctx = browser.new_context(viewport=size, color_scheme=scheme, device_scale_factor=1)
                page = ctx.new_page()
                for name, path in CONSOLE:
                    page.goto(base + path)
                    _settle(page)
                    shot(page, name, vp, scheme)
                page.goto(base + "/lab/sessions")
                _settle(page)
                page.locator("table a.mono").first.click()
                page.get_by_text("What happened").wait_for()
                page.get_by_role("button", name="Decision 4,", exact=False).click()
                shot(page, "replay", vp, scheme)
                ctx.close()
                # Participant screens: new sessions in the throwaway store until one is in arm C.
                for _ in range(6):
                    ctx = browser.new_context(viewport=size, color_scheme=scheme, device_scale_factor=1)
                    page = ctx.new_page()
                    page.goto(base + "/study")
                    _settle(page)
                    page.get_by_label("I have read this and agree to take part.").check()
                    page.get_by_role("button", name="Start the study").click()
                    page.locator("h1.question").wait_for()
                    if page.get_by_text("Pointing to", exact=False).count():
                        break
                    ctx.close()
                page.goto(base + "/study")
                _settle(page)
                shot(page, "study-welcome", vp, scheme)
                page.goto(base + "/study/task")
                page.locator("h1.question").wait_for()
                page.locator(".choice input").first.check()
                page.locator("#conf").fill("75")
                shot(page, "study-task", vp, scheme)
                ctx.close()
        browser.close()
    server.should_exit = True


if __name__ == "__main__":
    main()
