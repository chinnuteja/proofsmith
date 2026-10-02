#pragma once

#include <cstdint>
#include <thread>
#include <vector>

class Stats {
 public:
  void record(std::uint64_t latency_us);
  std::uint64_t requests() const;

 private:
  std::uint64_t requests_ = 0;
  std::uint64_t latency_sum_ = 0;
};

class WorkerPool {
 public:
  static void serve(Stats& stats, int workers, int each);
};
