// Reproduction for: "A timed-out DNS lookup can crash the client"
//
// The test forces the fallback (thread-based) getaddrinfo_with_timeout()
// implementation and uses the linker's --wrap facility to simulate a DNS
// lookup that outlives the DNS timeout.  On timeout the current implementation
// detaches the resolver thread while the thread still holds references to
// variables on the function's stack.  When the simulated lookup finishes a few
// seconds later, that detached thread touches the dead stack and ASan aborts
// the process.
//
// On a fixed implementation the background lookup may still be running, but it
// must not touch the returned function's stack.  The process then sleeps long
// enough for the simulated lookup to finish and exits successfully.

// Include the C++ standard library headers used by httplib.h while the
// compiler's default feature-test macros (notably _GNU_SOURCE) are intact.
// libstdc++'s <locale> machinery needs _GNU_SOURCE, so we can only undefine it
// after these headers have been processed.  This is what forces httplib.h onto
// the fallback path instead of the Linux getaddrinfo_a() path.
#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <cctype>
#include <climits>
#include <condition_variable>
#include <csignal>
#include <cstring>
#include <exception>
#include <functional>
#include <iomanip>
#include <iostream>
#include <list>
#include <map>
#include <memory>
#include <mutex>
#include <random>
#include <regex>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <utility>

#include <netdb.h>
#include <sys/socket.h>

#include <chrono>

#undef _GNU_SOURCE

// Select the non-blocking getaddrinfo implementation in httplib.h.  With
// _GNU_SOURCE undefined on Linux, this is the thread-based fallback.
#define CPPHTTPLIB_USE_NON_BLOCKING_GETADDRINFO 1

#include "httplib.h"

extern "C" const char *__asan_default_options() {
  return "detect_stack_use_after_return=1:halt_on_error=1";
}

extern "C" int __wrap_getaddrinfo(const char *node, const char * /*service*/,
                                  const struct addrinfo * /*hints*/,
                                  struct addrinfo **res) {
  if (node != nullptr &&
      std::string(node) == "proofsmith-slow-dns.invalid") {
    // Simulate a DNS lookup that is still running when the timeout fires.
    std::this_thread::sleep_for(std::chrono::seconds(3));
    *res = nullptr;
    return EAI_AGAIN;
  }

  // The test only performs the single lookup above.
  *res = nullptr;
  return EAI_FAIL;
}

int main() {
  struct addrinfo hints;
  std::memset(&hints, 0, sizeof(hints));
  hints.ai_family = AF_UNSPEC;
  hints.ai_socktype = SOCK_STREAM;

  struct addrinfo *result = nullptr;

  // One second timeout against a lookup that takes three seconds.  The call
  // must return (with an error) before the lookup finishes.
  auto rc = httplib::detail::getaddrinfo_with_timeout(
      "proofsmith-slow-dns.invalid", "80", &hints, &result, 1);
  (void)rc;

  // Keep the process alive until the detached resolver thread has definitely
  // finished.  On the buggy code ASan aborts in that thread; on fixed code the
  // extra time is harmless and main returns 0.
  std::this_thread::sleep_for(std::chrono::seconds(5));

  return 0;
}
