#include "subject.h"
#include "proofsmith_check.h"
int main() {
  Queue q{{10,20,30}};
  bool ok = q.take(2) == std::vector<int>{10,20} && q.values == std::vector<int>{30};
  ok = q.take(0).empty() && q.values == std::vector<int>{30} && ok;
  ok = q.take(1) == std::vector<int>{30} && q.values.empty() && ok;
  PS_CHECK(ok);
}
