#include <thread>

int counter = 0;

void bump() {
  for (int i = 0; i < 10000; ++i) {
    ++counter;
  }
}

int main() {
  std::thread t1(bump);
  std::thread t2(bump);
  t1.join();
  t2.join();
  return counter == 20000 ? 0 : 1;
}
