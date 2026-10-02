cmake_minimum_required(VERSION 3.16)
project(prices LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(core STATIC price_cache.cpp)
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

enable_testing()
add_executable(cache_test tests/cache_test.cpp)
target_link_libraries(cache_test PRIVATE core)
add_test(NAME cache_test COMMAND cache_test)
