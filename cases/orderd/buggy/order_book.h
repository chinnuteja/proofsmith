#pragma once

#include <cstdint>
#include <map>
#include <mutex>
#include <string>
#include <unordered_map>

namespace orderd {

enum class Side { Buy, Sell };

struct Order {
  std::uint64_t id;
  std::string account;
  Side side;
  std::int64_t price_ticks;
  std::int64_t qty;
};

class OrderBook {
 public:
  explicit OrderBook(std::int64_t per_account_limit);
  bool add(const Order& o);             // reserve exposure (risk_mtx_), then rest the order (book_mtx_); never nested
  bool cancel(std::uint64_t order_id);  // BUG: holds book_mtx_, then takes risk_mtx_
  std::size_t risk_sweep();             // risk thread: BUG: holds risk_mtx_, then takes book_mtx_
  std::int64_t exposure(const std::string& account) const;
  std::size_t resting() const;

 private:
  mutable std::mutex book_mtx_;
  mutable std::mutex risk_mtx_;
  std::map<std::uint64_t, Order> orders_;                   // guarded by book_mtx_
  std::unordered_map<std::string, std::int64_t> exposure_;  // guarded by risk_mtx_
  std::int64_t limit_;
};

}  // namespace orderd
