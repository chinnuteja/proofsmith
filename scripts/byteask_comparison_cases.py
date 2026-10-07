"""Fresh authored C++ fixtures. Controls are never agent-visible.

These are synthetic boundary cases, not an upstream benchmark or evidence of a
ByteAsk win. Independent judges cover inputs beyond the supplied regression check.
"""
from pathlib import Path
import json

CASE_IDS = ["quota-overflow", "frame-length", "expiry-boundary", "queue-prefix", "notional-width"]

COMMON_CMAKE = """cmake_minimum_required(VERSION 3.16)
project(subject LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_library(subject STATIC subject.cpp)
target_include_directories(subject PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
enable_testing()
add_executable(smoke smoke.cpp)
target_link_libraries(smoke PRIVATE subject)
add_test(NAME smoke COMMAND smoke)
"""
BUILD_SH = """#!/usr/bin/env bash
set -euo pipefail
"$PS_CXX" $PS_CXXFLAGS -I"$PS_INCLUDE" -I"$PS_REPO" \\
  "$PS_REPO/proofsmith_harness/harness.cpp" "$PS_BUILD_DIR/libsubject.a" \\
  $PS_LDFLAGS -o "$PS_OUT/harness"
"""
CHECK_HEADER = '#include "subject.h"\n#include "proofsmith_check.h"\n'
JUDGE_HEADER = """#include "subject.h"
#include <iostream>
static unsigned checked = 0, failures = 0;
static void check(bool ok) { ++checked; if (!ok) ++failures; }
static int finish() {
  std::cout << "{\\\"checked\\\":" << checked << ",\\\"failures\\\":" << failures << "}\\n";
  return failures ? 1 : 0;
}
"""

