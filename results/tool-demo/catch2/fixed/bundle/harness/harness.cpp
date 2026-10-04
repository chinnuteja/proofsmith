// Supplied development example, derived from the public issue's const-call contract.
// This is a type-level consumer check, not execution coverage of Approx::operator().
#include <internal/catch_approx.h>
#include <type_traits>
#include "proofsmith_check.h"

int main() {
  constexpr bool callable = std::is_invocable_v<const Catch::Detail::Approx&, double>;
  PS_CHECK(callable);
  return 0;
}
