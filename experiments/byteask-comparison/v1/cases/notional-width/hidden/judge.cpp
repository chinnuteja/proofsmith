#include "subject.h"
#include <iostream>
static unsigned checked = 0, failures = 0;
static void check(bool ok) { ++checked; if (!ok) ++failures; }
static int finish() {
  std::cout << "{\"checked\":" << checked << ",\"failures\":" << failures << "}\n";
  return failures ? 1 : 0;
}
#include <array>
#include <limits>
int main() {
  const std::array<std::int32_t, 14> inputs = {std::numeric_limits<std::int32_t>::min(), -100003,
    -65537, -46341, -12, -1, 0, 1, 13, 46341, 65537, 100003,
    std::numeric_limits<std::int32_t>::max()-1, std::numeric_limits<std::int32_t>::max()};
  for (auto p : inputs) for (auto q : inputs) {
    const __int128 exact = static_cast<__int128>(p) * q;
    check(static_cast<__int128>(notional(p, q)) == exact);
  }
  return finish();
}
