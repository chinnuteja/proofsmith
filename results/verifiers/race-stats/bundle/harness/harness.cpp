#include "metrics.h"

int main() {
  Stats stats;
  // Two or more worker threads call Stats::record with no synchronization
  // between them, which is the lost-update path described in the issue.
  WorkerPool::serve(stats, 4, 1000);
  return 0;
}
