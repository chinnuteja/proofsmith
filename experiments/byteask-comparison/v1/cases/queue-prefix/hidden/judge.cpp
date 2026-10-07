#include "subject.h"
#include <iostream>
static unsigned checked = 0, failures = 0;
static void check(bool ok) { ++checked; if (!ok) ++failures; }
static int finish() {
  std::cout << "{\"checked\":" << checked << ",\"failures\":" << failures << "}\n";
  return failures ? 1 : 0;
}
#include <algorithm>
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
