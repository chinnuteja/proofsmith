#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
python - <<'PY'
import functools, http.server, json, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
root = Path.cwd()
scored = root / 'experiments/byteask-comparison/live-v1-score'
result = json.loads((scored / 'results.json').read_text())
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(root)))
threading.Thread(target=server.serve_forever, daemon=True).start()
snapshots = root / 'docs/evidence/byteask-comparison'
snapshots.mkdir(parents=True, exist_ok=True)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (1280, 390):
            page = browser.new_page(viewport={'width': width, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            response = page.goto(f'http://127.0.0.1:{server.server_port}/experiments/byteask-comparison/live-v1-score/index.html')
            assert response.status == 200 and not errors
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert page.locator('tbody tr').count() == len(result['rows'])
            text = page.locator('body').inner_text()
            assert result['metrics']['claim'] in text
            assert result['protocol_sha256'] in text
            for row, recorded in zip(page.locator('tbody tr').all(), result['rows']):
                assert recorded['case_id'] in row.inner_text()
                assert recorded['judge_status'] in row.inner_text()
                assert recorded['gate_status'] in row.inner_text()
            page.screenshot(path=str(snapshots / f'live-{width}.png'), full_page=True)
            if width == 1280:
                with page.expect_navigation():
                    page.locator('tbody a').first.click()
                assert result['rows'][0]['gate_status'] in page.locator('body').inner_text()
            page.close()
        browser.close()
finally:
    server.shutdown()
    server.server_close()
record = {'schema': 'proofsmith.byteask-live-browser/1', 'widths': [1280,390],
          'rows_match_recorded_results': True, 'horizontal_overflow': False,
          'javascript_errors': [], 'gate_receipt_link_checked': True}
(root / 'results/byteask-live-browser.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
PY
