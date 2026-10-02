# Track A source

Dataset card: https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench

The card was read before any field was used. C++ instances live in the `cpp/` JSONL files
(Catch2, fmt, nlohmann/json, simdjson, cpp-httplib). Each record has `org`, `repo`, `number`,
`title`, `body`, `base.sha` (the buggy commit), `resolved_issues`, `fix_patch`, and `f2p_tests`.

Revision: 56ff018c04a38e27ada1e9d0a6d5839a51f88f0d

Fetched: 2026-10-02

Twelve instances were selected across fmt, nlohmann/json, Catch2, and cpp-httplib,
preferring small patches and projects that configure with CMake.
Builds are local clang builds. There is no Docker step.
