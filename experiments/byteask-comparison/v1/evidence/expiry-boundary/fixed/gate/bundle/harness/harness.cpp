#include "subject.h"
#include "proofsmith_check.h"
int main() {
  Entry e{42, 100};
  bool ok = !e.lookup(100) && !e.lookup(101) && e.lookup(99) == 42;
  PS_CHECK(ok);
}
