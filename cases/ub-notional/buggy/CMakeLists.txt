cmake_minimum_required(VERSION 3.16)
project(pricing LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(core STATIC pricing.cpp)
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

enable_testing()
add_executable(pricing_test tests/pricing_test.cpp)
target_link_libraries(pricing_test PRIVATE core)
add_test(NAME pricing_test COMMAND pricing_test)
