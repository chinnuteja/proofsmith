#include "metrics.h"

#include <cstdint>
#include <iostream>

int main() {
  constexpr int kWorkers = 16;
  constexpr int kEach = 20000;

  Stats stats;
  WorkerPool::serve(stats, kWorkers, kEach);

  const std::uint64_t expected =
      static_cast<std::uint64_t>(kWorkers) * static_cast<std::uint64_t>(kEach);
  const std::uint64_t got = stats.requests();

  if (got != expected) {
    std::cerr << "request counter mismatch: expected " << expected << ", got "
              << got << '\n';
    return 1;
  }

  return 0;
}
