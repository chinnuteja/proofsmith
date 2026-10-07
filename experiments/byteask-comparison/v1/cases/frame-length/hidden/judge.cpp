#include "subject.h"
#include <iostream>
static unsigned checked = 0, failures = 0;
static void check(bool ok) { ++checked; if (!ok) ++failures; }
static int finish() {
  std::cout << "{\"checked\":" << checked << ",\"failures\":" << failures << "}\n";
  return failures ? 1 : 0;
}
#include <array>
int main() {
  for (unsigned size = 0; size < 4; ++size) check(!complete_frame(std::vector<std::uint8_t>(size)));
  const std::array<std::uint32_t, 10> lengths = {0, 1, 3, 19, 255, 4096, 32769, 65535, 65536, 80001};
  for (auto length : lengths) for (int delta : {-1, 0, 1, 7}) {
    const long payload = static_cast<long>(length) + delta;
    if (payload < 0) continue;
    std::vector<std::uint8_t> bytes(4 + payload, 17);
    bytes[0] = length >> 24; bytes[1] = length >> 16; bytes[2] = length >> 8; bytes[3] = length;
    check(complete_frame(bytes) == (static_cast<unsigned long>(payload) >= length));
  }
  for (auto length : {0x7fffffffu, 0x80000000u, 0xffffffffu}) {
    std::vector<std::uint8_t> bytes = {std::uint8_t(length >> 24), std::uint8_t(length >> 16),
                                    std::uint8_t(length >> 8), std::uint8_t(length), 0};
    check(!complete_frame(bytes));
  }
  return finish();
}
