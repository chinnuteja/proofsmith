#include "order_book.h"

#include <iostream>

namespace {

int g_fails = 0;

void check(bool cond, const char* text) {
  if (!cond) {
    std::cerr << "FAIL " << text << "\n";
    ++g_fails;
  }
}

}  // namespace

int main() {
  orderd::OrderBook book(1000);
  orderd::Order order{1, "alice", orderd::Side::Buy, 10, 5};
  check(book.add(order), "add resting order");
  check(book.resting() == 1, "one resting order");
  check(book.exposure("alice") == 50, "exposure after add");
  check(book.cancel(1), "cancel resting order");
  check(book.resting() == 0, "book empty after cancel");
  check(book.exposure("alice") == 0, "exposure released");
  check(!book.cancel(1), "second cancel misses");
  orderd::Order too_big{2, "alice", orderd::Side::Sell, 100, 20};
  check(!book.add(too_big), "over-limit add rejected");
  check(book.resting() == 0, "rejected add does not rest");
  check(book.exposure("alice") == 0, "rejected add does not reserve");
  return g_fails == 0 ? 0 : 1;
}
