#include "subject.h"
int main() { Queue q{{10,20}}; return !(q.take(5) == std::vector<int>{10,20} && q.values.empty()); }
