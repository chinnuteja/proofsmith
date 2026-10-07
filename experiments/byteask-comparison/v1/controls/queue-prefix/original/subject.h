#pragma once
#include <cstddef>
#include <vector>
struct Queue { std::vector<int> values; std::vector<int> take(std::size_t maximum); };
