# CacheForge - In-Memory Cache Server Debugging Challenge

## Overview

CacheForge is a high-performance in-memory cache server written in C++20 (similar to Redis). The codebase contains issues across 6 categories that need to be identified and fixed. All tests must pass before the task is complete.

## Known Issues

Test failures indicate issues in core modules. Some infrastructure code may also need review.

## Difficulty

**Senior Engineer Level** - Expected time: 2-4 hours

## Technology Stack

- **Language**: C++20
- **Build System**: CMake 3.20+ with vcpkg
- **Framework**: Boost.Asio (networking), spdlog (logging)
- **Database**: PostgreSQL 15 (persistence)
- **Cache**: Redis 7 (replication)
- **Testing**: Google Test (gtest)

## Getting Started

```bash
# Start infrastructure services
docker compose up -d

# Wait for services to be healthy
docker compose ps

# Build the project
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel

# Run all tests
cd build && ctest --output-on-failure

# Run specific test category (fine-grained CTest targets)
ctest -R setup_tests --output-on-failure
ctest -R parser_core_tests --output-on-failure
ctest -R value_tests --output-on-failure
ctest -R deadlock_tests --output-on-failure
ctest -R eviction_tests --output-on-failure
ctest -R security_suite --output-on-failure
ctest -R source_check_tests --output-on-failure
ctest -R ub_detection_tests --output-on-failure
```

**Important**: The build system itself has issues that must be fixed first. Setup bugs (L1-L4) prevent the project from building or starting correctly. Fix these before tackling other categories.

### Category A: Concurrency

### Category B: Memory Management

### Category C: Smart Pointers & RAII

### Category D: Move Semantics & UB

### Category E: Security

## Test Structure

| Category | Test Binary | Tests | Weight |
| Unit | `unit_tests` | 82 | 1.0x |
| Integration | `integration_tests` | 35 | 1.5x |
| Concurrency | `concurrency_tests` | 14 | 2.5x |
| Security | `security_tests` | 18 | 2.0x |
| **Total** | | **149** | |

Tests are organized into 15 CTest targets with dependency chains. Some tests (e.g., deadlock, eviction) depend on setup tests passing first. Use `ctest --output-on-failure` to see the full dependency-ordered execution.

## Key Files to Investigate

## Scoring

Your score is a blend of test pass rate (70%) and code correctness (30%):

**Test pass rate** (5-threshold sparse):

| Pass Rate | Reward |
|-----------|--------|
| < 50% | 0.00 |
| >= 50% | 0.15 |
| >= 75% | 0.35 |
| >= 90% | 0.65 |
| 100% | 1.00 |

**Code correctness** checks 12 source-level patterns (signal safety, const correctness, RAII usage, etc.) and contributes up to 0.30 to the final reward.

**Final reward** = 0.70 * test_pass_reward + 0.30 * code_correctness_score

## Hints

1. **Start with Setup (L category)**: Fix L1 (static init fiasco) first - many things depend on proper Config initialization
2. **Include guard collision (L4)**: Check that `config.h` and `connection.h` have different include guards
3. **Lock ordering (A2)**: Compare the mutex acquisition order in `set()` vs `remove()`
4. **Use ThreadSanitizer**: Build with `-fsanitize=thread` to catch data races
5. **Use AddressSanitizer**: Build with `-fsanitize=address` to catch buffer overflows and use-after-free
6. **Check memory_order**: `std::memory_order_relaxed` is rarely correct for inter-thread communication
7. **shared_ptr cycles**: Look for `shared_from_this()` stored in member variables
8. **Signal safety**: Only `sig_atomic_t` writes are safe in signal handlers

## Architecture

```
cacheforge/
├── src/
│ ├── config/ # Configuration loading (L1, L3)
│ ├── server/ # TCP server, connections (A1, A5, L4, C1, C3, E2)
│ ├── protocol/ # RESP-like protocol parser (B1, E2, E3)
│ ├── storage/ # Hash table, eviction, expiry (A2, A3, A4, C2, E1, E4)
│ ├── data/ # Value types (B2, D4)
│ ├── replication/ # Master-replica sync (D1, D3)
│ ├── persistence/ # Snapshot/AOF (C4)
│ └── utils/ # Memory pool (B3, B4)
├── tests/
│ ├── unit/ # Unit tests
│ ├── integration/ # Integration tests
│ ├── concurrency/ # Race condition and deadlock tests
│ └── security/ # Security vulnerability tests
├── environment/ # RL environment wrapper
├── CMakeLists.txt # Build configuration
├── vcpkg.json # C++ dependency manifest
├── Dockerfile # Container build
└── docker-compose.yml # Infrastructure services
```

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents:

| Scenario | Type | Description |
| [01-deadlock-under-load](./scenarios/01-deadlock-under-load.md) | PagerDuty Incident | Server hangs under concurrent SET/DELETE load |
| [02-memory-corruption-crashes](./scenarios/02-memory-corruption-crashes.md) | Incident Report | Random SIGSEGV, heap corruption, double-free |
| [03-security-audit-findings](./scenarios/03-security-audit-findings.md) | Security Audit | Penetration test findings (buffer overflow, DoS) |
| [04-startup-failures](./scenarios/04-startup-failures.md) | Deployment Blocker | Crashes on startup across environments |
| [05-replication-eviction-anomalies](./scenarios/05-replication-eviction-anomalies.md) | Support Ticket | Empty logs, eviction failures, stale data |

Each scenario describes **symptoms only** (error messages, stack traces, user reports) without revealing the underlying code issues. Use these to practice realistic debugging workflows.

## Verification

After making fixes:

```bash
# Rebuild
cmake --build build --parallel

# Run all tests
cd build && ctest --output-on-failure -j 4

# Run with verbose output
ctest --output-on-failure -V

# Run specific test
ctest -R security_tests --output-on-failure
```

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | LFU Eviction, Memory Pool Slab Allocator, Lock-Free Hash Table, TTL Precision, Binary Protocol |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Cache Warmer, Compression Pipeline, Cache Analytics |

These tasks test different software engineering skills while using the same codebase.
