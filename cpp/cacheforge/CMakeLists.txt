cmake_minimum_required(VERSION 3.20)
project(cacheforge VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(ENABLE_SANITIZERS "Enable ASan+UBSan" OFF)
if(ENABLE_SANITIZERS AND CMAKE_BUILD_TYPE STREQUAL "Debug")
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all)
    add_link_options(-fsanitize=address,undefined)
endif()

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
    tests/unit/test_ub_detection.cpp
)
target_link_libraries(unit_tests PRIVATE cacheforge_lib GTest::gtest GTest::gtest_main)
target_compile_definitions(unit_tests PRIVATE SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")

# Integration tests
add_executable(integration_tests
    tests/integration/test_server_integration.cpp
    tests/integration/test_replication.cpp
    tests/integration/test_persistence.cpp
    tests/integration/test_source_checks.cpp
)
target_link_libraries(integration_tests PRIVATE cacheforge_lib GTest::gtest GTest::gtest_main)
target_compile_definitions(integration_tests PRIVATE SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")

# Concurrency tests
add_executable(concurrency_tests
    tests/concurrency/test_concurrent_access.cpp
    tests/concurrency/test_deadlock.cpp
)
target_link_libraries(concurrency_tests PRIVATE cacheforge_lib GTest::gtest GTest::gtest_main)
target_compile_definitions(concurrency_tests PRIVATE SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")

# Security tests
add_executable(security_tests
    tests/security/test_security.cpp
)
target_link_libraries(security_tests PRIVATE cacheforge_lib GTest::gtest GTest::gtest_main)
target_compile_definitions(security_tests PRIVATE SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")

# ====================================================================
# CTest targets with dependency chains
# ====================================================================

# Tier 0: No dependencies
add_test(NAME setup_tests COMMAND unit_tests --gtest_filter="ConfigTest.*")
add_test(NAME parser_core_tests COMMAND unit_tests --gtest_filter="ParserTest.*")
add_test(NAME value_tests COMMAND unit_tests --gtest_filter="ValueTest.*")
add_test(NAME hashtable_tests COMMAND unit_tests --gtest_filter="HashTableTest.*")
add_test(NAME ub_detection_tests COMMAND unit_tests --gtest_filter="UBDetectionTest.*")
add_test(NAME source_check_tests COMMAND integration_tests --gtest_filter="SourceCheckTest.*")

# Tier 1: Depends on setup
add_test(NAME deadlock_tests COMMAND concurrency_tests --gtest_filter="DeadlockTest.*")
set_tests_properties(deadlock_tests PROPERTIES DEPENDS setup_tests)

add_test(NAME eviction_tests COMMAND unit_tests --gtest_filter="EvictionTest.*")
set_tests_properties(eviction_tests PROPERTIES DEPENDS setup_tests)

add_test(NAME snapshot_tests COMMAND unit_tests --gtest_filter="SnapshotTest.*")
set_tests_properties(snapshot_tests PROPERTIES DEPENDS setup_tests)

# Tier 2: Depends on tier 1
add_test(NAME memory_pool_tests COMMAND unit_tests --gtest_filter="MemoryPoolTest.*")
set_tests_properties(memory_pool_tests PROPERTIES DEPENDS deadlock_tests)

add_test(NAME expiry_tests COMMAND unit_tests --gtest_filter="ExpiryTest.*")
set_tests_properties(expiry_tests PROPERTIES DEPENDS eviction_tests)

# Tier 3: Depends on tier 1-2
add_test(NAME security_suite COMMAND security_tests)
set_tests_properties(security_suite PROPERTIES DEPENDS parser_core_tests)

add_test(NAME condvar_tests COMMAND concurrency_tests --gtest_filter="ConcurrencyTest.*")
set_tests_properties(condvar_tests PROPERTIES DEPENDS setup_tests)

add_test(NAME replication_tests COMMAND integration_tests --gtest_filter="ReplicationTest.*")
set_tests_properties(replication_tests PROPERTIES DEPENDS setup_tests)

add_test(NAME persistence_tests COMMAND integration_tests --gtest_filter="PersistenceIntegrationTest.*")
set_tests_properties(persistence_tests PROPERTIES DEPENDS snapshot_tests)

add_test(NAME server_integration_tests COMMAND integration_tests --gtest_filter="ServerIntegrationTest.*")
set_tests_properties(server_integration_tests PROPERTIES DEPENDS setup_tests)
