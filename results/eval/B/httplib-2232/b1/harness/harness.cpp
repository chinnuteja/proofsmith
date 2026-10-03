#include <netdb.h>

#include <chrono>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <thread>

// The Linux branch of httplib::detail::getaddrinfo_with_timeout uses the
// glibc getaddrinfo_a family.  Replace those calls with deterministic mocks
// that model a resolver which is still running when the timeout fires:
//   * getaddrinfo_a starts a background lookup that finishes after 3 seconds.
//   * gai_suspend honours the requested timeout and reports EAI_AGAIN.
//   * gai_cancel reports EAI_NOTCANCELED (the lookup is already in progress).
//
// The current implementation ignores that gai_cancel result and returns while
// the lookup thread still holds a pointer to the stack-allocated `gaicb`.
#define getaddrinfo_a mock_getaddrinfo_a
#define gai_suspend mock_gai_suspend
#define gai_cancel mock_gai_cancel
#define gai_error mock_gai_error

int mock_getaddrinfo_a(int mode, struct gaicb **list, int ent,
                       struct sigevent *sig);
int mock_gai_suspend(const struct gaicb *const *list, int ent,
                     const struct timespec *timeout);
int mock_gai_cancel(struct gaicb *req);
int mock_gai_error(struct gaicb *req);

#include <httplib.h>

namespace {

constexpr int kClientTimeoutSec = 1;
constexpr int kLookupDelaySec = 3;

std::mutex g_mu;
std::condition_variable g_cv;
bool g_completed = false;

} // namespace

int mock_getaddrinfo_a(int mode, struct gaicb **list, int ent,
                       struct sigevent * /*sig*/) {
  if (mode != GAI_NOWAIT || ent != 1 || !list || !list[0]) {
    return EAI_SYSTEM;
  }

  auto *req = list[0];
  {
    std::lock_guard<std::mutex> lock(g_mu);
    g_completed = false;
  }

  // Simulate a slow DNS lookup that outlives the client's connection timeout.
  // Just like the glibc worker thread, this writes the result back into the
  // request even if gai_cancel failed to cancel it.
  std::thread([req] {
    std::this_thread::sleep_for(std::chrono::seconds(kLookupDelaySec));

    req->ar_result = nullptr;

    {
      std::lock_guard<std::mutex> lock(g_mu);
      g_completed = true;
    }
    g_cv.notify_all();
  }).detach();

  return 0;
}

int mock_gai_suspend(const struct gaicb *const * /*list*/, int /*ent*/,
                     const struct timespec *timeout) {
  std::unique_lock<std::mutex> lock(g_mu);

  if (g_completed) { return 0; }

  if (!timeout) {
    g_cv.wait(lock, [] { return g_completed; });
    return 0;
  }

  auto wait = std::chrono::seconds(timeout->tv_sec) +
              std::chrono::nanoseconds(timeout->tv_nsec);
  if (g_cv.wait_for(lock, wait, [] { return g_completed; })) { return 0; }

  return EAI_AGAIN;
}

int mock_gai_cancel(struct gaicb * /*req*/) {
  // The lookup is already running, so cancellation is not possible.
  return EAI_NOTCANCELED;
}

int mock_gai_error(struct gaicb * /*req*/) {
  return EAI_SYSTEM;
}

extern "C" const char *__asan_default_options() {
  return "detect_stack_use_after_return=1:halt_on_error=1";
}

int main() {
  std::cout << "starting client request" << std::endl;

  {
    httplib::Client cli("http://does-not-resolve.invalid");
    cli.set_connection_timeout(kClientTimeoutSec, 0);

    auto res = cli.Get("/");
    if (!res) {
      std::cout << "client returned error: "
                << httplib::to_string(res.error()) << std::endl;
    }
  }

  std::cout << "request returned; waiting for the timed-out lookup to finish"
            << std::endl;
  std::this_thread::sleep_for(std::chrono::seconds(kLookupDelaySec + 2));

  std::cout << "no crash" << std::endl;
  return 0;
}
