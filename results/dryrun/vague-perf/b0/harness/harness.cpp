#include "match.h"

#include <chrono>
#include <iostream>
#include <string>

int main() {
  // Adversarial input for the matcher: the haystack is all 'a's and the
  // needle is a long run of 'a's followed by a single 'b'.  A matcher that
  // degenerates to quadratic behaviour (for example libstdc++'s
  // std::string::find on this input) takes seconds here, while a linear-time
  // matcher finishes in milliseconds.
  const std::string::size_type n = 500000;
  std::string text(n, 'a');
  std::string needle(n / 2, 'a');
  needle.push_back('b');

  const auto start = std::chrono::steady_clock::now();
  const bool found = contains_text(text, needle);
  const auto end = std::chrono::steady_clock::now();

  const double elapsed_ms =
      std::chrono::duration<double, std::milli>(end - start).count();
  std::cerr << "matcher elapsed: " << elapsed_ms << " ms\n";

  // The expected answer is false; a wrong result is not what this test is
  // about, but check it anyway to avoid silently accepting a broken matcher.
  if (found) {
    std::cerr << "unexpected match\n";
    return 2;
  }

  // A linear-time matcher completes this case in well under a second on the
  // reference machine.  The current quadratic matcher takes multiple seconds.
  if (elapsed_ms > 1000.0) {
    std::cerr << "matcher is too slow\n";
    return 1;
  }

  return 0;
}
