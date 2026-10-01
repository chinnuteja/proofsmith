# Proofsmith

**Turns a C/C++ bug report into a frozen, validated failing check before the coding agent touches the code.**

> ByteAsk writes the fix. Proofsmith decides in advance what "fixed" means, and says "I couldn't" when it can't.

---

## 1. The gap in ByteAsk's loop

ByteAsk's loop today: edit → compile → sanitizers → debugger → your tests → diff.

"All green" means *nothing we ran found a problem*. If no existing test exercises the reported bug, green says nothing about that bug. The agent both decides what is wrong and decides whether it fixed it. That is circular.

Proofsmith covers exactly that case, and only that case:

- **An existing test already fails on the bug:** Proofsmith is skipped.
- **Nothing reproduces the bug:** Proofsmith runs before any patch.

## 2. The thesis (this is what has to be true)

Many C/C++ bugs have no assertion-shaped oracle. The observable evidence is a toolchain event.

| Bug shape | Oracle Proofsmith constructs |
|---|---|
| Wrong behavior | Assertion in a new test target |
| Lifetime / bounds | ASan report from a targeted harness |
| Undefined behavior | UBSan report |
| Data race | TSan race report. TSan flags accesses that are not ordered by happens-before, even when the timing happens to be benign, so detection is far more stable than stress-until-crash. |
| "Sometimes deadlocks" | TSan **lock-order-inversion** report. It fires on the inverted lock order itself, so the program never has to actually hang. |
| Intermittent native failure | Hand off to ByteAsk's existing rr chaos recording. Proofsmith does not rebuild it. |

**The claim to test:** give both agents the same model, the same tools and the same budget. An agent that explicitly selects and constructs the toolchain oracle, and validates it statistically, produces more *aligned* fail→pass checks than an agent told "reproduce first, sanitizers are available". The gap should be largest on lifetime and concurrency bugs.

If a prompt alone gets the same result, Proofsmith is dead. The evaluation is designed to answer that.

## 3. Why ByteAsk specifically

- **Their homepage promise is verification:** "Writes C++. Proves it compiles, runs, and passes."
- **Their own homepage demo is a deadlock in an order book,** fixed with `std::scoped_lock`. That is exactly a lock-order inversion. A TSan lock-order check would have been a deterministic failing check for that bug before any patch existed.
- **Their hiring page says it outright:** deciding whether a C/C++ patch is actually correct is an open problem. It also lists tool selection "including knowing when the honest answer is 'we don't know'".
- **The CEO's rule:** "use AI to write the deterministic tool", then let the compiler, sanitizers, gdb and tests do the reviewing. Proofsmith is the AI writing the reviewer.
- **The CTO owns the harness, benchmarks and model training.** Every accepted verifier produces a fail→pass eval instance and training signal for him as a byproduct.
- **It fits their rr work.** rr chaos mode can replay a failure once you have a program that fails 1 time in 20. **Proofsmith builds that program from the bug report.** It complements their tool rather than competing with it.

## 4. Prior art

| Area | Existing work | What it does *not* do |
|---|---|---|
| Issue → reproduction test | SWT-Bench, Otter, Aegis, REAgent, SWE-Tester, Multi-SWT-Bench (Sep 2026: C++ has the lowest success) | Judges with ordinary test pass/fail. No sanitizer or concurrency oracles. The C++ instances are mostly behavioral library bugs. |
| Sanitizer PoC generation for C/C++ | ARVO, SEC-bench, PAGENT, FuzzingBrain, SyzHarness (kernel) | Starts from a fuzzer crash report with a fuzz harness already provided. Mostly memory bugs. No human-written issue, no concurrency, no gate for a coding agent. |
| Synthetic environments | SWE-smith, SWE-Gym, R2E-Gym | Mostly Python. Aimed at training data, not at a live pre-patch gate. |

**The gap, as far as I found:** start from a *human-written* C/C++ issue with *no harness*. Choose the toolchain oracle. Handle concurrency nondeterminism with a statistical acceptance rule. Freeze the result as a gate for a coding agent.

This is a combination of known pieces, not a new concept. The novelty claim lives or dies on Track B results (section 7).

## 5. The four contributions (all measurable)

1. **Oracle selection and construction.**
   - Classify the issue.
   - Build the right instrumented variant of the project's own targets. ASan+UBSan and TSan need separate builds because they cannot be combined.
   - Write a harness as a **new** target. Never edit existing tests.

2. **Flake-aware acceptance rule.**
   - **At runtime** (the fixed version does not exist yet): accept V only if it fails ≥ k of n runs on the buggy code with a **stable failure signature**. The signature is sanitizer fault type plus the top 3 application frames.
   - **At evaluation time** (hidden fixed commit): V must also fail 0 of n runs on the fixed code, with n = 20.

