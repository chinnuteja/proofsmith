#include <vector>
#include <fmt/core.h>

int main() {
  std::vector<bool> myVector = {false};
  fmt::print("{}", myVector[0]);
}
