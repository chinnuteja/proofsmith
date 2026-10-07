#include "subject.h"
std::int64_t notional(std::int32_t price, std::int32_t quantity) {
  return std::int64_t(price) * quantity;
}
