cmake_minimum_required(VERSION 3.16)
project(ticks LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(core STATIC ticks.cpp)
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

enable_testing()
add_executable(ticks_test tests/ticks_test.cpp)
target_link_libraries(ticks_test PRIVATE core)
add_test(NAME ticks_test COMMAND ticks_test)
