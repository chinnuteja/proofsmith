#include "subject.h"
bool Quota::reserve(std::uint64_t amount) {
  if (used + amount > limit) return false;
  used += amount;
  return true;
}
