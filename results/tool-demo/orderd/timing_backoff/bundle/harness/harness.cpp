#include "order_book.h"

#include <thread>

int main() {
  orderd::OrderBook book(1000000);
  const orderd::Order order{1, "acct", orderd::Side::Buy, 10, 2};
  std::thread cancel_thread([&] {
    book.add(order);
    book.cancel(order.id);
  });
  cancel_thread.join();
  std::thread sweep_thread([&] { book.risk_sweep(); });
  sweep_thread.join();
  return 0;
}
