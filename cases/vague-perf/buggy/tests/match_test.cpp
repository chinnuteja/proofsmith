#include "match.h"

int main() {
  if (!contains_text("abcdef", "cde")) {
    return 1;
  }
  if (contains_text("abcdef", "xyz")) {
    return 1;
  }
  if (!contains_text("", "")) {
    return 1;
  }
  return 0;
}
