#include "proofsmith_check.h"

#include <csignal>
#include <execinfo.h>
#include <unistd.h>

// abort() alone writes one line (77 bytes on this machine). The handler
// prints a backtrace so the captured report is a real stack and exceeds
// the fixture size check.
static void on_abort(int) {
  void* frames[32];
  int n = backtrace(frames, 32);
  backtrace_symbols_fd(frames, n, STDERR_FILENO);
  _exit(134);
}

static void level3() { PS_CHECK(1 + 1 == 3); }
static void level2() { level3(); }
static void level1() { level2(); }

int main() {
  std::signal(SIGABRT, on_abort);
  level1();
  return 0;
}