CASES = {
"quota-overflow": {
"issue": "A quota reservation near UINT64_MAX is accepted even though it exceeds the limit. Reject any amount greater than remaining capacity without changing used; valid reservations including zero must succeed. State starts with used <= limit. Keep the API and normal behavior.",
"header": """#pragma once
#include <cstdint>
struct Quota { std::uint64_t used, limit; bool reserve(std::uint64_t amount); };
""",
"buggy": """#include "subject.h"
bool Quota::reserve(std::uint64_t amount) {
  if (used + amount > limit) return false;
  used += amount;
  return true;
}
""",
"fixed": """#include "subject.h"
bool Quota::reserve(std::uint64_t amount) {
  if (amount > limit - used) return false;
  used += amount;
  return true;
}
""",
"partial": """#include "subject.h"
bool Quota::reserve(std::uint64_t amount) {
  if (amount > limit / 2) return false;
  if (used + amount > limit) return false;
  used += amount;
  return true;
}
""",
"smoke": 'int main() { Quota q{2, 10}; return !(q.reserve(3) && q.used == 5); }\n',
"check": """#include <limits>
int main() {
  const auto m = std::numeric_limits<std::uint64_t>::max();
  Quota overflow{m - 3, m}, valid{0, 100}, empty{0, 0};
  bool ok = !overflow.reserve(10) && overflow.used == m - 3;
  ok = valid.reserve(75) && valid.used == 75 && ok;
  ok = empty.reserve(0) && empty.used == 0 && ok;
  PS_CHECK(ok);
}
""",
"judge": """#include <limits>
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
"""},
"frame-length": {
"issue": "The decoder says a six-byte buffer contains a complete frame whose four-byte big-endian header declares 65538 payload bytes. It must return true only when the whole declared payload is available after the header. Empty payloads are valid; short headers are incomplete. Payload lengths are 32-bit unsigned values; do not introduce a smaller maximum.",
"header": """#pragma once
#include <cstdint>
#include <vector>
bool complete_frame(const std::vector<std::uint8_t>& bytes);
""",
"buggy": """#include "subject.h"
bool complete_frame(const std::vector<std::uint8_t>& bytes) {
  if (bytes.size() < 4) return false;
  std::uint32_t length = (std::uint32_t(bytes[0]) << 24) | (std::uint32_t(bytes[1]) << 16)
                       | (std::uint32_t(bytes[2]) << 8) | bytes[3];
  return bytes.size() >= 4 + static_cast<std::uint16_t>(length);
}
""",
"fixed": """#include "subject.h"
bool complete_frame(const std::vector<std::uint8_t>& bytes) {
  if (bytes.size() < 4) return false;
  std::uint32_t length = (std::uint32_t(bytes[0]) << 24) | (std::uint32_t(bytes[1]) << 16)
                       | (std::uint32_t(bytes[2]) << 8) | bytes[3];
  return bytes.size() - 4 >= length;
}
""",
"partial": """#include "subject.h"
bool complete_frame(const std::vector<std::uint8_t>& bytes) {
  if (bytes.size() < 4) return false;
  std::uint32_t length = (std::uint32_t(bytes[0]) << 24) | (std::uint32_t(bytes[1]) << 16)
                       | (std::uint32_t(bytes[2]) << 8) | bytes[3];
  return length <= 32768 && bytes.size() - 4 >= length;
}
""",
"smoke": 'int main() { return !complete_frame({0, 0, 0, 2, 10, 20}); }\n',
"check": """int main() {
  std::vector<std::uint8_t> large(70004, 0); large[1] = 1; large[2] = 17; large[3] = 112;
  bool ok = !complete_frame({0, 1, 0, 2, 10, 20});
  ok = complete_frame(large) && complete_frame({0,0,0,0}) && ok;
  PS_CHECK(ok);
}
""",
"judge": """#include <array>
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
"""},
"expiry-boundary": {
"issue": "A cache entry is returned exactly at its expiry timestamp. The interval of validity ends at expires: return its value only while now < expires. Expired entries must not be returned, and lookups must not mutate stored state. Timestamps are unsigned 64-bit values.",
"header": """#pragma once
#include <cstdint>
#include <optional>
struct Entry { int value; std::uint64_t expires; std::optional<int> lookup(std::uint64_t now) const; };
""",
"buggy": """#include "subject.h"
std::optional<int> Entry::lookup(std::uint64_t now) const {
  if (now > expires) return std::nullopt;
  return value;
}
""",
"fixed": """#include "subject.h"
std::optional<int> Entry::lookup(std::uint64_t now) const {
  if (now >= expires) return std::nullopt;
  return value;
}
""",
"partial": """#include "subject.h"
std::optional<int> Entry::lookup(std::uint64_t now) const {
  if (now == expires) return std::nullopt;
  return value;
}
""",
"smoke": 'int main() { Entry e{42, 100}; return !(e.lookup(50) == 42); }\n',
"check": """int main() {
  Entry e{42, 100};
  bool ok = !e.lookup(100) && !e.lookup(101) && e.lookup(99) == 42;
  PS_CHECK(ok);
}
""",
"judge": """#include <limits>
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
"""},
"queue-prefix": {
"issue": "Taking at most two orders from a queue of three loses the unconsumed third order. take(maximum) must remove and return exactly the oldest min(maximum, size) orders, in order. A zero-sized take leaves the queue unchanged; repeated takes must neither duplicate nor lose orders.",
"header": """#pragma once
#include <cstddef>
#include <vector>
struct Queue { std::vector<int> values; std::vector<int> take(std::size_t maximum); };
""",
"buggy": """#include "subject.h"
#include <algorithm>
std::vector<int> Queue::take(std::size_t maximum) {
  auto n = std::min(maximum, values.size());
  std::vector<int> result(values.begin(), values.begin() + n);
  values.clear();
  return result;
}
""",
"fixed": """#include "subject.h"
#include <algorithm>
std::vector<int> Queue::take(std::size_t maximum) {
  auto n = std::min(maximum, values.size());
  std::vector<int> result(values.begin(), values.begin() + n);
  values.erase(values.begin(), values.begin() + n);
  return result;
}
""",
"partial": """#include "subject.h"
#include <algorithm>
std::vector<int> Queue::take(std::size_t maximum) {
  auto n = std::min(maximum, values.size());
  std::vector<int> result(values.begin(), values.begin() + n);
  if (n == 2) values.erase(values.begin(), values.begin() + n);
  else values.clear();
  return result;
}
""",
"smoke": 'int main() { Queue q{{10,20}}; return !(q.take(5) == std::vector<int>{10,20} && q.values.empty()); }\n',
"check": """int main() {
  Queue q{{10,20,30}};
  bool ok = q.take(2) == std::vector<int>{10,20} && q.values == std::vector<int>{30};
  ok = q.take(0).empty() && q.values == std::vector<int>{30} && ok;
  ok = q.take(1) == std::vector<int>{30} && q.values.empty() && ok;
  PS_CHECK(ok);
}
""",
"judge": """#include <algorithm>
#include <deque>
#include <limits>
int main() {
  for (unsigned size = 0; size < 13; ++size) for (unsigned maximum = 0; maximum < 16; ++maximum) {
    Queue q; std::deque<int> ref;
    for (unsigned i = 0; i < size; ++i) { q.values.push_back(i * 7 - 12); ref.push_back(i * 7 - 12); }
    for (unsigned step = 0; step < 5; ++step) {
      std::vector<int> expected;
      const auto count = std::min<std::size_t>(maximum, ref.size());
      for (std::size_t i = 0; i < count; ++i) { expected.push_back(ref.front()); ref.pop_front(); }
      check(q.take(maximum) == expected);
      check(q.values == std::vector<int>(ref.begin(), ref.end()));
    }
  }
  Queue q{{1,2,3}};
  check(q.take(std::numeric_limits<std::size_t>::max()) == std::vector<int>{1,2,3});
  check(q.values.empty());
  return finish();
}
"""},
"notional-width": {
"issue": "notional(50000, 50000) returns a negative value instead of 2500000000. Compute the exact signed product of any two signed 32-bit inputs in the signed 64-bit return value. Negative quantities and negative prices are valid; do not clamp, take absolute values, or narrow before multiplication.",
"header": """#pragma once
#include <cstdint>
std::int64_t notional(std::int32_t price, std::int32_t quantity);
""",
"buggy": """#include "subject.h"
std::int64_t notional(std::int32_t price, std::int32_t quantity) {
  return price * quantity;
}
""",
"fixed": """#include "subject.h"
std::int64_t notional(std::int32_t price, std::int32_t quantity) {
  return std::int64_t(price) * quantity;
}
""",
"partial": """#include "subject.h"
std::int64_t notional(std::int32_t price, std::int32_t quantity) {
  return std::uint64_t(std::uint32_t(price)) * std::uint32_t(quantity);
}
""",
"smoke": 'int main() { return notional(10, 20) != 200; }\n',
"check": """int main() {
  bool ok = notional(50000, 50000) == 2500000000LL;
  ok = notional(-70000, 30000) == -2100000000LL && ok;
  ok = notional(0, -100000) == 0 && ok;
  PS_CHECK(ok);
}
""",
"judge": """#include <array>
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
"""}}


