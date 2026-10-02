#include "ticks.h"

int main() {
  if (to_ticks(10.0, 1.0) != 10) {
    return 1;
  }
  if (to_ticks(8.0, 2.0) != 4) {
    return 1;
  }
  if (resting_price(10.0, 1.0) != 10.0) {
    return 1;
  }
  return 0;
}
