"""Write the 12 selected Multi-SWE-bench C++ instances. Run inside WSL."""

from __future__ import annotations

import json
from pathlib import Path

from proofsmith.datasets.check import separation_problems

ROOT = Path.home() / "psw" / "multiswe"
DEST = Path.home() / "proofsmith" / "data" / "trackA"
URL = "https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench"
REVISION = "56ff018c04a38e27ada1e9d0a6d5839a51f88f0d"

SELECTED = (
    "fmtlib__fmt-4310",
    "fmtlib__fmt-4057",
    "fmtlib__fmt-3734",
    "fmtlib__fmt-3713",
    "fmtlib__fmt-3569",
    "nlohmann__json-2332",
    "nlohmann__json-1769",
    "nlohmann__json-807",
    "nlohmann__json-708",
    "nlohmann__json-4537",
    "catchorg__Catch2-2288",
    "yhirose__cpp-httplib-1765",
)

HEADER_BUILD = "scripts/tracka_header_build.sh"
BUILD = {
    "fmt": {
        "system": "cmake",
        "cmake_args": [
            "-DFMT_DOC=OFF",
            "-DFMT_TEST=OFF",
            "-DFMT_INSTALL=OFF",
            "-DFMT_FUZZ=OFF",
            "-DFMT_MODULE=OFF",
        ],
        "custom_script": None,
    },
    "json": {"system": "custom", "cmake_args": [], "custom_script": HEADER_BUILD},
    "Catch2": {"system": "custom", "cmake_args": [], "custom_script": HEADER_BUILD},
    "cpp-httplib": {
        "system": "cmake",
        "cmake_args": [
            "-DHTTPLIB_COMPILE=ON",
            "-DHTTPLIB_TEST=OFF",
            "-DHTTPLIB_INSTALL=OFF",
            "-DHTTPLIB_REQUIRE_OPENSSL=OFF",
            "-DHTTPLIB_USE_OPENSSL_IF_AVAILABLE=OFF",
            "-DHTTPLIB_REQUIRE_MBEDTLS=OFF",
            "-DHTTPLIB_USE_MBEDTLS_IF_AVAILABLE=OFF",
            "-DHTTPLIB_USE_BROTLI_IF_AVAILABLE=OFF",
            "-DHTTPLIB_USE_ZLIB_IF_AVAILABLE=OFF",
            "-DHTTPLIB_USE_ZSTD_IF_AVAILABLE=OFF",
        ],
        "custom_script": None,
    },
}


