#include "price_cache.h"

#include <iostream>

int main() {
  PriceCache cache(1);

  cache.put("A", 1.5);

  // Hold a reference to the cached price, as the public API allows.
  const double& held = cache.get("A");

  // Fill the cache with a new symbol.  This evicts "A" and frees the
  // PriceCache node that "held" points to.
  cache.put("B", 2.5);

  // Reading the previously read price is now a use-after-free.  With
  // AddressSanitizer this is reported and the process aborts; without it,
  // the value may be garbage.
  std::cout << held << '\n';
  if (held != 1.5) {
    return 1;
  }
  return 0;
}
