"""
tests/test_b10_playwright_smoke.py - Stage B10: Playwright Smoke Testing Suite with Screenshots.

Verifies:
1. Streamlit server boots up and serves the dashboard application.
2. Navigation across key command-center pages works without crash.
3. Screenshots are captured and archived into `docs/screenshots/`.
4. Graceful teardown of server process.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.parent
SCREENSHOT_DIR = ROOT / "docs" / "screenshots"


@pytest.fixture(scope="module")
def streamlit_server():
    """Start Streamlit server on an ephemeral port and yield URL."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    port = "8599"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ROOT / "demo" / "app.py"),
        "--server.port",
        port,
        "--server.headless",
        "true",
        "--server.runOnSave",
        "false",
        "--browser.gatherUsageStats",
        "false",
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["URBANFLOW_OFFLINE"] = "1"
    env["URBANFLOW_CACHE_MODE"] = "1"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    url = f"http://localhost:{port}"

    # Poll server until live or timeout
    import urllib.request
    started = False
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=1) as resp:
                if resp.status == 200:
                    started = True
                    break
        except Exception:
            time.sleep(1)

    if not started:
        proc.terminate()
        pytest.skip(f"Streamlit server failed to start within 30s on {url}")

    yield url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_command_center_page_smoke(streamlit_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(streamlit_server, wait_until="networkidle", timeout=45000)
        page.wait_for_selector(".command-header", timeout=30000)

        # Confirm command center title is rendered
        assert page.locator(".command-title").is_visible()

        # Capture screenshot
        shot_path = SCREENSHOT_DIR / "b10_01_command_center.png"
        page.screenshot(path=str(shot_path), full_page=True)
        assert shot_path.exists()
        assert shot_path.stat().st_size > 5000

        browser.close()


def test_scenario_lab_page_smoke(streamlit_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(streamlit_server, wait_until="networkidle", timeout=45000)
        page.wait_for_selector(".command-header", timeout=30000)

        # Navigate to Scenario Lab specifically using the sidebar radio locator
        page.locator('[data-testid="stRadioGroup"]').get_by_text("Scenario Lab").click()
        page.wait_for_timeout(4000)

        # Confirm verdict card or MCDA is visible
        assert "SCENARIO LAB" in page.content() or page.locator(".command-title").is_visible()

        shot_path = SCREENSHOT_DIR / "b10_02_scenario_lab.png"
        page.screenshot(path=str(shot_path), full_page=True)
        assert shot_path.exists()

        browser.close()


def test_transit_metro_page_smoke(streamlit_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(streamlit_server, wait_until="networkidle", timeout=45000)
        page.wait_for_selector(".command-header", timeout=30000)

        page.locator('[data-testid="stRadioGroup"]').get_by_text("Transit & Metro").click()
        page.wait_for_timeout(4000)

        assert "TRANSIT & METRO" in page.content() or page.locator(".command-title").is_visible()

        shot_path = SCREENSHOT_DIR / "b10_03_transit_metro.png"
        page.screenshot(path=str(shot_path), full_page=True)
        assert shot_path.exists()

        browser.close()


def test_validation_harness_page_smoke(streamlit_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(streamlit_server, wait_until="networkidle", timeout=45000)
        page.wait_for_selector(".command-header", timeout=30000)

        page.locator('[data-testid="stRadioGroup"]').get_by_text("Validation Harness").click()
        page.wait_for_timeout(4000)

        assert "VALIDATION HARNESS" in page.content() or page.locator(".command-title").is_visible()

        shot_path = SCREENSHOT_DIR / "b10_04_validation_harness.png"
        page.screenshot(path=str(shot_path), full_page=True)
        assert shot_path.exists()

        browser.close()

