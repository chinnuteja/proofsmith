#include "metrics.h"

int main() {
  Stats stats;
  WorkerPool::serve(stats, 1, 10);
  if (stats.requests() != 10) {
    return 1;
  }
  stats.record(5);
  if (stats.requests() != 11) {
    return 1;
  }
  return 0;
}
