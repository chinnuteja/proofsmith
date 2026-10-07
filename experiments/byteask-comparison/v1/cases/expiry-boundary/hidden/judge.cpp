#include "subject.h"
#include <iostream>
static unsigned checked = 0, failures = 0;
static void check(bool ok) { ++checked; if (!ok) ++failures; }
static int finish() {
  std::cout << "{\"checked\":" << checked << ",\"failures\":" << failures << "}\n";
  return failures ? 1 : 0;
}
#include <limits>
#include <vector>
int main() {
  const auto m = std::numeric_limits<std::uint64_t>::max();
  const std::vector<std::uint64_t> times = {0, 1, 2, 17, 88, 999, m/2, m-1, m};
  for (auto expiry : times) for (auto now : times) for (int value : {-77, 0, 51}) {
    const Entry e{value, expiry};
    const auto got = e.lookup(now);
    check(got.has_value() == (now < expiry));
    check(!got || *got == value);
    check(e.value == value && e.expires == expiry);
  }
  return finish();
}
