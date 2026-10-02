Oracle: a direct assertion. Call finish with variant plain.

Encode the issue's expected behavior with PS_CHECK(...) from proofsmith_check.h, on the project's public API, with concrete values from the issue. One focused check beats many.

Include the header as #include "proofsmith_check.h". The check must fail on the current code because the reported behavior is wrong, and it must pass once that behavior is fixed. Use the inputs and the correct observable result stated in the issue. If the issue does not state both, abstain. Do not invent timing limits, iteration counts, or expected speeds.
