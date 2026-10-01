"""ToolSet rejects edits outside the harness and runs the orderd reference check."""

from __future__ import annotations

import shutil

import pytest

from proofsmith.agent.tools import ToolSet
from proofsmith.config import REPO, WORK
from proofsmith.datasets.schema import Instance
from proofsmith.sandbox import Sandbox

pytestmark = pytest.mark.slow


def test_write_guard_build_and_harness():
    instance = Instance.model_validate_json(
        (REPO / "cases" / "orderd" / "instance.json").read_text(encoding="utf-8")
    )
    sandbox = Sandbox.create(REPO / "cases" / "orderd" / "buggy", "phase2-tools-orderd")
    try:
        tools = ToolSet(sandbox, instance.build, WORK / "sandboxes" / "phase2-tools-orderd" / "work")
        original = (sandbox.repo / "order_book.cpp").read_text(encoding="utf-8")
        denied = tools.dispatch("write_file", {"path": "order_book.cpp", "content": "nope\n"})
        assert "proofsmith_harness" in denied
        assert (sandbox.repo / "order_book.cpp").read_text(encoding="utf-8") == original

        built = tools.dispatch("build_variant", {"variant": "tsan"})
        assert "ok: true" in built, built[-2000:]

        harness = sandbox.repo / "proofsmith_harness"
        reference = REPO / "cases" / "orderd" / "reference_harness"
        shutil.copyfile(reference / "harness.cpp", harness / "harness.cpp")
        shutil.copyfile(reference / "build.sh", harness / "build.sh")
        ran = tools.dispatch("run_harness", {"variant": "tsan", "n": 2})
        assert ran.count("tsan:lock-order-inversion") >= 2, ran[-2000:]
    finally:
        sandbox.destroy()
