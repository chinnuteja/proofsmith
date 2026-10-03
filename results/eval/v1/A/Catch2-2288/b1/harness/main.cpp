#include <catch2/catch.hpp>

#include <type_traits>
#include <utility>

namespace {
    template <typename...>
    struct make_void { using type = void; };

    template <typename T, typename = void>
    struct is_const_approx_callable : std::false_type {};

    template <typename T>
    struct is_const_approx_callable<
        T,
        typename make_void<decltype(
            std::declval<const T&>()(std::declval<double>()))>::type
    > : std::true_type {};
}

int main() {
    // Catch::Detail::Approx::operator() is a factory that copies the
    // configured epsilon/margin/scale onto a new Approx for the supplied
    // value. It does not mutate the source Approx, so it should be callable
    // on a const instance.
    return is_const_approx_callable<Catch::Detail::Approx>::value ? 0 : 1;
}
