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

# Run specific test categories
ctest -R unit_tests --output-on-failure
ctest -R concurrency_tests --output-on-failure
ctest -R security_tests --output-on-failure
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

Pass all tests across 4 categories:
- Unit tests (~55)
- Integration tests (~35)
- Concurrency tests (~20)
- Security tests (~15)

**Reward function** (5-threshold sparse):
- 0% - 24%: 0.00
- 25% - 49%: 0.15
- 50% - 74%: 0.35
- 75% - 89%: 0.65
- 90% - 100%: 1.00

**Bonuses**: Category completion, concurrency fix (+3%), security fix (+2%)

**Penalties**: Regression (-15%) for re-breaking tests

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | LFU Eviction, Memory Pool Slab Allocator, Lock-Free Hash Table, TTL Precision, Binary Protocol |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Cache Warmer, Compression Pipeline, Cache Analytics |

These tasks test different software engineering skills while using the same codebase.
