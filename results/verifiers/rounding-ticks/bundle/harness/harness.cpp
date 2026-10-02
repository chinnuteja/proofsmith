#include "proofsmith_check.h"
#include "ticks.h"

int main() {
  // The issue states that an order at 0.29 with tick size 0.01
  // should rest at 0.29, but currently rests at 0.28.
  PS_CHECK(resting_price(0.29, 0.01) == 0.29);
  return 0;
}
