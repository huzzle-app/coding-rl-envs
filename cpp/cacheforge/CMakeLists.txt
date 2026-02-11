
# The global Config object is defined in config.cpp but referenced in server.cpp's
# file-scope initializer. Since C++ doesn't guarantee cross-TU static init order,
# this causes undefined behavior (crash or garbage values on startup).
# FIX: Use a function-local static (Meyers' singleton) instead of a global variable.


# correctly, BUT the macro-based fallback guards use the same name CACHEFORGE_CONFIG_H
# in both files. When both are included, the second file's content is silently skipped.
# FIX: Give connection.h its own unique guard name (CACHEFORGE_CONNECTION_H).

cmake_minimum_required(VERSION 3.20)
project(cacheforge VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Find packages
find_package(Threads REQUIRED)
find_package(Boost REQUIRED COMPONENTS system)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(spdlog CONFIG REQUIRED)
find_package(fmt CONFIG REQUIRED)
find_package(GTest CONFIG REQUIRED)

# Main library
add_library(cacheforge_lib
    src/config/config.cpp
    src/server/server.cpp
    src/server/connection.cpp
    src/protocol/parser.cpp
    src/storage/hashtable.cpp
    src/storage/eviction.cpp
    src/storage/expiry.cpp
    src/data/value.cpp
    src/replication/replicator.cpp
    src/persistence/snapshot.cpp
    src/utils/memory_pool.cpp
)

target_include_directories(cacheforge_lib PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(cacheforge_lib PUBLIC
    Threads::Threads
    Boost::system
    nlohmann_json::nlohmann_json
    spdlog::spdlog
    fmt::fmt
)

# Main executable
add_executable(cacheforge src/main.cpp)
target_link_libraries(cacheforge PRIVATE cacheforge_lib)

# Tests
enable_testing()

# Unit tests
add_executable(unit_tests
    tests/unit/test_config.cpp
    tests/unit/test_parser.cpp
    tests/unit/test_hashtable.cpp
    tests/unit/test_eviction.cpp
    tests/unit/test_expiry.cpp
    tests/unit/test_value.cpp
    tests/unit/test_memory_pool.cpp
    tests/unit/test_snapshot.cpp
)
target_link_libraries(unit_tests PRIVATE cacheforge_lib GTest::gtest GTest::gtest_main)
add_test(NAME unit_tests COMMAND unit_tests)

# Integration tests
add_executable(integration_tests
    tests/integration/test_server_integration.cpp
    tests/integration/test_replication.cpp
    tests/integration/test_persistence.cpp
)
target_link_libraries(integration_tests PRIVATE cacheforge_lib GTest::gtest GTest::gtest_main)
add_test(NAME integration_tests COMMAND integration_tests)

# Concurrency tests
add_executable(concurrency_tests
    tests/concurrency/test_concurrent_access.cpp
    tests/concurrency/test_deadlock.cpp
)
target_link_libraries(concurrency_tests PRIVATE cacheforge_lib GTest::gtest GTest::gtest_main)
add_test(NAME concurrency_tests COMMAND concurrency_tests)

# Security tests
add_executable(security_tests
    tests/security/test_security.cpp
)
target_link_libraries(security_tests PRIVATE cacheforge_lib GTest::gtest GTest::gtest_main)
add_test(NAME security_tests COMMAND security_tests)
