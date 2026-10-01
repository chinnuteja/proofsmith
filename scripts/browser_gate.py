"""Playwright checks for the static site. The gate treats this as authoritative."""

from __future__ import annotations

import argparse
import json
import re
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


def check_b1_1(page: Page) -> None:
    page.goto(BASE_URL + "demo/", wait_until="load")
    page.wait_for_selector("[data-testid=issue-body]")
    instance = json.loads((REPO / "cases" / "orderd" / "instance.json").read_text(encoding="utf-8"))
    actual = page.locator("[data-testid=issue-body]").inner_text().strip()
    expected = instance["issue"]["body"].strip()
    assert actual == expected, f"issue body mismatch\npage={actual!r}\njson={expected!r}"


def check_b1_2(page: Page) -> None:
    page.goto(BASE_URL + "demo/", wait_until="load")
    rows = page.locator("[data-testid=matrix] tbody tr")
    assert rows.count() == 4, f"expected 4 rows, got {rows.count()}"
    for index in range(4):
        cells = rows.nth(index).locator("td.result")
        assert cells.count() == 3, f"row {index} has {cells.count()} result cells"
        for column in range(3):
            cell = cells.nth(column)
            bits = cell.locator("[data-source]")
            assert bits.count() == 2, f"row {index} col {column} data-source count {bits.count()}"
            left = bits.nth(0).inner_text().strip()
            right = bits.nth(1).inner_text().strip()
            shown = cell.inner_text().replace(" ", "").replace("\n", "")
            assert f"{left}/{right}" in shown, f"row {index} col {column}: {shown!r} vs {left}/{right}"


def check_b1_3(page: Page) -> None:
    page.goto(BASE_URL + "demo/", wait_until="load")
    row = page.locator("[data-testid=row-timing_backoff]")
    assert row.locator("[data-testid=ctest-cell] .pill-pass").count() == 1
    assert row.locator("[data-testid=verifier-cell] .pill-fail").count() == 1


def check_b1_4(page: Page) -> None:
    page.goto(BASE_URL + "demo/", wait_until="load")
    pill = page.locator("[data-testid=row-scoped_cancel] [data-testid=verifier-cell] .pill-pass")
    assert pill.count() == 1, "scoped_cancel verifier is not a pass pill"
    text = pill.inner_text().replace(" ", "").replace("\n", "")
    assert text == "0/20", text


def check_b1_5(page: Page) -> None:
    page.goto(BASE_URL + "demo/", wait_until="load")
    dots = page.locator("[data-testid=run-strip] .dot")
    assert dots.count() == 10, dots.count()


def check_b1_6(page: Page) -> None:
    page.goto(BASE_URL + "demo/", wait_until="load")
    raw = page.locator("[data-testid=raw-report]")
    assert raw.count() == 1
    raw.locator("summary").click()
    pre = raw.locator("pre")
    pre.wait_for(state="visible")
    text = pre.inner_text()
    assert "lock-order-inversion" in text
    assert "OrderBook::" in text


def check_b1_7(page: Page) -> None:
    page.goto(BASE_URL + "demo/", wait_until="load")
    label = page.locator("[data-testid=harness-source-label]")
    assert label.inner_text().strip() == "Reference harness (hand-written)"


def check_b1_8(page: Page) -> None:
    page.goto(BASE_URL + "demo/", wait_until="load")
    verified = {"C1", "C2", "C3", "C4", "C5", "C6"}
    links = page.locator("a[href]")
    external = 0
    for index in range(links.count()):
        href = links.nth(index).get_attribute("href") or ""
        if href.startswith("http://") or href.startswith("https://"):
            external += 1
            ok = href == "https://byteask.ai/" or href.startswith("https://docs.byteask.ai/")
            assert ok, href
            claim = links.nth(index).get_attribute("data-claim")
            assert claim in verified, claim
    assert external >= 1, "no external claim links"


check_b1_1.check_id = "B1.1"  # type: ignore[attr-defined]
check_b1_2.check_id = "B1.2"  # type: ignore[attr-defined]
check_b1_3.check_id = "B1.3"  # type: ignore[attr-defined]
check_b1_4.check_id = "B1.4"  # type: ignore[attr-defined]
check_b1_5.check_id = "B1.5"  # type: ignore[attr-defined]
check_b1_6.check_id = "B1.6"  # type: ignore[attr-defined]
check_b1_7.check_id = "B1.7"  # type: ignore[attr-defined]
check_b1_8.check_id = "B1.8"  # type: ignore[attr-defined]

CHECKS[1] = [
    check_b1_1,
    check_b1_2,
    check_b1_3,
    check_b1_4,
    check_b1_5,
    check_b1_6,
    check_b1_7,
    check_b1_8,
]

_SK = re.compile(r"(?<![A-Za-z0-9])sk-")
RUNS_URL = BASE_URL + "runs/"
RUN_URL = BASE_URL + "runs/live-smoke/"


