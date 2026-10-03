import json

import pytest

from proofsmith.eval import protocol


@pytest.fixture
def versions(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol.config, 'REPO', tmp_path)
    monkeypatch.setattr(protocol.config, 'RESULTS', tmp_path / 'results')
    path = tmp_path / 'docs/protocol.json'
    path.parent.mkdir()
    previous = {'id': 'v1'}
    path.write_text(json.dumps(previous))
    return tmp_path, path, previous


def test_new_protocol_preserves_prior_observations_and_hash(versions):
    root, path, previous = versions
    result = root / 'results/eval/v1/B/one/b0.json'
    result.parent.mkdir(parents=True)
    result.write_text('{"old": true}')
    (result.parent / 'b0.attempt.json').write_text('{}')
    frozen = protocol.freeze_protocol(path, protocol_id='v2')
    assert frozen['id'] == 'v2'
    assert result.read_text() == '{"old": true}'
    archive = root / 'docs/protocol-history' / (protocol.fingerprint(previous) + '.json')
    assert json.loads(archive.read_text()) == previous
    protocol.validate_protocol(frozen)


def test_unresolved_attempt_prevents_protocol_change(versions):
    root, path, previous = versions
    attempt = root / 'results/eval/v1/B/one/b0.attempt.json'
    attempt.parent.mkdir(parents=True)
    attempt.write_text('{}')
    with pytest.raises(RuntimeError, match='unresolved'):
        protocol.freeze_protocol(path, protocol_id='v2')
    assert json.loads(path.read_text()) == previous


def test_artifact_protocol_id_cannot_be_reused(versions):
    root, path, previous = versions
    used = root / 'results/eval/v2/B/one/b0.json'
    used.parent.mkdir(parents=True)
    used.write_text('{}')
    with pytest.raises(RuntimeError, match='already has artifacts'):
        protocol.freeze_protocol(path, protocol_id='v2')
    assert json.loads(path.read_text()) == previous


def test_protocol_id_cannot_escape_result_directory(versions):
    _, path, _ = versions
    with pytest.raises(ValueError):
        protocol.freeze_protocol(path, protocol_id='../other')