def _load() -> dict[str, dict]:
    found: dict[str, dict] = {}
    for path in sorted(ROOT.glob("*_dataset.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            found[item["instance_id"]] = item
    return found


def _files(diff: str) -> list[str]:
    names: list[str] = []
    for line in diff.splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split()
        if parts and parts[-1].startswith("b/"):
            names.append(parts[-1][2:])
    return names


def _source_files(paths: list[str]) -> list[str]:
    suffixes = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".ipp", ".inl"}
    kept = []
    for path in paths:
        if "test" in path.lower():
            continue
        if Path(path).suffix.lower() in suffixes:
            kept.append(path)
    return kept


def _issue(item: dict) -> tuple[str, str, str | None]:
    issues = item.get("resolved_issues") or []
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict) and (issue.get("title") or issue.get("body")):
                title = str(issue.get("title") or item.get("title") or "").strip()
                body = str(issue.get("body") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
                number = issue.get("number")
                url = None
                if number is not None:
                    url = f"https://github.com/{item['org']}/{item['repo']}/issues/{number}"
                return title, body, url
    title = str(item.get("title") or "").strip()
    body = str(item.get("body") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    number = item.get("number")
    url = f"https://github.com/{item['org']}/{item['repo']}/pull/{number}" if number else None
    return title, body, url


def _short(repo: str) -> str:
    if repo == "cpp-httplib":
        return "httplib"
    return repo


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    records = _load()
    missing = [name for name in SELECTED if name not in records]
    if missing:
        raise SystemExit(f"missing records: {missing}")
    instances = DEST / "instances"
    hidden = DEST / "hidden"
    instances.mkdir(parents=True, exist_ok=True)
    hidden.mkdir(parents=True, exist_ok=True)
    for name in SELECTED:
        item = records[name]
        repo = str(item["repo"])
        org = str(item["org"])
        number = int(item["number"])
        instance_id = f"{_short(repo)}-{number}"
        diff = str(item.get("fix_patch") or "").replace("\r\n", "\n").replace("\r", "\n")
        if not diff.endswith("\n"):
            diff += "\n"
        title, body, issue_url = _issue(item)
        base = item.get("base") or {}
        commit = str(base.get("sha") or "")
        if not commit:
            raise SystemExit(f"{name} has no base sha")
        paths = _files(diff)
        fix_files = _source_files(paths) or paths
        f2p = item.get("f2p_tests") or {}
        dev_tests = sorted(str(key) for key in f2p) if isinstance(f2p, dict) else []
        mentions_fix = False
        rewritten = False
        visible = {
            "schema": "proofsmith.instance/1",
            "id": instance_id,
            "track": "A",
            "source": {
                "kind": "git",
                "url": f"https://github.com/{org}/{repo}",
                "commit": commit,
            },
            "issue": {
                "title": title,
                "body": body,
                "url": issue_url,
                "rewritten": False,
                "mentions_fix": False,
            },
            "build": {
                "system": BUILD[repo]["system"],
                "cmake_args": BUILD[repo]["cmake_args"],
                "targets": [],
                "jobs": 4,
                "custom_script": BUILD[repo]["custom_script"],
                "test_command": None,
            },
        }
        hidden_doc = {
            "schema": "proofsmith.hidden/1",
            "id": instance_id,
            "fixed": {"kind": "patch", "path": f"data/trackA/hidden/{instance_id}.fix.diff"},
            "bug_class": "behavioral",
            "fix_files": fix_files,
            "dev_tests": dev_tests,
            "notes": f"Multi-SWE-bench {name} at dataset revision {REVISION}.",
        }
        visible_text = json.dumps(visible, indent=2) + "\n"
        problems = separation_problems(
            visible_text,
            f"{title}\n{body}",
            "",
            diff,
            fix_files,
            False,
        )
        if any(item.startswith("issue text contains fix file") for item in problems):
            mentions_fix = True
            visible["issue"]["mentions_fix"] = True
        leaked_lines = [item for item in problems if "fix diff line" in item]
        if leaked_lines:
            rewritten = True
            visible["issue"]["rewritten"] = True
            for line in diff.splitlines():
                if len(line) >= 20 and line in visible["issue"]["body"]:
                    visible["issue"]["body"] = visible["issue"]["body"].replace(line, "")
        visible["issue"]["mentions_fix"] = mentions_fix
        visible["issue"]["rewritten"] = rewritten
        visible_text = json.dumps(visible, indent=2) + "\n"
        problems = separation_problems(
            visible_text,
            f"{visible['issue']['title']}\n{visible['issue']['body']}",
            "",
            diff,
            fix_files,
            mentions_fix,
        )
        if problems:
            raise SystemExit(f"{instance_id} separation failed: {problems}")
        _write(instances / f"{instance_id}.json", visible_text)
        _write(hidden / f"{instance_id}.json", json.dumps(hidden_doc, indent=2) + "\n")
        _write(hidden / f"{instance_id}.fix.diff", diff)
        print(f"wrote {instance_id} files={len(fix_files)} dev_tests={len(dev_tests)} mentions_fix={mentions_fix}")
    source = {
        "url": URL,
        "revision": REVISION,
        "fetched": "2026-10-02",
        "card": "https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench",
    }
    _write(DEST / "source.json", json.dumps(source, indent=2) + "\n")
    _write(
        DEST / "SOURCE.md",
        "\n".join(
            [
                "# Track A source",
                "",
                "Dataset card: https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench",
                "",
                "The card was read before any field was used. C++ instances live in the `cpp/` JSONL files",
                "(Catch2, fmt, nlohmann/json, simdjson, cpp-httplib). Each record has `org`, `repo`, `number`,",
                "`title`, `body`, `base.sha` (the buggy commit), `resolved_issues`, `fix_patch`, and `f2p_tests`.",
                "",
                f"Revision: {REVISION}",
                "",
                "Fetched: 2026-10-02",
                "",
                "Twelve instances were selected across fmt, nlohmann/json, Catch2, and cpp-httplib,",
                "preferring small patches and projects that configure with CMake.",
                "Builds are local clang builds. There is no Docker step.",
                "",
            ]
        ),
    )
    print("instances", len(SELECTED))


if __name__ == "__main__":
    main()
