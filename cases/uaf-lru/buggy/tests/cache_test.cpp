#include "price_cache.h"

int main() {
  PriceCache cache(2);
  cache.put("AAA", 10.0);
  cache.put("BBB", 11.0);
  double first = cache.get("AAA");
  double second = cache.get("BBB");
  if (first != 10.0 || second != 11.0) {
    return 1;
  }
  cache.put("AAA", 12.0);
  if (cache.get("AAA") != 12.0) {
    return 1;
  }
  PriceCache small(1);
  small.put("AAA", 1.0);
  double held = small.get("AAA");
  small.put("BBB", 2.0);
  if (held != 1.0 || small.get("BBB") != 2.0) {
    return 1;
  }
  return 0;
}
