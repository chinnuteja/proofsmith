"""Synthetic diffs and ctags ranges."""

from __future__ import annotations

from pathlib import Path

from proofsmith.eval.alignment import align, changed_functions
from proofsmith.oracles.signature import Frame


def _source() -> str:
    lines = ["//"] * 40
    lines[7] = "int foo() {"
    for index in range(8, 19):
        lines[index] = "  int value = 1;"
    lines[19] = "}"
    lines[20] = "int baz() {"
    lines[21] = "  return 1;"
    lines[22] = "}"
    lines[24] = "int bar() {"
    for index in range(25, 39):
        lines[index] = "  int value = 2;"
    lines[39] = "}"
    return "\n".join(lines) + "\n"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.cpp").write_text(_source(), encoding="utf-8", newline="\n")
    return repo


def _names(items) -> list[str]:
    return [item.name for item in items]


def test_hunk_selects_the_enclosing_function(tmp_path: Path):
    repo = _repo(tmp_path)
    diff = """diff --git a/a.cpp b/a.cpp
--- a/a.cpp
+++ b/a.cpp
@@ -10,3 +10,3 @@
-  int value = 1;
-  int value = 1;
-  int value = 1;
+  int value = 3;
+  int value = 3;
+  int value = 3;
"""
    changed = changed_functions(repo, diff)
    assert _names(changed) == ["foo"]
    assert changed[0].start == 8
    assert changed[0].end == 20


def test_pure_insertion_selects_the_enclosing_function(tmp_path: Path):
    repo = _repo(tmp_path)
    diff = """diff --git a/a.cpp b/a.cpp
--- a/a.cpp
+++ b/a.cpp
@@ -30,0 +30,1 @@
+  int inserted = 1;
"""
    changed = changed_functions(repo, diff)
    assert _names(changed) == ["bar"]
    assert changed[0].start == 25
    assert changed[0].end == 40


def test_frame_inside_changed_function_is_strict(tmp_path: Path):
    repo = _repo(tmp_path)
    changed = changed_functions(
        repo,
        """diff --git a/a.cpp b/a.cpp
--- a/a.cpp
+++ b/a.cpp
@@ -10,3 +10,3 @@
-  int value = 1;
-  int value = 1;
-  int value = 1;
+  int value = 3;
+  int value = 3;
+  int value = 3;
""",
    )
    frame = Frame(0, "foo", str(repo / "a.cpp"), 15)
    scored = align([frame], [], changed, str(repo))
    assert scored.strict is True
    assert scored.relaxed is True
    assert scored.unknown is False
    assert scored.hits[0]["via"] == "frame"
    assert scored.hits[0]["function"] == "foo"


def test_frame_in_unchanged_function_is_only_relaxed(tmp_path: Path):
    repo = _repo(tmp_path)
    changed = changed_functions(
        repo,
        """diff --git a/a.cpp b/a.cpp
--- a/a.cpp
+++ b/a.cpp
@@ -10,3 +10,3 @@
-  int value = 1;
+  int value = 3;
""",
    )
    assert _names(changed) == ["foo"]
    frame = Frame(0, "baz", str(repo / "a.cpp"), 22)
    scored = align([frame], [], changed, str(repo))
    assert scored.strict is False
    assert scored.relaxed is True
    assert scored.unknown is False


def test_coverage_timeout_is_unknown(tmp_path: Path):
    repo = _repo(tmp_path)
    changed = changed_functions(
        repo,
        """diff --git a/a.cpp b/a.cpp
--- a/a.cpp
+++ b/a.cpp
@@ -10,3 +10,3 @@
-  int value = 1;
+  int value = 3;
""",
    )
    scored = align([], None, changed, str(repo))
    assert scored.unknown is True
    assert scored.strict is False
    assert scored.relaxed is False
