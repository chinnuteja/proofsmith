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
  const std::vector<std::uint64_t> v = {0, 1, 2, 7, 31, 99, 128, 65536, m/2, m/2+1, m-7, m-1, m};
  for (auto limit : v) for (auto used : v) if (used <= limit) for (auto amount : v) {
    Quota q{used, limit};
    const bool expected = static_cast<unsigned __int128>(used) + amount <= limit;
    const bool actual = q.reserve(amount);
    check(actual == expected);
    check(q.used == (expected ? used + amount : used));
  }
  return finish();
}
