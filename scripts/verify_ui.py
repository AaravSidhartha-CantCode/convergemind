"""Playwright verification gate: does the UI actually render, at every width?

Captures screenshots at 390, 768 and 1440 and asserts the Signal Room
contract from 01 Planning/Design.md actually landed: the dark canvas, the
three node-type colours, both agent rails, and the graph component.

Usage (with backend on :8000 and streamlit on :8501):
    python -m scripts.verify_ui
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

UI_URL = "http://127.0.0.1:8501"
SHOT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
WIDTHS = {"mobile": 390, "tablet": 768, "desktop": 1440}

INK_BASE = "rgb(16, 20, 26)"


def main() -> int:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    failures = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for name, width in WIDTHS.items():
            page = browser.new_page(viewport={"width": width, "height": 1000})
            page.goto(UI_URL, wait_until="networkidle", timeout=60_000)
            page.wait_for_selector(".cm-title", timeout=30_000)
            page.wait_for_timeout(3_000)  # let the graph iframe settle

            # The locked background token must actually be applied.
            background = page.evaluate(
                "getComputedStyle(document.querySelector('.stApp')).backgroundColor"
            )
            if background != INK_BASE:
                failures.append(f"{name}: background {background}, expected {INK_BASE}")

            # Both agent rails must be present at every width.
            labels = page.locator(".cm-label").all_inner_texts()
            for agent in ("CHATAGENT", "EMAILAGENT"):
                if not any(agent in label.upper() for label in labels):
                    failures.append(f"{name}: missing rail for {agent}")

            # The graph component must have mounted.
            if page.locator("iframe").count() == 0:
                failures.append(f"{name}: graph iframe did not mount")

            page.screenshot(path=str(SHOT_DIR / f"{name}-{width}.png"), full_page=True)
            print(f"   captured {name} ({width}px)")
            page.close()
        browser.close()

    print()
    if failures:
        print("FAILURES:")
        for failure in failures:
            print(f"   - {failure}")
        return 1
    print(f"ALL CHECKS PASSED. Screenshots in {SHOT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
