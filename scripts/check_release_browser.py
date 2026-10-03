"""Inspect current release pages without claiming the full evaluation gate passed."""
import functools
import http.server
import json
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

from proofsmith import config
from proofsmith.report.readme import pointer
from proofsmith.report.site import build_site, format_number


def main():
    build_site()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(config.SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    evidence = config.REPO / "docs/evidence/build"
    evidence.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width, height in ((1280, 800), (390, 844)):
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                for route in ("/", "/results/", "/integrate/", "/toolchain/", "/demo/"):
                    response = page.goto(base + route, wait_until="load")
                    assert response.status == 200, route
                    assert not errors, errors
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (route, width,
                        page.evaluate("Array.from(document.querySelectorAll('*')).filter(e => e.getBoundingClientRect().right > innerWidth).map(e => [e.tagName, e.className, e.getBoundingClientRect().right]).slice(0,10)"))
                    values = page.locator("[data-source]")
                    assert values.count(), route
                    for item in values.all():
                        source, suffix = item.get_attribute("data-source").split("#", 1)
                        actual = pointer(json.loads((config.REPO / source).read_text()), suffix)
                        assert item.inner_text().strip() == format_number(actual).strip(), (route, source, suffix)
                    if route == "/results/":
                        for rect in page.locator("rect[data-count-source]").all():
                            source, suffix = rect.get_attribute("data-count-source").split("#", 1)
                            count = pointer(json.loads((config.REPO / source).read_text()), suffix)
                            assert float(rect.get_attribute("height")) == count * 5
                        links = page.locator("a[href^='/results/']").all()
                        for link in links:
                            assert page.request.get(base + link.get_attribute("href")).status == 200
                    if route == "/" and width == 1280:
                        first = page.locator(".demo-matrix tbody tr").first.bounding_box()
                        assert first["y"] + first["height"] <= height, first
                    label = route.strip("/") or "landing"
                    page.screenshot(path=str(evidence / f"{label}-{width}.png"), full_page=True)
                page.close()
            browser.close()
    finally:
        server.shutdown()
    print("release browser checks: PASS (implementation preview; evaluation may remain incomplete)")


if __name__ == "__main__":
    main()
