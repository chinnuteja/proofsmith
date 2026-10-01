cmake_minimum_required(VERSION 3.16)
project(orderd LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)

add_library(orderd_core STATIC order_book.cpp wire_codec.cpp)
target_include_directories(orderd_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(orderd_core PUBLIC Threads::Threads)

enable_testing()

add_executable(book_ops tests/book_ops.cpp)
target_link_libraries(book_ops PRIVATE orderd_core)
add_test(NAME book_ops COMMAND book_ops)

add_executable(risk_engine tests/risk_engine.cpp)
target_link_libraries(risk_engine PRIVATE orderd_core)
add_test(NAME risk_engine COMMAND risk_engine)

add_executable(wire_codec tests/wire_codec.cpp)
target_link_libraries(wire_codec PRIVATE orderd_core)
add_test(NAME wire_codec COMMAND wire_codec)
