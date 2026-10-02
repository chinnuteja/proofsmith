cmake_minimum_required(VERSION 3.16)
project(metrics LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)

add_library(core STATIC metrics.cpp)
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(core PUBLIC Threads::Threads)

enable_testing()
add_executable(metrics_test tests/metrics_test.cpp)
target_link_libraries(metrics_test PRIVATE core)
add_test(NAME metrics_test COMMAND metrics_test)
