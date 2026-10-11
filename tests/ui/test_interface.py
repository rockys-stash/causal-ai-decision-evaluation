"""Browser tests for the participant study and the researcher console.

Served from the committed analysis (``results/LATEST``, or ``DECLAB_RESULTS``) and the committed
session logs, with a fresh event store for participant sessions. Run with ``uv run pytest -m ui``
after ``npm --prefix web run build``.
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
AXE = ROOT / "web" / "node_modules" / "axe-core" / "axe.min.js"
pytestmark = [pytest.mark.ui]
playwright_api = pytest.importorskip("playwright.sync_api")

VIEWPORTS = {"desktop": {"width": 1440, "height": 900}, "mobile": {"width": 390, "height": 844}}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    if not (ROOT / "web" / "dist" / "index.html").exists():
        pytest.skip("frontend not built (npm --prefix web run build)")
    results = Path(os.environ.get("DECLAB_RESULTS", ROOT / "results"))
    if not (results / "LATEST").exists():
        pytest.skip("no committed analysis result")
    import uvicorn

    from declab.api import create_app
    from declab.store import Store

    tmp = Path(tempfile.mkdtemp())
    app = create_app(store=Store(tmp / "lab.db"), results=results, rate_limit=False)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{url}/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    yield url
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    with playwright_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


PAGES = [
    ("overview", "/lab/overview", "Session populations"),
    ("results", "/lab/results", "Primary contrasts"),
    ("reliance", "/lab/reliance", "Agreement with the AI"),
    ("sessions", "/lab/sessions", "append-only event log"),
    ("design", "/lab/design", "Pre-registered analysis"),
    ("method", "/lab/method", "Populations"),
    ("study", "/study", "Before you start"),
    ("not-found", "/nowhere", "Page not found"),
]


def _open(browser: Any, base_url: str, viewport: str, path: str, marker: str, scheme: str = "light") -> Any:
    ctx = browser.new_context(viewport=VIEWPORTS[viewport], color_scheme=scheme)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base_url + path)
    page.get_by_text(marker, exact=False).first.wait_for(timeout=30000)
    page.wait_for_load_state("networkidle")
    page.errors = errors
    return page


def _check_page(page: Any) -> None:
    assert page.locator("h1").count() == 1
    assert not page.locator(".skeleton").count(), "loading skeleton still visible"
    assert not page.locator("[role=alert]").count(), "error state rendered"
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 1, f"page scrolls horizontally by {overflow}px"
    assert not page.errors, page.errors


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
@pytest.mark.parametrize(("name", "path", "marker"), PAGES)
def test_page_renders(browser: Any, base_url: str, viewport: str, name: str, path: str, marker: str) -> None:
    page = _open(browser, base_url, viewport, path, marker)
    _check_page(page)
    page.context.close()


def _start(page: Any) -> None:
    start = page.get_by_role("button", name="Start the study")
    assert start.is_disabled(), "the study must not start without consent"
    page.get_by_label("I have read this and agree to take part.").check()
    start.click()
    page.locator("h1.question").wait_for()


def _complete(page: Any) -> dict[str, Any]:
    """Answer every screen (attention checks as instructed); returns what was seen."""
    seen = {"ai": False, "screens": 0}
    while True:
        if page.url.endswith("/study/done"):
            return seen
        page.locator("h1.question").wait_for()
        seen["screens"] += 1
        seen["ai"] = seen["ai"] or page.locator(".ai-panel").count() > 0
        confirm = page.get_by_role("button", name="Confirm and continue")
        assert confirm.is_disabled()
        card = page.locator(".case-fields").inner_text()
        want = "Decline" if "choose “Decline”" in card else "Approve" if "choose “Approve”" in card else None
        if want:
            page.get_by_label(want, exact=True).check()
        else:
            page.locator(".choice input").first.check()
        assert confirm.is_disabled(), "confidence must be set before continuing"
        page.locator("#conf").fill("100" if want else "70")
        before = page.locator("p[aria-live]").inner_text()
        confirm.click()
        page.wait_for_function(
            "b => location.pathname.endsWith('/done') || (document.querySelector('p[aria-live]')?.textContent ?? b) !== b",
            arg=before,
        )


def test_participant_completes_the_study(browser: Any, base_url: str) -> None:
    arms_seen = set()
    for _ in range(4):
        page = _open(browser, base_url, "mobile", "/study", "Before you start")
        _start(page)
        seen = _complete(page)
        assert seen["screens"] == 28
        page.get_by_text("Nearly done").wait_for()
        if seen["ai"]:
            finish = page.get_by_role("button", name="Finish")
            assert finish.is_disabled(), "AI arms answer the trust questions"
            page.get_by_role("group", name="How much did you trust the AI's recommendations?").get_by_label("5").check()
            page.get_by_role("group", name="How useful were they for your decisions?").get_by_label("4").check()
        page.get_by_role("button", name="Finish").click()
        page.get_by_text("Thank you").wait_for()
        assert len(page.locator(".code-box").inner_text().strip()) == 8
        _check_page(page)
        arms_seen.add("ai" if seen["ai"] else "none")
        page.context.close()
        if arms_seen == {"ai", "none"}:
            break
    assert arms_seen == {"ai", "none"}, arms_seen


def test_task_without_a_session_explains_itself(browser: Any, base_url: str) -> None:
    page = _open(browser, base_url, "desktop", "/study/task", "No study session in this tab")
    page.get_by_role("link", name="Start from the beginning").click()
    page.get_by_text("Before you start").wait_for()
    page.context.close()


def test_population_toggle(browser: Any, base_url: str) -> None:
    page = _open(browser, base_url, "desktop", "/lab/results", "Primary contrasts")
    page.get_by_text("not people", exact=False).first.wait_for()
    page.get_by_role("button", name="Simulated: planted").click()
    page.get_by_text("planted on purpose", exact=False).first.wait_for()
    page.get_by_role("button", name="Human").click()
    page.get_by_text("No sessions in this population").wait_for()
    page.context.close()


def test_human_study_is_labelled_pending(browser: Any, base_url: str) -> None:
    page = _open(browser, base_url, "desktop", "/lab/overview", "Session populations")
    assert page.get_by_text("Human study: pending").count() >= 2
    row = page.locator("tr", has_text="Human participants")
    assert "pending" in row.inner_text()
    page.context.close()


def test_session_replay(browser: Any, base_url: str) -> None:
    page = _open(browser, base_url, "desktop", "/lab/sessions", "append-only event log")
    page.locator("table a.mono").first.click()
    page.get_by_text("What happened").wait_for()
    page.get_by_role("button", name="Decision 5,", exact=False).click()
    assert page.get_by_role("button", name="Decision 5,", exact=False).get_attribute("aria-current") == "step"
    page.get_by_text("Event log", exact=False).first.click()
    assert page.locator("details table tbody tr").count() > 26
    _check_page(page)
    page.context.close()


def test_design_preview_per_arm(browser: Any, base_url: str) -> None:
    page = _open(browser, base_url, "desktop", "/lab/design", "Pre-registered analysis")
    page.get_by_text("Pointing to", exact=False).first.wait_for()
    page.get_by_role("button", name="A · Human only").click()
    page.locator(".ai-panel").wait_for(state="detached")
    page.get_by_role("button", name="B · AI recommendation").click()
    page.locator(".ai-panel").wait_for()
    assert page.get_by_text("Pointing to", exact=False).count() == 0
    page.get_by_label("Case", exact=True).select_option("credit_limit-05")
    page.get_by_text("Reduce this customer's credit limit?").wait_for()
    page.context.close()


def test_keyboard_reaches_navigation(browser: Any, base_url: str) -> None:
    page = _open(browser, base_url, "desktop", "/lab/overview", "Session populations")
    names = []
    for _ in range(12):  # focus starts on the main region after each navigation; go back through the header
        page.keyboard.press("Shift+Tab")
        names.append(page.evaluate("document.activeElement && document.activeElement.textContent"))
    assert any(n and n.strip() == "Sessions" for n in names), names
    assert any(n and "Skip to content" in n for n in names), names
    page.context.close()


def test_researcher_routes_need_the_token_when_set(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from declab.api import create_app
    from declab.store import Store

    c = TestClient(create_app(token="t", store=Store(tmp_path / "x.db"), rate_limit=False))
    assert c.get("/lab/overview").status_code == 200  # the page loads; its data needs the token
    assert c.get("/api/lab/results/overview").status_code == 401
    assert json.loads(c.get("/api/study").text)["cases"] == 24


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_no_wcag_violations(browser: Any, base_url: str, viewport: str, scheme: str) -> None:
    """axe-core audit (WCAG 2.1 A/AA and best practices) of every view in both themes, the task screen included."""
    if not AXE.exists():
        pytest.skip("axe-core not installed (npm --prefix web ci)")
    ctx = browser.new_context(viewport=VIEWPORTS[viewport], color_scheme=scheme, bypass_csp=True)
    page = ctx.new_page()
    found: dict[str, list[str]] = {}

    def audit(label: str) -> None:
        page.wait_for_load_state("networkidle")
        page.add_script_tag(path=str(AXE))
        v = page.evaluate(
            """async () => (await axe.run(document, {runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa',
               'best-practice']})).violations.map(v => v.id + ': ' + v.nodes.map(n => n.target.join(' ')).join(', '))"""
        )
        if v:
            found[label] = v

    for _, path, marker in PAGES:
        page.goto(base_url + path)
        page.get_by_text(marker, exact=False).first.wait_for(timeout=30000)
        audit(path)
    page.goto(base_url + "/lab/sessions")
    page.locator("table a.mono").first.click()
    page.get_by_text("What happened").wait_for()
    audit("replay")
    page.goto(base_url + "/study")
    _start(page)
    audit("task")
    ctx.close()
    assert not found, found
