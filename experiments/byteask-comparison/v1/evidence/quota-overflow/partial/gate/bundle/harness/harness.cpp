#include "subject.h"
#include "proofsmith_check.h"
#include <limits>
int main() {
  const auto m = std::numeric_limits<std::uint64_t>::max();
  Quota overflow{m - 3, m}, valid{0, 100}, empty{0, 0};
  bool ok = !overflow.reserve(10) && overflow.used == m - 3;
  ok = valid.reserve(75) && valid.used == 75 && ok;
  ok = empty.reserve(0) && empty.used == 0 && ok;
  PS_CHECK(ok);
}
