import os
import sys
import time
import asyncio
from playwright.async_api import async_playwright

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

async def run_ui_test():
    console_messages = []
    page_errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        print("1. Navigating to http://127.0.0.1:8000...")
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.evaluate("() => localStorage.clear()")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # Upload View - Dark Mode
        await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "01_upload_dark.png"), full_page=True)
        print("Captured 01_upload_dark.png")

        # Click Load Demo
        print("2. Clicking 'Load Demo'...")
        demo_btn = page.locator("#btn-load-demo")
        await demo_btn.click()

        # Wait for pipeline to complete and auto-redirect to #overview
        print("3. Waiting for processing and redirect to #overview...")
        await page.wait_for_url("**/#overview", timeout=15000)
        await page.wait_for_timeout(2000) # Allow animations/charts to render

        # Overview View - Dark Mode
        await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "02_overview_dark.png"), full_page=True)
        print("Captured 02_overview_dark.png")

        # Transactions View - Dark Mode
        print("4. Navigating to #transactions...")
        await page.goto("http://127.0.0.1:8000/#transactions")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "03_transactions_dark.png"), full_page=True)
        print("Captured 03_transactions_dark.png")

        # Open inspection drawer on first transaction
        inspect_btn = page.locator(".btn-inspect").first
        if await inspect_btn.count() > 0:
            await inspect_btn.click()
            await page.wait_for_timeout(1500)
            await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "04_inspection_drawer_dark.png"))
            print("Captured 04_inspection_drawer_dark.png")
            # Close drawer
            await page.locator("#btn-close-drawer").click()
            await page.wait_for_timeout(500)

        # Analytics View - Dark Mode
        print("5. Navigating to #analytics...")
        await page.goto("http://127.0.0.1:8000/#analytics")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "05_analytics_dark.png"), full_page=True)
        print("Captured 05_analytics_dark.png")

        # Validation View - Dark Mode
        print("6. Navigating to #validation...")
        await page.goto("http://127.0.0.1:8000/#validation")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "06_validation_dark.png"), full_page=True)
        print("Captured 06_validation_dark.png")

        # Export View - Dark Mode
        print("7. Navigating to #export...")
        await page.goto("http://127.0.0.1:8000/#export")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "07_export_dark.png"), full_page=True)
        print("Captured 07_export_dark.png")

        # Toggle to Light Mode
        print("8. Toggling to Light Mode...")
        await page.locator("#theme-toggle").click()
        await page.wait_for_timeout(800)

        # Overview View - Light Mode
        await page.goto("http://127.0.0.1:8000/#overview")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "08_overview_light.png"), full_page=True)
        print("Captured 08_overview_light.png")

        # Analytics View - Light Mode
        await page.goto("http://127.0.0.1:8000/#analytics")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "09_analytics_light.png"), full_page=True)
        print("Captured 09_analytics_light.png")

        await browser.close()

    print("\n--- Console Messages ---")
    for msg in console_messages:
        print(msg)

    print("\n--- Page Errors ---")
    if page_errors:
        for err in page_errors:
            print("ERROR:", err)
        sys.exit(1)
    else:
        print("No Javascript page errors detected!")

if __name__ == "__main__":
    asyncio.run(run_ui_test())
