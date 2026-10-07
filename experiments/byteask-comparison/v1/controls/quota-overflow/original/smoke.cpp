#include "subject.h"
int main() { Quota q{2, 10}; return !(q.reserve(3) && q.used == 5); }
