#include "pricing.h"

#include <cstdint>

int main() {
  volatile std::int32_t px = 100000;
  volatile std::int32_t qty = 100000;
  std::int64_t result = notional(px, qty);
  return result == 10000000000LL ? 0 : 1;
}
