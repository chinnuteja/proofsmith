#include "subject.h"
int main() { Entry e{42, 100}; return !(e.lookup(50) == 42); }
