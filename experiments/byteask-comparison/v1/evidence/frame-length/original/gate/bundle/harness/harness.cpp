#include "subject.h"
#include "proofsmith_check.h"
int main() {
  std::vector<std::uint8_t> large(70004, 0); large[1] = 1; large[2] = 17; large[3] = 112;
  bool ok = !complete_frame({0, 1, 0, 2, 10, 20});
  ok = complete_frame(large) && complete_frame({0,0,0,0}) && ok;
  PS_CHECK(ok);
}
