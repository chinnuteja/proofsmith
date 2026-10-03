#define CATCH_CONFIG_MAIN
#include <catch2/catch.hpp>

TEST_CASE("Approx factory is const-correct") {
  // Set up a template Approx with problem-specific margin, etc.
  Approx const apprx = Approx(0.0).margin(1e-6);
  double value = 1.0;
  // Use template in assertions
  REQUIRE(value == apprx(1.0));
}
