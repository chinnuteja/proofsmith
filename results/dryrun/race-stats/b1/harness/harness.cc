#include "metrics.h"
#include "proofsmith_check.h"

#include <cstdint>

// Make ThreadSanitizer fail the process as soon as it observes the data race,
// rather than only printing a report and continuing.
extern "C" const char *__tsan_default_options() {
  return "halt_on_error=1";
}

int main() {
  constexpr int kWorkers = 12;
  constexpr int kEach = 50000;
  constexpr std::uint64_t kExpected =
      static_cast<std::uint64_t>(kWorkers) * static_cast<std::uint64_t>(kEach);

  Stats stats;
  WorkerPool::serve(stats, kWorkers, kEach);

  // After all workers have joined, every served request must have been
  // counted. The current implementation updates the counter with a non-atomic
  // read-modify-write from many threads, so some increments are lost.
  PS_CHECK(stats.requests() == kExpected);

  return 0;
}
