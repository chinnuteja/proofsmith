"""Playwright checks for the static site. The gate treats this as authoritative."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from proofsmith.config import REPO
from proofsmith.report.site import format_number

BASE_URL = "http://127.0.0.1:8765/"
VIEWPORTS = ((1280, 800, "1280"), (390, 844, "390"))


def _resolve_pointer(document: object, pointer: str) -> object:
    if pointer.startswith("#"):
        pointer = pointer[1:]
    if pointer == "" or pointer == "/":
        return document
    current = document
    for raw in pointer.split("/"):
        if raw == "":
            continue
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(pointer)
    return current


_JSON_CACHE: dict[str, object] = {}


def _value_at(spec: str) -> object:
    path, _, pointer = spec.partition("#")
    if not pointer.startswith("/") and pointer != "":
        pointer = "/" + pointer
    if path not in _JSON_CACHE:
        _JSON_CACHE[path] = json.loads((REPO / path).read_text(encoding="utf-8"))
    return _resolve_pointer(_JSON_CACHE[path], "#" + pointer)


def assert_data_sources(page: Page) -> None:
    loc = page.locator("[data-source]")
    count = loc.count()
    assert count > 0, "page has no data-source elements"
    for index in range(count):
        el = loc.nth(index)
        spec = el.get_attribute("data-source")
        assert spec, "empty data-source"
        expected = format_number(_value_at(spec)).strip()
        actual = (el.text_content() or "").strip()
        assert actual == expected, f"{spec}: page={actual!r} json={expected!r}"


def assert_no_overflow(page: Page, width: int) -> None:
    metrics = page.evaluate(
        """() => ({
            scroll: document.documentElement.scrollWidth,
            inner: window.innerWidth
        })"""
    )
    assert metrics["scroll"] <= metrics["inner"], (
        f"horizontal overflow at {width}: scrollWidth={metrics['scroll']} innerWidth={metrics['inner']}"
    )


def assert_clean(page: Page, state: dict, width: int) -> None:
    assert not state["console"], f"console errors at {width}: {state['console']}"
    assert not state["failed"], f"failed requests at {width}: {state['failed']}"
    assert_no_overflow(page, width)
    assert_data_sources(page)


def check_b0_1(page: Page) -> None:
    page.goto(BASE_URL, wait_until="load")
    page.wait_for_selector("[data-testid=toolchain-table]")
    title = page.title()
    assert "Proofsmith" in title, f"title was {title!r}"


def check_b0_2(page: Page) -> None:
    page.goto(BASE_URL, wait_until="load")
    rows = page.locator("[data-testid=toolchain-table] tbody tr")
    assert rows.count() == 6, f"expected 6 rows, got {rows.count()}"
    for index in range(6):
        row = rows.nth(index)
        assert row.locator(".pill-pass").count() >= 1, f"row {index} missing .pill-pass"
        expected = row.locator("[data-testid=expected-kind]").inner_text().strip()
        observed = row.locator("[data-testid=observed-kind]").inner_text().strip()
        assert expected == observed, f"row {index}: expected {expected!r} observed {observed!r}"


def check_b0_3(page: Page) -> None:
    page.goto(BASE_URL, wait_until="load")
    el = page.locator("[data-testid=clang-version]")
    assert el.count() == 1, "missing clang-version"
    text = el.inner_text()
    assert "clang version 18" in text, text
    source = el.get_attribute("data-source")
    assert source == "results/toolchain.json#/clang_version", source


def check_b0_4(page: Page) -> None:
    page.goto(BASE_URL, wait_until="load")
    rows = page.locator("[data-testid=toolchain-table] tbody tr")
    assert rows.count() == 6, f"expected 6 rows, got {rows.count()}"
    for index in range(6):
        details = rows.nth(index).locator("details")
        assert details.count() == 1, f"row {index} has no raw output details"
        summary = details.locator("summary").inner_text().strip().lower()
        assert "raw output" in summary, f"row {index} summary was {summary!r}"
    lock = page.locator("[data-testid=raw-lock_order]")
    assert lock.count() == 1, "missing lock-order raw output"
    lock.locator("summary").click()
    pre = lock.locator("pre")
    pre.wait_for(state="visible")
    text = pre.inner_text()
    assert "lock-order-inversion" in text, text[:400]


check_b0_1.check_id = "B0.1"  # type: ignore[attr-defined]
check_b0_2.check_id = "B0.2"  # type: ignore[attr-defined]
check_b0_3.check_id = "B0.3"  # type: ignore[attr-defined]
check_b0_4.check_id = "B0.4"  # type: ignore[attr-defined]

CHECKS: dict[int, list[Callable[[Page], None]]] = {
    0: [check_b0_1, check_b0_2, check_b0_3, check_b0_4],
}


def _open(browser, width: int, height: int):
    page = browser.new_page(viewport={"width": width, "height": height})
    state: dict[str, list[str]] = {"console": [], "failed": []}

    def on_console(msg) -> None:
        if msg.type == "error":
            state["console"].append(msg.text)

    def on_failed(req) -> None:
        failure = req.failure
        state["failed"].append(f"{req.url} {failure}")

    page.on("console", on_console)
    page.on("requestfailed", on_failed)
    page.goto(BASE_URL, wait_until="load")
    page.wait_for_selector("[data-testid=toolchain-table]")
    return page, state


def run(phase: int) -> list[str]:
    evidence = REPO / "docs" / "evidence" / f"phase-{phase}"
    evidence.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    checks = CHECKS[phase]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for width, height, tag in VIEWPORTS:
                page, state = _open(browser, width, height)
                try:
                    page.screenshot(path=str(evidence / f"index-{tag}.png"), full_page=True)
                    assert_clean(page, state, width)
                    for check in checks:
                        check_id = getattr(check, "check_id", check.__name__)
                        try:
                            check(page)
                        except Exception as exc:
                            failures.append(f"{check_id}@{tag}: {exc}")
                        page.screenshot(
                            path=str(evidence / f"{check_id}-{tag}.png"),
                            full_page=True,
                        )
                    try:
                        assert_clean(page, state, width)
                    except Exception as exc:
                        failures.append(f"global@{tag}: {exc}")
                except Exception as exc:
                    failures.append(f"page@{tag}: {exc}")
                    page.screenshot(path=str(evidence / f"index-{tag}.png"), full_page=True)
                finally:
                    page.close()
        finally:
            browser.close()
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, required=True)
    args = parser.parse_args(argv)
    if args.phase not in CHECKS:
        print(f"BROWSER {args.phase}: FAIL")
        print(f"no checks registered for phase {args.phase}")
        return 1
    try:
        failures = run(args.phase)
    except Exception:
        traceback.print_exc()
        print(f"BROWSER {args.phase}: FAIL")
        return 1
    if failures:
        print(f"BROWSER {args.phase}: FAIL")
        for item in failures:
            print(item)
        return 1
    print(f"BROWSER {args.phase}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
