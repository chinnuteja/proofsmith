#include "order_book.h"

#include <utility>

namespace orderd {

OrderBook::OrderBook(std::int64_t per_account_limit) : limit_(per_account_limit) {}

bool OrderBook::add(const Order& o) {
  const std::int64_t notional = o.price_ticks * o.qty;
  {
    std::lock_guard<std::mutex> risk(risk_mtx_);
    if (exposure_[o.account] + notional > limit_) {
      return false;
    }
    exposure_[o.account] += notional;
  }
  {
    std::lock_guard<std::mutex> book(book_mtx_);
    orders_.insert_or_assign(o.id, o);
  }
  return true;
}

bool OrderBook::cancel(std::uint64_t order_id) {
  std::lock_guard<std::mutex> book(book_mtx_);
  auto it = orders_.find(order_id);
  if (it == orders_.end()) return false;
  const Order o = it->second;
  orders_.erase(it);
  std::lock_guard<std::mutex> risk(risk_mtx_);
  exposure_[o.account] -= o.price_ticks * o.qty;
  return true;
}

std::size_t OrderBook::risk_sweep() {
  std::lock_guard<std::mutex> risk(risk_mtx_);
  std::lock_guard<std::mutex> book(book_mtx_);
  std::unordered_map<std::string, std::int64_t> recomputed;
  for (const auto& [id, o] : orders_) recomputed[o.account] += o.price_ticks * o.qty;
  std::size_t breaches = 0;
  for (const auto& [acct, v] : recomputed)
    if (v > limit_) ++breaches;
  exposure_ = std::move(recomputed);
  return breaches;
}

std::int64_t OrderBook::exposure(const std::string& account) const {
  std::lock_guard<std::mutex> risk(risk_mtx_);
  auto it = exposure_.find(account);
  if (it == exposure_.end()) return 0;
  return it->second;
}

std::size_t OrderBook::resting() const {
  std::lock_guard<std::mutex> book(book_mtx_);
  return orders_.size();
}

}  // namespace orderd
