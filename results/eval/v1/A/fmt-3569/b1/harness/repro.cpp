#define FMT_HEADER_ONLY

#include <fmt/core.h>

#include <string>
#include <vector>

// Regression test for formatting elements of std::vector<bool>.
//
// std::vector<bool> is specialized to store bits, so operator[] returns a
// proxy reference (std::_Bit_reference on libstdc++, or the equivalent on
// libc++).  fmt currently rejects that proxy type, which makes even a simple
// fmt::print("{}", myVector[0]) fail to compile.  Once fmt recognizes the
// proxy reference (or maps it to bool), the if constexpr branch below becomes
// active and verifies that the value is actually formatted as "false".
int main() {
  std::vector<bool> values = {false};
  using reference_type = decltype(values[0]);

  if constexpr (fmt::is_formattable<reference_type>::value) {
    auto formatted = fmt::format("{}", values[0]);
    return formatted == "false" ? 0 : 2;
  } else {
    // The type is not formattable yet: report the bug.
    return 1;
  }
}
