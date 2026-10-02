"""Schema checks for Track B instances."""

from __future__ import annotations

import json
from pathlib import Path

from proofsmith.config import REPO
from proofsmith.datasets.schema import HiddenInstance, Instance

ROOT = REPO / "data" / "trackB"
VISIBLE_KEYS = {"schema", "id", "track", "source", "issue", "build"}


def _visible_paths() -> list[Path]:
    return sorted((ROOT / "instances").glob("*.json"))


def test_every_instance_and_hidden_validates():
    paths = _visible_paths()
    assert paths, "no Track B instances"
    ids: list[str] = []
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert set(raw) <= VISIBLE_KEYS
        instance = Instance.model_validate(raw)
        assert instance.schema_version == "proofsmith.instance/1"
        assert instance.track == "B"
        assert instance.id == path.stem
        ids.append(instance.id)
        hidden_path = ROOT / "hidden" / f"{instance.id}.json"
        assert hidden_path.is_file(), instance.id
        hidden = HiddenInstance.model_validate_json(hidden_path.read_text(encoding="utf-8"))
        assert hidden.schema_version == "proofsmith.hidden/1"
        assert hidden.id == instance.id
        assert (ROOT / "hidden" / f"{instance.id}.fix.diff").is_file()
        assert (ROOT / "raw" / f"{instance.id}.issue.json").is_file()
    assert len(ids) == len(set(ids))


def test_every_visible_id_has_a_hidden_twin():
    visible = {path.stem for path in _visible_paths()}
    hidden = {path.stem for path in (ROOT / "hidden").glob("*.json")}
    assert visible
    assert visible <= hidden
