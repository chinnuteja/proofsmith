#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
python - <<'PY'
import functools, http.server, json, subprocess, sys, tempfile, threading
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from playwright.sync_api import sync_playwright
root = Path.cwd()
with tempfile.TemporaryDirectory(prefix='proofsmith-share-') as name:
    site = Path(name) / 'site'
    subprocess.run([sys.executable, 'scripts/build_share_site.py', '--out', str(site)], check=True)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    screenshots = root / 'docs/evidence/byteask-comparison'
    overview_screenshots = root / 'docs/evidence/product-overview'
    overview_screenshots.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width in (1280,390):
                page = browser.new_page(viewport={'width':width,'height':900})
                errors=[]
                page.on('pageerror', lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                assert not errors and page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert 'no advantage over ByteAsk' in page.locator('body').inner_text()
                for anchor in page.locator('a').all():
                    href = anchor.get_attribute('href')
                    if urlsplit(href).scheme:
                        continue
                    assert (site / unquote(urlsplit(href).path)).is_file(), href
                page.screenshot(path=str(screenshots / f'share-{width}.png'), full_page=True)
                page.get_by_role('link',name='Inspect the real ByteAsk results').click()
                assert page.locator('tbody tr').count()==5
                page.locator('tbody a').first.click()
                assert 'VERIFIED' in page.locator('body').inner_text()
                page.close()
                page = browser.new_page(viewport={'width':width,'height':900})
                overview_errors=[]
                page.on('pageerror', lambda e:overview_errors.append(str(e)))
                overview_url=f'http://127.0.0.1:{server.server_port}/overview/'
                page.goto(overview_url)
                assert page.title()=='Proofsmith — C++ patch verification with replayable evidence'
                assert not overview_errors, overview_errors
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'overview overflow at {width}px'
                assert 'No advantage over ByteAsk' in page.locator('body').inner_text()
                for anchor in page.locator('a').all():
                    href = anchor.get_attribute('href')
                    if urlsplit(href).scheme:
                        continue
                    destination=urlsplit(urljoin(overview_url,href))
                    target=site / unquote(destination.path).lstrip('/')
                    if target.is_dir():
                        target=target / 'index.html'
                    assert target.is_file(), href
                    if href.startswith('#'):
                        assert page.locator(href).count()==1, href
                page.screenshot(path=str(overview_screenshots / f'overview-{width}.png'), full_page=True)
                for verdict in ('REJECTED','VERIFIED'):
                    page.get_by_role('link',name=verdict,exact=True).click()
                    assert verdict in page.locator('body').inner_text()
                    page.goto(overview_url)
                page.get_by_role('link',name='Real repairs, measurements, and receipts →').click()
                assert page.locator('tbody tr').count()==5
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
record={'static_share_site_valid':True,'widths':[1280,390], 'relative_links_preserved':True,
        'live_report_and_gate_link_checked':True,
        'neutral_overview_valid':True,'overview_rejected_and_verified_receipts_checked':True,
        'overview_case_study_link_checked':True,'model_requests':0}
(root / 'results/share-site-check.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
PY
