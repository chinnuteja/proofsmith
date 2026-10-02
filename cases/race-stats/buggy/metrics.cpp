#include "metrics.h"

void Stats::record(std::uint64_t latency_us) {
  requests_ += 1;
  latency_sum_ += latency_us;
}

std::uint64_t Stats::requests() const { return requests_; }

void WorkerPool::serve(Stats& stats, int workers, int each) {
  std::vector<std::thread> threads;
  threads.reserve(static_cast<std::size_t>(workers));
  for (int i = 0; i < workers; ++i) {
    threads.emplace_back([&stats, each] {
      for (int n = 0; n < each; ++n) {
        stats.record(100);
      }
    });
  }
  for (std::thread& thread : threads) {
    thread.join();
  }
}
