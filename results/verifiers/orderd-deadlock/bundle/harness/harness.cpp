#include "order_book.h"

#include <thread>

int main() {
  orderd::OrderBook book(1000);

  // One resting order so cancel() has real work to do and must update risk
  // exposure after removing the order.
  orderd::Order resting{1, "alice", orderd::Side::Buy, 10, 5};
  book.add(resting);

  // Drive the two production paths that freeze orderd. cancel() takes
  // book_mtx_ then risk_mtx_, while risk_sweep() takes risk_mtx_ then
  // book_mtx_. The reported production hang always has a cancel in flight
  // while the periodic risk sweep is running.
  std::thread canceller([&book] { book.cancel(1); });
  std::thread sweeper([&book] { book.risk_sweep(); });

  canceller.join();
  sweeper.join();

  return 0;
}
