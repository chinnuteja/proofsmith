#pragma once
#include <cstdio>
#include <cstdlib>

#define PS_CHECK(cond)                                                              \
  do {                                                                              \
    if (!(cond)) {                                                                  \
      std::fprintf(stderr, "PROOFSMITH_CHECK_FAILED %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      std::fflush(stderr);                                                          \
      std::abort();                                                                 \
    }                                                                               \
  } while (0)