def _assert_no_sk(page: Page) -> None:
    html = page.content()
    assert _SK.search(html) is None, "page contains a string starting with sk-"


def check_b2_1(page: Page) -> None:
    page.goto(RUNS_URL, wait_until="load")
    page.wait_for_selector("[data-testid=runs-table]")
    row = page.locator("[data-testid=run-live-smoke]")
    assert row.count() == 1, "live smoke run is not listed"
    status = row.locator("[data-testid=run-status]").inner_text().strip()
    assert status == "finished", status


def check_b2_2(page: Page) -> None:
    page.goto(RUN_URL, wait_until="load")
    page.wait_for_selector("[data-testid=step]")
    steps = page.locator("[data-testid=step]")
    assert steps.count() >= 2, f"expected at least 2 steps, got {steps.count()}"
    names = page.locator("[data-testid=tool-name]")
    args = page.locator("[data-testid=tool-args]")
    assert names.count() >= 1, "no tool calls"
    assert names.count() == args.count(), f"names {names.count()} args {args.count()}"
    for index in range(names.count()):
        assert names.nth(index).inner_text().strip(), f"empty tool name at {index}"
        assert args.nth(index).inner_text().strip(), f"empty tool arguments at {index}"
    outputs = page.locator("[data-testid=tool-output]")
    assert outputs.count() >= 1, "no tool output"
    outputs.first.locator("summary").click()
    pre = outputs.first.locator("pre")
    pre.wait_for(state="visible")
    assert pre.inner_text().strip(), "tool output was empty"


def check_b2_3(page: Page) -> None:
    page.goto(RUN_URL, wait_until="load")
    summary = json.loads((REPO / "runs" / "live-smoke" / "summary.json").read_text(encoding="utf-8"))
    tokens = page.locator("[data-testid=token-total]").inner_text().strip()
    cost = page.locator("[data-testid=cost-total]").inner_text().strip()
    assert tokens == format_number(summary["tokens"]), tokens
    assert cost == format_number(summary["cost_usd"]), cost
    assert_data_sources(page)


def check_b2_4(page: Page) -> None:
    page.goto(RUN_URL, wait_until="load")
    bar = page.locator("[data-testid=budget-bar]")
    tokens = page.locator("[data-testid=token-total]").inner_text().strip()
    assert bar.get_attribute("aria-valuenow") == tokens, bar.get_attribute("aria-valuenow")
    assert bar.get_attribute("aria-valuemax") == "500000", bar.get_attribute("aria-valuemax")


def check_b2_5(page: Page) -> None:
    page.goto(RUN_URL, wait_until="load")
    _assert_no_sk(page)
    page.goto(RUNS_URL, wait_until="load")
    _assert_no_sk(page)
    page.goto(RUN_URL, wait_until="load")


check_b2_1.check_id = "B2.1"  # type: ignore[attr-defined]
check_b2_2.check_id = "B2.2"  # type: ignore[attr-defined]
check_b2_3.check_id = "B2.3"  # type: ignore[attr-defined]
check_b2_4.check_id = "B2.4"  # type: ignore[attr-defined]
check_b2_5.check_id = "B2.5"  # type: ignore[attr-defined]

CHECKS[2] = [check_b2_1, check_b2_2, check_b2_3, check_b2_4, check_b2_5]


_START = {
    0: (BASE_URL, "[data-testid=toolchain-table]", "index"),
    1: (BASE_URL + "demo/", "[data-testid=matrix]", "demo"),
    2: (RUNS_URL, "[data-testid=runs-table]", "runs"),
}


def _open(browser, width: int, height: int, url: str, ready: str):
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
    page.goto(url, wait_until="load")
    page.wait_for_selector(ready)
    return page, state


def run(phase: int) -> list[str]:
    evidence = REPO / "docs" / "evidence" / f"phase-{phase}"
    evidence.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    checks = CHECKS[phase]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            start_url, ready, shot = _START[phase]
            for width, height, tag in VIEWPORTS:
                page, state = _open(browser, width, height, start_url, ready)
                try:
                    page.screenshot(path=str(evidence / f"{shot}-{tag}.png"), full_page=True)
                    if phase == 1 and tag == "1280":
                        page.locator("[data-testid=matrix]").screenshot(
                            path=str(evidence / "demo-matrix-1280.png")
                        )
                    if phase == 2:
                        page.goto(RUN_URL, wait_until="load")
                        page.wait_for_selector("[data-testid=budget-bar]")
                        page.screenshot(path=str(evidence / f"run-{tag}.png"), full_page=True)
                        assert_clean(page, state, width)
                        page.goto(start_url, wait_until="load")
                        page.wait_for_selector(ready)
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
                    page.screenshot(path=str(evidence / f"{shot}-{tag}.png"), full_page=True)
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
