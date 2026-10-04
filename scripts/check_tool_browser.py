"""Inspect the portable tool reports at desktop and phone widths against actual receipts."""
import functools
import http.server
import json
import threading
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from proofsmith import config
from proofsmith.gate import _finish, check_receipt
from proofsmith.report.gate import render_demo
from proofsmith.report.readme import pointer
from proofsmith.report.site import build_site


def main():
    root = config.RESULTS / "tool-demo"
    for directory in [root / "orderd/qualification", root / "catch2/qualification", root / "catch2/fixed",
                      *[root / "orderd" / name for name in ("timing_backoff", "scoped_cancel", "consistent_order")]]:
        check_receipt(directory)
        _finish(directory, json.loads((directory / "receipt.json").read_text()))
        check_receipt(directory)
    render_demo(root / "orderd", json.loads((root / "orderd/summary.json").read_text()))
    build_site()
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    handler = functools.partial(QuietHandler, directory=str(config.SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    evidence = config.REPO / "docs/evidence/tool"
    evidence.mkdir(parents=True, exist_ok=True)
    pages_checked = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width, height in ((1280, 900), (390, 844)):
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                for route in ("/gate/", "/gate/timing_backoff/", "/gate/scoped_cancel/", "/upstream/"):
                    response = page.goto(base + route, wait_until="load")
                    assert response.status == 200 and not errors, (route, errors)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (route, width)
                    if route != "/gate/":
                        expected = "REJECTED" if "timing_backoff" in route else "VERIFIED"
                        assert page.get_by_test_id("status").inner_text() == expected
                        assert page.get_by_test_id("baseline-failures").inner_text().strip() == "20 / 20"
                        assert page.get_by_test_id("candidate-failures").inner_text().strip() == ("20 / 20" if expected == "REJECTED" else "0 / 20")
                    values = page.locator("[data-source]")
                    assert values.count(), route
                    sources = {}
                    for item in values.all():
                        relative, fragment = item.get_attribute("data-source").split("#", 1)
                        if relative not in sources:
                            sources[relative] = page.request.get(urljoin(page.url, relative)).json()
                        source = sources[relative]
                        assert item.text_content().strip() == str(pointer(source, fragment)), (route, fragment, item.text_content())
                    for link in page.locator("a").all():
                        assert page.request.get(urljoin(page.url, link.get_attribute("href"))).status == 200
                    label = route.strip("/").replace("/", "-")
                    page.screenshot(path=str(evidence / f"{label}-{width}.png"), full_page=True)
                    pages_checked += 1
                page.close()
            browser.close()
    finally:
        server.shutdown()
    receipt = {"schema": "proofsmith.tool-browser-check/1", "pages_checked": pages_checked,
               "widths": [1280, 390], "receipt_values_match": True, "relative_links_work": True,
               "horizontal_overflow": False, "javascript_errors": []}
    (config.RESULTS / "tool-browser-check.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
