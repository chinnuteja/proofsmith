Choose the oracles that can show the reported symptom directly. Return JSON only, with no markdown fence:

{"oracles": [...], "rationale": "...", "suspects": ["function or file names you'd look at first"]}

Rank oracles by which one gives the most direct, observable evidence for the reported symptom. Allowed values: tsan, asan_ubsan, assertion.

Use tsan for hangs, freezes, lost updates under concurrency, or reports that mention threads. Use asan_ubsan for crashes, garbage values after later updates, use of freed memory, out-of-bounds access, or numeric results that go wrong on extreme inputs (often signed overflow or another undefined behavior). Use assertion when the issue states a concrete input and the correct observable result.

Return at most two oracles. If the report does not describe an observable failure (a wrong value, a crash, a hang, or a sanitizer finding), return an empty oracles list. Do not guess a performance bug into existence.
