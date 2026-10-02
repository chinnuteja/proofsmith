Oracle: ThreadSanitizer. Call finish with variant tsan.

TSan reports unordered accesses even when the timing is benign, and reports lock-order inversions even if no deadlock happens. Prefer harnesses that perform the conflicting operations in separate threads with no extra synchronization between them, rather than stress loops. For "sometimes hangs/freezes", look for two code paths acquiring the same locks in different orders and drive both paths once each; sequential threads are fine because TSan records the lock-order graph. Do not introduce races in the harness itself: harness-only reports have no application frames and are rejected.

Drive the project's own functions. Do not add sleeps to try to force a hang. One pass through each conflicting path is enough.
