#include "subject.h"
#include <algorithm>
std::vector<int> Queue::take(std::size_t maximum) {
  auto n = std::min(maximum, values.size());
  std::vector<int> result(values.begin(), values.begin() + n);
  values.clear();
  return result;
}
