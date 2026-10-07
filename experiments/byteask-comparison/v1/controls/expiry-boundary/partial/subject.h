#pragma once
#include <cstdint>
#include <optional>
struct Entry { int value; std::uint64_t expires; std::optional<int> lookup(std::uint64_t now) const; };
