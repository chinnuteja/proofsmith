from pathlib import Path

import pytest

from proofsmith.datasets.schema import BuildRecipe
from proofsmith.eval.alignment import changed_functions
from proofsmith.freeze import TamperError, freeze
from proofsmith.oracles.builds import build_key


def test_cache_key_includes_recipe_and_custom_script(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "source.cpp").write_text("int x;")
    script = tmp_path / "build.sh"
    script.write_text("echo first")
    recipe = BuildRecipe(system="custom", custom_script=str(script))
    first = build_key(repo, "plain", recipe, repo)
    script.write_text("echo changed")
    assert build_key(repo, "plain", recipe, repo) != first
    changed = recipe.model_copy(update={"jobs": 1})
    assert build_key(repo, "plain", changed, repo) != build_key(repo, "plain", recipe, repo)


def test_diff_context_does_not_change_neighbouring_function(tmp_path):
    (tmp_path / "app.cpp").write_text("int untouched() { return 0; }\n\nint changed() {\n  return 1;\n}\n")
    diff = "--- a/app.cpp\n+++ b/app.cpp\n@@ -1,5 +1,5 @@\n int untouched() { return 0; }\n \n int changed() {\n-  return 1;\n+  return 2;\n }\n"
    assert [r.name for r in changed_functions(tmp_path, diff)] == ["changed"]


def test_freezing_cannot_follow_symlink_to_hidden_host_file(tmp_path):
    repo = tmp_path / "repo"
    harness = repo / "proofsmith_harness"
    harness.mkdir(parents=True)
    hidden = tmp_path / "hidden-fix"
    hidden.write_text("must never be copied")
    (harness / "escape").symlink_to(hidden)
    with pytest.raises(TamperError, match="symlink"):
        freeze(repo, {}, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()
