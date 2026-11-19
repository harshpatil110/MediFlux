"""Browser regression checks against running local web, mobile, and desktop clients.

Install Playwright and its Chromium browser, start the API in demo replay mode,
start Vite on 5173, and serve mobile/dist on 8081 before running this module.
Pass --desktop-cdp http://127.0.0.1:9224 to check a packaged Electron window.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from playwright.async_api import Browser, Page, async_playwright

WEB_ROUTES = (
    "overview", "cascade", "agents", "approvals", "adapter-forge",
    "regulatory-lab", "prescriptions", "cold-chain", "audit", "copilot", "developer",
)


async def check_web(browser: Browser, api_url: str, web_url: str) -> None:
    """Check authenticated routes, stable SSE subscriptions, sale, and audit UI."""
    context = await browser.new_context()
    await context.add_init_script(
        f"localStorage.setItem('mediflux_backend_url', {api_url!r})"
    )
    page = await context.new_page()
    errors: list[str] = []
    failures: list[str] = []
    streams: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: failures.append(response.url)
            if response.url.startswith(api_url) and response.status >= 400 else None)
    page.on("request", lambda request: streams.append(request.url)
            if "/stream?" in request.url else None)
    await page.goto(f"{web_url}/login")
    await page.get_by_role("button", name="Sign In as ADMIN", exact=True).click()
    await page.wait_for_url("**/overview")
    await page.get_by_role("button", name="Sell 1 Strip", exact=True).wait_for()
    await page.wait_for_timeout(500)
    count = len(streams)
    await page.wait_for_timeout(1500)
    assert len(streams) == count, "Web SSE subscriptions restart while idle"
    async with page.expect_response("**/api/v1/simulator/pos") as pending:
        await page.get_by_role("button", name="Sell 1 Strip", exact=True).click()
    assert (await pending.value).ok
    for route in WEB_ROUTES:
        await page.goto(f"{web_url}/{route}", wait_until="domcontentloaded")
        await page.wait_for_timeout(500)
        assert len(await page.locator("body").inner_text()) > 200, f"Blank route: {route}"
        if route == "audit":
            await page.get_by_role("button", name="Verify Hash Chain Integrity").click()
            await page.get_by_text("CHAIN VERIFIED (INTACT)", exact=True).wait_for()
        print(f"[OK] Web /{route}", flush=True)
    assert not errors, errors
    assert not failures, failures
    await context.close()


async def check_mobile(browser: Browser, api_url: str, mobile_url: str) -> None:
    """Exercise real mobile login, barcode dispensing, and live SSE event delivery."""
    context = await browser.new_context(viewport={"width": 390, "height": 844})
    await context.add_init_script(
        f"localStorage.setItem('mediflux_mobile_backend_url', {api_url!r})"
    )
    page = await context.new_page()
    errors: list[str] = []
    failures: list[str] = []
    auth_requests: list[str] = []
    page.on("request", lambda request: auth_requests.append(request.url)
            if request.url.endswith(("/api/v1/me", "/api/v1/devices")) else None)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: failures.append(response.url)
            if response.url.startswith(api_url) and response.status >= 400 else None)
    await page.goto(mobile_url)
    await page.get_by_placeholder("operator@mediflux.in").fill("admin@mediflux.in")
    await page.locator("input[type=password]").fill("AdminPassword123!")
    await page.get_by_text("AUTHENTICATE & ENTER", exact=True).click()
    await page.get_by_text("OPERATIONAL NODE SCOPE", exact=True).wait_for()
    await page.get_by_text("LIVE STREAM CONNECTED", exact=True).wait_for()
    await page.wait_for_timeout(500)
    count = len(auth_requests)
    await page.wait_for_timeout(1500)
    assert len(auth_requests) == count, "Mobile session restoration loops while idle"
    marker = f"Browser stream regression {uuid.uuid4().hex[:8]}"
    response = await context.request.post(f"{api_url}/api/v1/events", data={
        "event_id": str(uuid.uuid4()), "type": "pos.sales",
        "node_id": "11111111-1111-1111-1111-111111111111",
        "payload": {"summary": marker},
    }, headers={"Authorization": "Bearer mock-admin-token"})
    assert response.ok
    await page.get_by_text(marker, exact=True).wait_for(timeout=10000)
    print("[OK] Mobile receives live events without a reload", flush=True)
    await page.locator('a[href="/sell"]').click()
    await page.get_by_text("Paracetamol 650mg", exact=True).first.click()
    async with page.expect_response("**/api/v1/events/sale") as pending:
        await page.get_by_text("DISPENSE & CASCADE (1 STRIP)", exact=True).click()
    sale_response = await pending.value
    assert sale_response.ok
    sale = await sale_response.json()
    assert sale["applied"] and len(sale["cascade"]["steps"]) == 5
    print("[OK] Mobile barcode sale and five-stage cascade", flush=True)
    for route in ("approvals", "scan-rx", "cold-chain", "copilot"):
        await page.locator(f'a[href="/{route}"]').click()
        await page.wait_for_timeout(650)
        assert len(await page.locator("body").inner_text()) > 200, f"Blank mobile route: {route}"
        print(f"[OK] Mobile /{route}", flush=True)
    assert not errors, errors
    assert not failures, failures
    await context.close()


async def check_desktop(page: Page, api_url: str) -> None:
    """Verify packaged assets and the native bridge through Electron's CDP port."""
    assert page.url.startswith("file:"), page.url
    assert await page.evaluate("Boolean(window.medifluxDesktop?.isDesktop)")
    await page.evaluate("url => localStorage.setItem('mediflux_backend_url', url)", api_url)
    await page.goto(f"{page.url.split('#')[0]}#/login")
    await page.get_by_role("button", name="Sign In as ADMIN", exact=True).click()
    await page.get_by_role("button", name="Sell 1 Strip", exact=True).wait_for()
    platform = await page.evaluate("window.medifluxDesktop.getPlatformInfo()")
    assert platform
    print("[OK] Packaged desktop renders, authenticates, and exposes its native bridge", flush=True)


async def main() -> None:
    """Run the selected local clients and fail on browser or API regressions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--web-url", default="http://127.0.0.1:5173")
    parser.add_argument("--mobile-url", default="http://127.0.0.1:8081")
    parser.add_argument("--desktop-cdp")
    args = parser.parse_args()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            await check_web(browser, args.api_url, args.web_url)
            await check_mobile(browser, args.api_url, args.mobile_url)
            if args.desktop_cdp:
                desktop = await playwright.chromium.connect_over_cdp(args.desktop_cdp)
                await check_desktop(desktop.contexts[0].pages[0], args.api_url)
                await desktop.close()
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
