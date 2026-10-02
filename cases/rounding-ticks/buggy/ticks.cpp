#include "ticks.h"

std::int64_t to_ticks(double price, double tick) {
  return static_cast<std::int64_t>(price / tick);
}

double resting_price(double price, double tick) {
  return static_cast<double>(to_ticks(price, tick)) * tick;
}
