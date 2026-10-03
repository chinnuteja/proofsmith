import json

from proofsmith import config
from proofsmith.benchmark import export_benchmark
from proofsmith.datasets.check import separation_problems


def test_export_is_separated_and_contains_runnable_evaluator(tmp_path):
    dest = export_benchmark(tmp_path / "benchmark")
    manifest = json.loads((dest / "manifest.json").read_text())
    assert manifest["instances"]
    assert (dest / "proofsmith/eval/evaluator.py").is_file()
    assert (dest / "pyproject.toml").is_file()
    assert not (dest / ".env").exists()
    for row in manifest["instances"]:
        visible_path = dest / "data/trackB/instances" / f"{row['id']}.json"
        visible_text = visible_path.read_text()
        visible = json.loads(visible_text)
        hidden = json.loads((dest / "data/trackB/hidden" / visible_path.name).read_text())
        diff = (dest / "data/trackB/hidden" / f"{row['id']}.fix.diff").read_text()
        problems = separation_problems(visible_text, visible["issue"]["body"], hidden["fixed"].get("commit", ""),
                                       diff, hidden["fix_files"], visible["issue"]["mentions_fix"])
        assert not problems, (row["id"], problems)
