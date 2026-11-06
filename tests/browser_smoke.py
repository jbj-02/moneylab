"""Real Chromium smoke journeys (desktop and narrow viewport).

Executed separately in GitHub Actions against a local Streamlit server, not
imported by pytest. Screenshots are uploaded as CI artifacts. Fictional values
only; the script does not contact the public MoneyLab deployment.
"""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright, expect

OUTPUT = Path(os.environ.get("BROWSER_ARTIFACT_DIR", "artifacts/browser"))
OUTPUT.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get("MONEYLAB_TEST_URL", "http://127.0.0.1:8501")


def assert_no_horizontal_scroll(page, view):
    width = page.evaluate("document.documentElement.scrollWidth")
    viewport = page.evaluate("window.innerWidth")
    if width > viewport + 4:
        raise AssertionError(
            f"{view}: horizontal overflow: document={width}px viewport={viewport}px"
        )


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        for viewport, label in (
            ({"width": 1280, "height": 900}, "desktop"),
            ({"width": 390, "height": 844}, "mobile"),
        ):
            context = browser.new_context(
                viewport=viewport, reduced_motion="reduce",
            )
            page = context.new_page()
            page.goto(BASE, wait_until="domcontentloaded", timeout=45000)
            expect(page.get_by_role(
                "heading", name="MoneyLab", exact=True
            )).to_be_visible(timeout=45000)
            assert_no_horizontal_scroll(page, f"{label} home")
            page.screenshot(path=str(OUTPUT / f"{label}-home.png"),
                            full_page=True)

            # Existing direct route must remain reachable even if the page
            # is hidden from primary navigation.
            page.goto(f"{BASE}/moving-alpha",
                      wait_until="domcontentloaded", timeout=45000)
            expect(page.get_by_role(
                "heading", name="Moving Out Decision Lab"
            )).to_be_visible(timeout=45000)
            expect(page.get_by_text(
                "Fictional example: includes", exact=False
            )).to_be_visible(timeout=45000)
            for _ in range(2):
                page.get_by_role("button", name="Continue", exact=True).click()
            page.get_by_role("button", name="Compare stay vs move").click()
            expect(page.get_by_text(
                "Included in this comparison", exact=True
            ).first).to_be_visible(timeout=45000)
            expect(page.get_by_text(
                "Recorded liquid funds before move", exact=False
            )).to_be_visible(timeout=15000)
            assert_no_horizontal_scroll(page, f"{label} move results")
            page.screenshot(path=str(OUTPUT / f"{label}-results.png"),
                            full_page=True)

            page.get_by_role(
                "button", name="Edit original assumptions"
            ).click()
            expect(page.get_by_role("button", name="Continue", exact=True)).to_be_visible(timeout=20000)
            for _ in range(2):
                page.get_by_role("button", name="Continue", exact=True).click()
            page.get_by_role("button", name="Compare stay vs move").click()
            expect(page.get_by_text(
                "Included in this comparison", exact=True
            ).first).to_be_visible(timeout=45000)

            page.goto(f"{BASE}/settings",
                      wait_until="domcontentloaded", timeout=45000)
            expect(page.get_by_role(
                "heading", name="Save or restore your workspace"
            )).to_be_visible(timeout=45000)
            assert_no_horizontal_scroll(page, f"{label} settings")
            context.close()
        browser.close()


if __name__ == "__main__":
    run()
