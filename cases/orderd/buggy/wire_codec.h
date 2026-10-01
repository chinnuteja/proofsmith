#pragma once

#include "order_book.h"

#include <cstddef>
#include <cstdint>
#include <vector>

namespace orderd {

std::vector<std::uint8_t> encode_order(const Order& order);
bool decode_order(const std::uint8_t* data, std::size_t size, Order& out);

}  // namespace orderd
