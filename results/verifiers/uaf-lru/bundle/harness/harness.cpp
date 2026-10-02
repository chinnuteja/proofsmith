#include "price_cache.h"
#include "proofsmith_check.h"

namespace {

__attribute__((noinline)) double read_price(const double& price) {
  // Force a real load through the reference so ASan observes the
  // heap-use-after-free when the cached node has been evicted.
  volatile double observed = price;
  return observed;
}

}  // namespace

int main() {
  PriceCache cache(1);

  cache.put("AAA", 10.0);

  // Hold the reference returned by get(), just like the reported callers do.
  const double& held = cache.get("AAA");

  // Filling the cache with a new symbol evicts (deletes) the node behind
  // `held`. A correct cache would keep that value alive or return by value.
  cache.put("BBB", 20.0);

  // This read is invalid in the current implementation: it loads from the
  // freed Node::price storage.
  const double observed = read_price(held);

  // If the read somehow succeeds on a non-sanitized build, check the
  // reported expectation: the previously read price must remain unchanged.
  PS_CHECK(observed == 10.0);

  return 0;
}
