#include "subject.h"
#include "proofsmith_check.h"
int main() {
  bool ok = notional(50000, 50000) == 2500000000LL;
  ok = notional(-70000, 30000) == -2100000000LL && ok;
  ok = notional(0, -100000) == 0 && ok;
  PS_CHECK(ok);
}
