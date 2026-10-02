"""Track A validates, separates, and builds. One httplib loopback check."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from proofsmith.config import REPO, WORK
from proofsmith.datasets.check import ensure_worktree
from proofsmith.datasets.schema import Instance
from proofsmith.datasets.tracka import check_tracka, list_ids, track_root
from proofsmith.sandbox import Sandbox

pytestmark = [pytest.mark.slow, pytest.mark.timeout(10800)]


def test_source_card_is_recorded():
    text = (track_root() / "SOURCE.md").read_text(encoding="utf-8")
    assert "https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench" in text
    assert re.search(r"\b[0-9a-f]{40}\b", text)


def test_twelve_instances_validate_and_build():
    report = check_tracka()
    assert report.total == 12
    assert len(report.instances) == 12
    repos = {item.repo for item in report.instances}
    assert len(repos) >= 3, repos
    for item in report.instances:
        assert item.schema_ok, item.problems
        assert item.separation_ok, item.problems
        for side in ("buggy", "fixed"):
            for variant in ("plain", "asan_ubsan"):
                assert item.builds[side][variant], f"{item.id} {side} {variant}: {item.problems}"


def test_httplib_loopback_inside_unshare():
    chosen = None
    for instance_id in list_ids():
        path = track_root() / "instances" / f"{instance_id}.json"
        instance = Instance.model_validate_json(path.read_text(encoding="utf-8"))
        if instance.source.url and instance.source.url.rstrip("/").endswith("cpp-httplib"):
            chosen = instance
            break
    assert chosen is not None, "Track A has no cpp-httplib instance"
    assert chosen.source.url and chosen.source.commit
    tree = ensure_worktree(chosen.source.url, chosen.source.commit, WORK / "tracka" / chosen.id / "buggy")
    sandbox = Sandbox.create(tree, "tracka-httplib-loopback")
    try:
        source = r"""#include "httplib.h"
#include <chrono>
#include <thread>
int main() {
  httplib::Server server;
  server.Get("/hi", [](const httplib::Request&, httplib::Response& response) {
    response.set_content("ok", "text/plain");
  });
  std::thread thread([&] { server.listen("127.0.0.1", 18081); });
  int code = 1;
  for (int attempt = 0; attempt < 50; ++attempt) {
    httplib::Client client("127.0.0.1", 18081);
    client.set_connection_timeout(1, 0);
    if (auto result = client.Get("/hi")) {
      code = result->status == 200 && result->body == "ok" ? 0 : 2;
      break;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  server.stop();
  thread.join();
  return code;
}
"""
        (sandbox.repo / "loopback.cpp").write_text(source, encoding="utf-8", newline="\n")
        compiled = subprocess.run(
            ["clang++", "-std=c++17", "-I", str(sandbox.repo), "loopback.cpp", "-pthread", "-o", "loopback"],
            cwd=sandbox.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
        assert compiled.returncode == 0, compiled.stdout
        result = sandbox.exec("./loopback", 30)
        assert result.exit_code == 0, result.output
    finally:
        sandbox.destroy()
