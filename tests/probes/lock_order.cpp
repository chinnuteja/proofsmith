#include <mutex>
#include <thread>

std::mutex a, b;

int main() {
  std::thread t1([] { std::lock_guard<std::mutex> la(a); std::lock_guard<std::mutex> lb(b); });
  t1.join();
  std::thread t2([] { std::lock_guard<std::mutex> lb(b); std::lock_guard<std::mutex> la(a); });
  t2.join();
  return 0;
}
