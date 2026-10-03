#include <cstdio>

int main() {
#if REPRO_COMPILES
  std::puts("repro compiled");
  return 0;
#else
  std::puts("repro failed to compile");
  return 1;
#endif
}
