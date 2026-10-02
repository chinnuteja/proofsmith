#include "pricing.h"

int main() {
  if (notional(10, 5) != 50) {
    return 1;
  }
  if (notional(3, 0) != 0) {
    return 1;
  }
  if (notional(-4, 2) != -8) {
    return 1;
  }
  return 0;
}
