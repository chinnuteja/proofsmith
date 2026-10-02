#include "order_book.h"

#include <atomic>
#include <cstdlib>
#include <iostream>
#include <thread>
#include <vector>

int main() {
  orderd::OrderBook book(1000000000LL);

  // Pre-populate enough resting orders for cancel to have real work to do.
  for (std::uint64_t i = 1; i <= 20000; ++i) {
    orderd::Order o{i, "acct" + std::to_string(i % 100), orderd::Side::Buy,
                    static_cast<std::int64_t>(i % 50 + 1), 1};
    if (!book.add(o)) {
      std::cerr << "unexpected rejection during setup\n";
      return 2;
    }
  }

  std::atomic<bool> start{false};
  std::atomic<bool> stop{false};
  std::atomic<std::uint64_t> cancels{0};
  std::atomic<std::uint64_t> sweeps{0};

  std::thread risk([&]() {
    while (!start.load(std::memory_order_acquire)) {
    }
    while (!stop.load(std::memory_order_acquire)) {
      (void)book.risk_sweep();
      sweeps.fetch_add(1, std::memory_order_relaxed);
    }
  });

  std::thread cancel([&]() {
    while (!start.load(std::memory_order_acquire)) {
    }
    std::uint64_t next = 20001;
    while (!stop.load(std::memory_order_acquire)) {
      orderd::Order o{next, "acct" + std::to_string(next % 100),
                      orderd::Side::Buy, static_cast<std::int64_t>(next % 50 + 1),
                      1};
      (void)book.add(o);
      (void)book.cancel(next);
      ++next;
      cancels.fetch_add(1, std::memory_order_relaxed);
    }
  });

  start.store(true, std::memory_order_release);

  // Run long enough for TSan's deadlock detector to observe both lock orders.
  std::this_thread::sleep_for(std::chrono::seconds(3));
  stop.store(true, std::memory_order_release);

  risk.join();
  cancel.join();

  std::cout << "cancels=" << cancels.load() << " sweeps=" << sweeps.load() << "\n";
  return 0;
}
