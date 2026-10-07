#include "subject.h"
std::int64_t notional(std::int32_t price, std::int32_t quantity) {
  return std::uint64_t(std::uint32_t(price)) * std::uint32_t(quantity);
}
