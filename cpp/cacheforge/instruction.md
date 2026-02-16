# CacheForge - Debug C++ In-Memory Cache Server

Fix bugs in a high-performance in-memory cache server (Redis-like) written in C++20.

 | ## Technology Stack

- **C++20** with Boost.Asio (networking), spdlog (logging)
- **CMake 3.20+** with vcpkg for dependency management
- **PostgreSQL 15** (persistence), **Redis 7** (replication)
- **Google Test** (gtest) for testing

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Build project
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel

# Run tests
cd build && ctest --output-on-failure

# Run specific test categories (fine-grained CTest targets)
ctest -R setup_tests --output-on-failure
ctest -R parser_core_tests --output-on-failure
ctest -R deadlock_tests --output-on-failure
ctest -R source_check_tests --output-on-failure
ctest -R ub_detection_tests --output-on-failure
ctest -R security_suite --output-on-failure
```

**Critical**: Setup bugs (L1-L4) prevent the project from building correctly. Fix these first before tackling other categories.

## Known Issues

Test failures indicate issues in core modules. Some infrastructure code may also need review.

## Key C++ Pitfalls

- **Static initialization fiasco**: Global `Config` object used before construction
- **Signal handler UB**: Calling non-async-signal-safe functions (spdlog) in signal handlers
- **Lock ordering deadlock**: `set()` and `remove()` acquire mutexes in opposite order
- **memory_order_relaxed**: Causes stale reads on size counter (needs stronger ordering)
- **shared_ptr cycles**: `Connection` stores `shared_from_this()` creating reference cycle
- **Use-after-move**: Replication event enqueued after being moved
- **Strict aliasing**: Fast integer parse violates aliasing rules
- **Format string**: User data passed as format string to spdlog

## Debugging Tips

1. **Start with L1** (static init fiasco) - many bugs depend on proper Config initialization
2. **Check include guards**: Verify `config.h` and `connection.h` have different guards
3. **Use sanitizers**:
 - ThreadSanitizer: `cmake -B build -DCMAKE_CXX_FLAGS="-fsanitize=thread"`
 - AddressSanitizer: `cmake -B build -DCMAKE_CXX_FLAGS="-fsanitize=address"`
4. **Lock ordering**: Compare mutex acquisition order between functions
5. **Signal safety**: Only `sig_atomic_t` writes are safe in signal handlers
6. **shared_ptr cycles**: Look for `shared_from_this()` stored in members

## Success Criteria

Pass all 149 tests across 4 categories (16 CTest targets with dependency chains):
- Unit tests (82) — config, parser, value, hashtable, eviction, expiry, memory pool, snapshot, UB detection
- Integration tests (35) — server integration, replication, persistence, source checks
- Concurrency tests (14) — concurrent access, deadlock
- Security tests (18) — TTL overflow, format string, buffer overflow, key length, shared_ptr cycle

**Reward function** (hybrid: 70% test pass rate + 30% code correctness):

Test pass rate thresholds:
- < 50%: 0.00
- >= 50%: 0.15
- >= 75%: 0.35
- >= 90%: 0.65
- 100%: 1.00

Code correctness checks 12 source-level patterns (signal safety, const correctness, RAII, etc.)

**Final reward** = 0.70 * test_pass_reward + 0.30 * code_correctness_score

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | LFU Eviction, Memory Pool Slab Allocator, Lock-Free Hash Table, TTL Precision, Binary Protocol |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Cache Warmer, Compression Pipeline, Cache Analytics |

These tasks test different software engineering skills while using the same codebase.
