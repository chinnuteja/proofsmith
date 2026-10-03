#include "match.h"

#include <chrono>
#include <cstdio>
#include <string>

int main() {
  // This is the classic pathological case for a naive substring search:
  // a long text of all 'a's and a needle that matches until its final
  // character.  An O(n*m) matcher needs quadratic time here.  A linear
  // matcher (e.g. KMP / two-way) finishes this size in milliseconds.
  constexpr int text_size = 400'000;
  constexpr int needle_size = text_size / 2;

  std::string text(text_size, 'a');
  std::string needle(needle_size, 'a');
  needle.push_back('b');

  auto start = std::chrono::steady_clock::now();
  bool found = contains_text(text, needle);
  auto stop = std::chrono::steady_clock::now();

  double elapsed_ms =
      std::chrono::duration<double, std::milli>(stop - start).count();

  std::printf("contains_text took %.3f ms (text=%zu, needle=%zu)\n",
              elapsed_ms, text.size(), needle.size());
  std::fflush(stdout);

  if (found) {
    std::fprintf(stderr, "unexpected match for a non-occurring needle\n");
    return 1;
  }

  // The fixed matcher is linear.  Give the test a very generous upper
  // bound so it is stable on slow CI machines, while still failing on the
  // quadratic matcher: 400k/200k takes multiple seconds currently.
  constexpr double kMaxMatcherMs = 1000.0;
  if (elapsed_ms > kMaxMatcherMs) {
    std::fprintf(stderr,
                 "matcher is pathologically slow: %.3f ms for a %d-byte text "
                 "and %d-byte needle\n",
                 elapsed_ms, text_size, needle_size);
    return 1;
  }

  return 0;
}
