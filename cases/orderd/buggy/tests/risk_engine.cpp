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
  orderd::OrderBook book(10000);
  orderd::Order first{1, "bob", orderd::Side::Buy, 25, 4};
  orderd::Order second{2, "bob", orderd::Side::Sell, 10, 3};
  check(book.add(first), "add first");
  check(book.add(second), "add second");
  check(book.risk_sweep() == 0, "sweep finds no breach");
  check(book.exposure("bob") == 130, "sweep recomputes exposure");
  check(book.resting() == 2, "sweep leaves resting orders");
  check(book.cancel(2), "cancel one order");
  check(book.risk_sweep() == 0, "sweep after cancel");
  check(book.exposure("bob") == 100, "exposure matches the remaining order");
  check(book.exposure("missing") == 0, "unknown account");
  return g_fails == 0 ? 0 : 1;
}
