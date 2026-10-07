#include "subject.h"
bool Quota::reserve(std::uint64_t amount) {
  if (amount > limit - used) return false;
  used += amount;
  return true;
}
