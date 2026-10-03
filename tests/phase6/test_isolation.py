from pathlib import Path

from proofsmith.sandbox import Sandbox


def test_hidden_files_environment_and_outside_writes_are_denied(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.cpp").write_text("int main() {}")
    hidden = tmp_path / "hidden-fix.txt"
    hidden.write_text("secret fix")
    outside = tmp_path / "outside.txt"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-never-leak")
    sandbox = Sandbox.create(source, "phase6-isolation")
    try:
        result = sandbox.exec(f"cat '{hidden}'; printf '%s' \"${{DEEPSEEK_API_KEY-unset}}\"", 10)
        assert "secret fix" not in result.output
        assert "test-secret-never-leak" not in result.output
        assert "unset" in result.output
        denied = sandbox.exec(f"echo bad > '{outside}'", 10)
        assert denied.exit_code != 0
        assert not outside.exists()
        sandbox.exec("echo ignored >> app.cpp; git update-index --assume-unchanged app.cpp", 10)
        assert sandbox.illegal_changes()
    finally:
        sandbox.destroy()
