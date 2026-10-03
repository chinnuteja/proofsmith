#include "ticks.h"

#include <cmath>
#include <cstdlib>

int main() {
  const double price = 0.29;
  const double tick = 0.01;
  const double expected = 0.29;
  const double actual = resting_price(price, tick);

  // The reported bug: 0.29 / 0.01 computes to 28.999999999999996,
  // truncates to tick 28, and therefore rests at 0.28 instead of 0.29.
  if (std::fabs(actual - expected) > 1e-12) {
    return EXIT_FAILURE;
  }

  if (to_ticks(price, tick) != 29) {
    return EXIT_FAILURE;
  }

  return EXIT_SUCCESS;
}
