"""Bundle freeze and tamper detection."""

from __future__ import annotations

import pytest

from proofsmith.freeze import TamperError, freeze, load_bundle


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "order_book.cpp").write_text("int x;\n", encoding="utf-8", newline="\n")
    harness = repo / "proofsmith_harness"
    harness.mkdir()
    (harness / "harness.cpp").write_text("int main(){return 0;}\n", encoding="utf-8", newline="\n")
    (harness / "build.sh").write_text("#!/bin/sh\ntrue\n", encoding="utf-8", newline="\n")
    return repo


def test_freeze_round_trip_and_stable_tree_hash(tmp_path):
    repo = _repo(tmp_path)
    meta = {"schema": "proofsmith.verifier/1", "system": "reference", "instance_id": "t"}
    first = freeze(repo, meta, tmp_path / "b1")
    second = freeze(repo, meta, tmp_path / "b2")
    loaded = load_bundle(first)
    again = load_bundle(second)
    assert loaded["files"]["harness/harness.cpp"]
    assert loaded["buggy_tree_sha256"] == again["buggy_tree_sha256"]
    assert loaded["files"] == again["files"]


def test_edited_harness_byte_is_tamper(tmp_path):
    repo = _repo(tmp_path)
    bundle = freeze(repo, {"system": "reference"}, tmp_path / "bundle")
    cpp = bundle / "harness" / "harness.cpp"
    cpp.write_bytes(cpp.read_bytes().replace(b"i", b"j", 1))
    with pytest.raises(TamperError):
        load_bundle(bundle)


def test_added_file_is_tamper(tmp_path):
    repo = _repo(tmp_path)
    bundle = freeze(repo, {"system": "reference"}, tmp_path / "bundle")
    (bundle / "harness" / "extra.cpp").write_text("int y;\n", encoding="utf-8", newline="\n")
    with pytest.raises(TamperError):
        load_bundle(bundle)
