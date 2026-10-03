#pragma once
#include <cstdio>
#include <cstdlib>

// Aborting does not flush LLVM counters. The weak symbol keeps other variants
// independent of the coverage runtime.
#if defined(__GNUC__)
extern "C" int __llvm_profile_write_file(void) __attribute__((weak));
inline void proofsmith_flush_coverage() {
  if (__llvm_profile_write_file) __llvm_profile_write_file();
}
#else
inline void proofsmith_flush_coverage() {}
#endif

#define PS_CHECK(cond)                                                              \
  do {                                                                              \
    if (!(cond)) {                                                                  \
      std::fprintf(stderr, "PROOFSMITH_CHECK_FAILED %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      std::fflush(stderr);                                                          \
      proofsmith_flush_coverage();                                                   \
      std::abort();                                                                 \
    }                                                                               \
  } while (0)
