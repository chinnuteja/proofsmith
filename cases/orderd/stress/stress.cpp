#include "order_book.h"

#include <chrono>
#include <cstdint>
#include <random>
#include <thread>

int main() {
  orderd::OrderBook book(1000000000);
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(300);

  auto trader = [&](std::uint32_t seed) {
    std::mt19937 rng(seed);
    std::uniform_int_distribution<int> pick(0, 31);
    while (std::chrono::steady_clock::now() < deadline) {
      const auto id = static_cast<std::uint64_t>(pick(rng) + static_cast<int>(seed) * 100);
      orderd::Order order{id, "acct", orderd::Side::Buy, 10, 1};
      book.add(order);
      book.cancel(id);
    }
  };

  auto risk = [&] {
    while (std::chrono::steady_clock::now() < deadline) {
      book.risk_sweep();
    }
  };

  std::thread first(trader, 1);
  std::thread second(trader, 2);
  std::thread sweep(risk);
  first.join();
  second.join();
  sweep.join();
  return 0;
}
