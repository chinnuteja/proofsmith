### Harness contract (identical for every system)

- The harness lives in `proofsmith_harness/` at the repo root. Nothing outside it may be created, modified or deleted. Violations invalidate the run.
- `proofsmith_harness/build.sh` is run as `bash proofsmith_harness/build.sh` with cwd = repo root and env:
  - `PS_REPO` absolute repo path; `PS_BUILD_DIR` the project's build dir for the chosen variant; `PS_COMPILE_COMMANDS` path to `compile_commands.json`;
  - `PS_CC=clang`, `PS_CXX=clang++`, `PS_CXXFLAGS` and `PS_LDFLAGS` for the variant; `PS_INCLUDE` dir containing `proofsmith_check.h`;
  - `PS_OUT` output dir. It must produce the executable `$PS_OUT/harness` and exit 0.
- The harness is run as `$PS_OUT/harness` with no args, cwd = repo root, the variant's runtime env, and timeout `RUN_TIMEOUT_S`.
- **Fail** = non-zero exit code, a signal, or a timeout. **Pass** = exit 0 within the timeout.
