cmake_minimum_required(VERSION 3.16)
project(matcher LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(core STATIC match.cpp)
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

enable_testing()
add_executable(match_test tests/match_test.cpp)
target_link_libraries(match_test PRIVATE core)
add_test(NAME match_test COMMAND match_test)
