#include <climits>
#include <cstdio>

int main(int argc, char**) {
  int v = argc;
  int x = INT_MAX + v;
  std::printf("%d\n", x);
  return 0;
}