def write_cases(destination: Path):
    destination.mkdir(parents=True, exist_ok=False)
    for case_id in CASE_IDS:
        item = CASES[case_id]
        base = destination / case_id
        files = {
            "original/CMakeLists.txt": COMMON_CMAKE,
            "original/subject.h": item["header"],
            "original/subject.cpp": item["buggy"],
            "original/smoke.cpp": '#include "subject.h"\n' + item["smoke"],
            "original/issue.md": item["issue"] + "\n",
            "supplied/harness.cpp": CHECK_HEADER + item["check"],
            "supplied/build.sh": BUILD_SH,
            "hidden/judge.cpp": JUDGE_HEADER + item["judge"],
            "controls/fixed.cpp": item["fixed"],
            "controls/partial.cpp": item["partial"],
        }
        for relative, content in files.items():
            path = base / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        instance = {"schema": "proofsmith.instance/1", "id": case_id, "track": "micro",
                    "source": {"kind": "dir", "path": str(base / "original")},
                    "issue": {"title": case_id, "body": item["issue"], "rewritten": False, "mentions_fix": False},
                    "build": {"system": "cmake", "test_command": "ctest --output-on-failure"}}
        (base / "instance.json").write_text(json.dumps(instance, indent=2) + "\n", encoding="utf-8")
