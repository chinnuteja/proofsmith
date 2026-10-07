#include "subject.h"
std::optional<int> Entry::lookup(std::uint64_t now) const {
  if (now > expires) return std::nullopt;
  return value;
}