3. **Alignment check (evaluator-side).**
   - Fail→pass alone can test the wrong thing.
   - A result counts as *aligned* only if the failure evidence (sanitizer frames or the failing assertion's call path) touches the functions changed by the developer's real fix.
   - Report raw F→P **and** aligned F→P.

4. **Abstention.**
   - Return `NO VERIFIER: <reason>` instead of manufacturing a weak check.
   - Measure abstention precision: when it abstains, did the baseline also fail?

## 6. v0 architecture

```
issue text + buggy repo            (fixed commit is NEVER visible)
        │
        ▼
build once → compile_commands.json
        │
        ▼
classify oracle(s): assertion | ASan+UBSan | TSan
        │
        ▼
build instrumented variant(s) of the project's own targets
        │
        ▼
write harness as a NEW target (existing tests untouched)
        │
        ▼
run n times → extract failure signature (fault type + top-3 app frames)
        │
        ├── fails ≥k/n with a stable signature → ACCEPT → freeze
        │                                        (hash harness + build flags)
        └── otherwise → retry within budget → ABSTAIN with reason
```

## 7. Evaluation

**Hidden evaluator:** Proofsmith sees only the issue and the buggy commit. The evaluator alone runs V against the fixed commit.

### Track A: breadth (public, comparable)
- **Source:** Multi-SWE-bench C++, 129 instances from fmt, nlohmann/json, simdjson, Catch2 and cpp-httplib, with Docker images and fail→pass tests. Use Multi-SWT-Bench's C++ split instead if its data is released.
- **Expectation:** almost all behavioral bugs.
- **Purpose:** show that Proofsmith does **not hurt** ordinary cases. It is not where the thesis gets proven.

### Track B: the thesis (hand-curated)
- **Size:** 12–20 real C/C++ **lifetime and concurrency** fixes, each with a human-written issue.
- **Sources:** merged PRs or commits mentioning data race, TSan, use-after-free, deadlock or lock order. Candidates: rocksdb, leveldb, spdlog, concurrentqueue, taskflow, oneTBB, cpp-httplib, libuv, redis.
- **Build check:** verify that both the buggy and fixed commits build under clang with the sanitizers before accepting an instance.
- **Leakage rule:** use the linked *issue* text only. If only a PR description exists, rewrite it to symptoms only and disclose that you did.

### Baselines (same model, token budget and wall clock)
- **B0:** "Write a reproduction test for this issue."
- **B1 (the one that matters):** the same agent with the same tools, sanitizers included, explicitly told to reproduce first and allowed to use sanitizers.
- **Proofsmith must beat B1, not B0.**

### Metrics
- Raw F→P and **aligned F→P**, per track.
- Per-oracle breakdown: which oracle produced each success.
- Abstention precision.
- Flake rate on the fixed commit (0/20 required).
- Median wall-clock and cost per instance.

### Kill criteria
- **Track B:** if aligned F→P is not clearly above B1, kill or rethink. At about 15 instances, anything under roughly +20 points is noise.
- **Track A:** if Proofsmith is more than about 5 points below B1, the oracle step is hurting ordinary cases. Restrict it to issues classified as lifetime or concurrency.

## 8. First 7 days (smallest honest version)

| Day | Work |
|---|---|
| 1–2 | Curate Track B: 10–15 instances whose buggy and fixed commits both build under clang with ASan and TSan. This is the hardest step, so do it first. |
| 3 | Track A: pick 10–15 Multi-SWE-bench C++ instances from the prebuilt images. |
| 4 | Run B0 and B1 on both tracks. Record everything. |
| 5–6 | Proofsmith v0 with three oracles (assertion, ASan+UBSan, TSan), the acceptance rule, signature extraction and abstention. |
| 7 | Evaluator run, alignment check, then a README with one table, three worked cases (one sanitizer win, one plain-test win, one honest failure) and a one-command reproduction. |

**Not in week 1:** patch generation, freeze-and-patch gating, rr, ByteAsk integration, a second model, standards-to-check, dashboards, reinforcement learning.

## 9. Weeks 2–4 (only if week 1 passes the kill criteria)

- **Week 2, the gate experiment.**
  - Let a coding agent patch each Track B issue.
  - Count patches that **pass the repo's existing tests but fail the frozen V**.
  - Check each one against the hidden developer tests. This separates true catches from over-strict verifiers. Report both.
- **Week 3.**
  - Hand intermittent cases to rr chaos.
  - Grow Track B to 30–40 instances.
  - Wrap Proofsmith as a pre-step around `byteask exec`, or as a tool the agent can call.
- **Week 4.**
  - Clean write-up and one-command evaluation.
  - Open-source Track B as a small "C/C++ lifetime & concurrency reproduction" benchmark. The CTO can use it directly.

## 10. What to send (fill in only real numbers)

> Built Proofsmith: before an agent patches a C/C++ bug, it builds a toolchain-backed failing check (ASan/UBSan/TSan, including TSan lock-order checks for "sometimes deadlocks") and freezes it.
> On __ real lifetime/concurrency fixes, with the same model and tools as a strong "reproduce first" baseline: __ vs __ aligned fail→pass checks. On __ ordinary C++ bugs: __ vs __, so no regression.
> __ agent patches passed the repo's tests but failed the frozen check; __ of those were real misses.
> It abstained on __ and was right to __ times. Repo + one-command eval: <link>

## 11. Risks, stated up front

- Track B is small, so the statistics will be weak. Say so in the write-up.
- TSan can report false positives with uninstrumented dependencies and custom synchronization (standalone fences, some lock-free code). You will need suppressions, and you should report how many.
- Instrumented builds of big repos are slow, which caps n and the size of the dataset.
- Verifiers can be over-strict. The week 2 split between true catches and over-strict rejections measures this.
- ByteAsk may already prompt "reproduce first". B1 exists to answer exactly that objection.
- **Unverified claims:** the other analysis cited specific Multi-SWT-Bench figures (126 C++ instances, 52.5% for the best C++ configuration, ~994K LoC average C++ repo). Read the paper before quoting any of them. The 994K figure conflicts with Multi-SWE-bench's C++ repos, which range from 36K to 230K LoC.

## 12. One sentence

**Proofsmith makes a C/C++ coding agent earn its green checkmark. Before touching the code, it turns the bug report into a sanitizer- or TSan-backed check that fails on the broken program, freezes it, and refuses to guess when it can't.**
