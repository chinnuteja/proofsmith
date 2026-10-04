"""Check the updated integration page at desktop and phone sizes."""
import functools
import http.server
import json
import threading
from playwright.sync_api import sync_playwright
from proofsmith import config
from proofsmith.report.readme import pointer
from proofsmith.report.site import format_number

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(config.SITE)))
threading.Thread(target=server.serve_forever, daemon=True).start()
evidence = config.REPO / 'docs/evidence/integration'
evidence.mkdir(parents=True, exist_ok=True)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (1280, 390):
            page = browser.new_page(viewport={'width': width, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            response = page.goto(f'http://127.0.0.1:{server.server_port}/integrate/')
            assert response.status == 200 and not errors
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert '[mcp_servers.proofsmith]' in page.locator('pre').inner_text()
            assert 'seal_check' in page.locator('main').inner_text()
            for item in page.locator('[data-source]').all():
                relative, fragment = item.get_attribute('data-source').split('#', 1)
                value = json.loads((config.REPO / relative).read_text())
                assert item.text_content().strip() == format_number(pointer(value, fragment))
            page.screenshot(path=str(evidence / f'integrate-{width}.png'), full_page=True)
            page.close()
        browser.close()
finally:
    server.shutdown()
    server.server_close()
receipt = {'schema': 'proofsmith.integration-browser/1', 'widths': [1280, 390], 'receipt_values_match': True,
           'horizontal_overflow': False, 'javascript_errors': []}
(config.RESULTS / 'integration-browser-check.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
