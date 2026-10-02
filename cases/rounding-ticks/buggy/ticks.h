#pragma once

#include <cstdint>

std::int64_t to_ticks(double price, double tick);
double resting_price(double price, double tick);
