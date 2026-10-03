import json

from proofsmith import config
from proofsmith.report.readme import generate_readme, pointer
from proofsmith.report.site import format_number


def test_generated_numbers_resolve_to_evidence():
    generate_readme()
    for path in (config.REPO / "README.sources.json", config.REPO / "docs/send_message.sources.json"):
        for item in json.loads(path.read_text())["values"]:
            source, suffix = item["source"].split("#", 1)
            actual = pointer(json.loads((config.REPO / source).read_text()), suffix)
            assert item["rendered"] == (format_number(actual) if actual is not None else "pending")


def test_send_message_is_honest_and_short():
    generate_readme()
    text = (config.REPO / "docs/send_message.md").read_text()
    assert len(text.split()) <= 120
    assert "__" not in text
    summary = config.RESULTS / "summary.json"
    if not summary.exists() or not json.loads(summary.read_text())["complete"]:
        assert "Draft only" in text
    elif json.loads(summary.read_text())["tracks"]["B"]["verdict"] == "KILL_OR_RETHINK":
        assert "negative" in text


def test_company_claims_cite_verified_entries():
    generate_readme()
    ledger = (config.REPO / "docs/claims.md").read_text()
    for path in (config.REPO / "README.md", config.REPO / "docs/send_message.md"):
        for paragraph in path.read_text().split("\n\n"):
            if "ByteAsk" in paragraph:
                assert "C4" in paragraph or "C5" in paragraph
                assert "C4 VERIFIED" in ledger and "C5 VERIFIED" in ledger
            assert not any(f"U{i}" in paragraph for i in range(1, 5))
