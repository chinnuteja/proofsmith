# Phase 0 log
## Result
GATE 0: PASS

```
== pytest tests/phase0..phase0
.....                                                                    [100%]
5 passed in 8.48s
== no case-specific prompt tuning
check_no_tuning: OK
== browser gate
/mnt/c/Users/Profile 1/ByteAskEval/site/index.html
serve: OK
BROWSER 0: PASS
GATE 0: PASS
```

## What was built
- `.gitattributes`, `.gitignore`: LF for source files, CRLF for `*.ps1`, generated dirs ignored, `.env` ignored
- `pyproject.toml`: package `proofsmith`, dev extras, `live` and `slow` markers
- `scripts/ws.ps1`: PowerShell bridge into `~/proofsmith`
- `scripts/setup_wsl.sh`, `scripts/setup_root.sh`: venv, editable install, Playwright, `gh`, `universal-ctags`
- `scripts/gate.sh`, `scripts/check_no_tuning.sh`, `scripts/browser_gate.sh`, `scripts/browser_gate.py`, `scripts/serve.sh`: phase gate, tuning grep, static server, Playwright checks
- `proofsmith/config.py`: global-constraint constants and `.env` load without printing it
- `proofsmith/oracles/variants.py`: `plain`, `asan_ubsan`, `tsan`, `coverage`
- `proofsmith/toolchain.py`: `doctor()` compiles six probes under `~/psw/probes` and writes fixtures
- `proofsmith/cli.py`: `proofsmith doctor`, `proofsmith report build`
- `proofsmith/runtime/proofsmith_check.h`: `PS_CHECK`
- `proofsmith/report/`: toolchain page, sticky table, status pills, `data-source` values
- `tests/probes/`: six sanitizer probes; `tests/fixtures/sanitizer/`: captured compiler output
- `tests/phase0/`: config, doctor, and site tests
- `docs/interfaces.md`: Contracts section; `docs/claims.md`: the Phase 0 claim ledger only
- `results/toolchain.json`: clang 18.1.3 and six passing probes
- `docs/evidence/phase-0/`: browser screenshots

## Browser checks
- B0.1: PASS. `/` loads and the title is `Proofsmith`.
- B0.2: PASS. The toolchain table has 6 body rows. Every row has `.pill-pass`. Observed kind equals expected kind on each row (`asan:heap-buffer-overflow`, `asan:heap-use-after-free`, `ubsan:signed-integer-overflow`, `tsan:data-race`, `tsan:lock-order-inversion`, `assert`).
- B0.3: PASS. `[data-testid=clang-version]` reads `Ubuntu clang version 18.1.3 (1ubuntu1)`, which contains `clang version 18`. `data-source` is `results/toolchain.json#/clang_version` and matches the JSON.
- B0.4: PASS. Each row has a `raw output` details element. Opening lock-order shows a monospace report containing `lock-order-inversion`.
- Screenshots reviewed after the passing gate. Probe names stay on one line. Kind names wrap on hyphens. The open lock-order report is a wrapped monospace block in the report column, with no page-level horizontal overflow at 1280 or 390. Mobile layout is stacked cards.
- Screenshots: `docs/evidence/phase-0/index-1280.png`, `docs/evidence/phase-0/index-390.png`, `docs/evidence/phase-0/B0.1-1280.png`, `docs/evidence/phase-0/B0.1-390.png`, `docs/evidence/phase-0/B0.2-1280.png`, `docs/evidence/phase-0/B0.2-390.png`, `docs/evidence/phase-0/B0.3-1280.png`, `docs/evidence/phase-0/B0.3-390.png`, `docs/evidence/phase-0/B0.4-1280.png`, `docs/evidence/phase-0/B0.4-390.png`
- Layer B: no browser tool available

## Spend
- Ledger before: $0.00  after: $0.00  phase ceiling: $0.00
- No DeepSeek call. `proofsmith ledger status` does not exist until Phase 2.

## Deviations from plan
- `tests/probes/heap_overflow.cpp` does not write `a[8] = 1` in `main`. A direct store, built as `asan_ubsan`, was reported by UBSan object-size and never by ASan. First gate failure (`.\scripts\ws.ps1 scripts/gate.sh 0`):

```
AssertionError: assert 'ERROR: AddressSanitizer' in '/home/chinnu/psw/probes/heap_overflow.cpp:5:3: runtime error: store to address 0x503000000060 with insufficient space for an object of type '\''int'\'' ... SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior /home/chinnu/psw/probes/heap_overflow.cpp:5:3'
```

  `-fno-sanitize-recover=undefined` stops the process on that UBSan check. The write now goes through `poke(int*, int)`, marked `noinline` and `optnone`, which still stores one past `new int[8]`. Final observed kind is `asan:heap-buffer-overflow`.
- `tests/probes/check_fail.cpp` installs a `SIGABRT` handler that prints a backtrace. Bare `PS_CHECK(1 + 1 == 3)` plus `abort()` produced 77 bytes, under the test's 200-byte floor. Measured before the handler:

```
== check_fail.txt bytes 77
PROOFSMITH_CHECK_FAILED /home/chinnu/psw/probes/check_fail.cpp:4: 1 + 1 == 3
```

  The check is still `PS_CHECK(1 + 1 == 3)`. The fixture is now 636 bytes, contains `/psw/probes/`, and does not contain `/mnt/c/`.
- Coverage `ldflags` are `-fprofile-instr-generate -fcoverage-mapping`. The plan states those as the coverage compile flags and only says sanitizer variants repeat `-fsanitize=...` on the link line. Coverage is not built in this phase.

## Open issues for the orchestrator
- Layer B was not run here. Open `/` and expand two raw outputs.
- Screenshots show `git unknown`. The gate built the site before this commit, so `git rev-parse --short HEAD` had nothing to print. A rebuild after the tag will show the short sha.
- The plan said the disk had 950 GB free. `dir` of this repo reported `13,668,237,312 bytes free` on C:. Phase 0 installs fit. Check WSL `df` before later phases clone real repositories.
- Decide whether the heap-overflow helper and the check-fail backtrace should stay. The tests were not marked xfail; the gate passes with both.
