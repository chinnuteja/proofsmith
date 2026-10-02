#include "price_cache.h"

int main() {
  PriceCache cache(2);

  cache.put("AAA", 10.0);
  cache.put("BBB", 11.0);

  // Hold a reference to the price returned by get(), as the API allows.
  const double& held = cache.get("AAA");

  // Fill the cache so the node backing `held` is evicted and deleted.
  cache.put("CCC", 12.0);
  cache.put("DDD", 13.0);

  // The held reference should still have the value it had when it was read.
  return held == 10.0 ? 0 : 1;
}
