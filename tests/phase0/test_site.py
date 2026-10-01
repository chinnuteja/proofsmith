"""Phase 0 site skeleton."""

from proofsmith.config import SITE
from proofsmith.report.site import build_site


def test_build_site_writes_index_and_css():
    build_site()
    html_path = SITE / "index.html"
    css_path = SITE / "site.css"
    assert html_path.is_file()
    assert css_path.is_file()
    html = html_path.read_text(encoding="utf-8")
    assert 'data-testid="toolchain-table"' in html
