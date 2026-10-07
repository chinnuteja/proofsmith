#pragma once
#include <cstdint>
struct Quota { std::uint64_t used, limit; bool reserve(std::uint64_t amount); };
