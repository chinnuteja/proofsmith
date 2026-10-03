#include "ticks.h"

#include <cstdint>

int main() {
  const double price = 0.29;
  const double tick = 0.01;

  const std::int64_t ticks = to_ticks(price, tick);
  if (ticks != 29) {
    return 1;
  }

  const double resting = resting_price(price, tick);
  if (resting != 0.29) {
    return 2;
  }

  return 0;
}
