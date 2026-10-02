#include "pricing.h"

#include <cstdint>

int main() {
  // The reported bug: very large order price/quantity overflow the
  // std::int32_t multiplication in notional(). 100000 * 100000 = 10^10,
  // which cannot be represented in a 32-bit signed integer.
  const std::int32_t px = 100000;
  const std::int32_t qty = 100000;
  const volatile std::int32_t result = notional(px, qty);
  (void)result;
  return 0;
}
