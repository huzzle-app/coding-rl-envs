# VaultFS - Encrypted Filesystem Service

Fix 29 bugs across 7 categories in a Rust-based encrypted filesystem service built with Axum, Tokio, PostgreSQL, Redis, and S3/MinIO.

**29 bugs** | **90 tests** | Difficulty: Senior (4-8h)

## Bug Categories

| Category | Bugs | Description |
|----------|------|-------------|
| L: Setup/Config | 4 | Nested runtime, pool config, env parsing, graceful shutdown |
| A: Ownership | 5 | Use-after-move, partial move, borrowed values |
| B: Lifetime | 4 | References to locals, self-referential structs, async lifetimes |
| C: Concurrency | 5 | Deadlocks, blocking async, race conditions, non-Send futures |
| D: Error Handling | 4 | Unwrap on None, missing match arms, error conversion, panic in drop |
| E: Memory/Resource | 3 | Rc cycles, handle leaks, unbounded channels |
| F: Security | 4 | Path traversal, SQL injection, timing attacks, unsafe mmap |

## Getting Started

```bash
# Start infrastructure (PostgreSQL, Redis, MinIO)
docker compose up -d

# Run tests
cargo test

# Run specific test
cargo test test_name
```

## Key Notes

- **Setup bugs**: Some bugs prevent the project from compiling or starting. Fix these first.
- **Rust-specific bugs**: Watch for use-after-move, lifetime issues, blocking in async contexts, and lock ordering.
- **Ownership model**: Many bugs involve violating Rust's ownership and borrowing rules.
- **Async runtime**: Tokio-specific issues like nested runtimes and blocking operations in async contexts.
- **Memory safety**: Even "safe" Rust can have logic bugs that lead to resource leaks or deadlocks.

## Success Criteria

- All 79 tests pass
- No compilation errors
- No runtime panics or deadlocks
- Services start successfully with `docker compose up -d`

## Test Output

Cargo test will show:
```
test result: ok. X passed; Y failed; Z ignored
```

Your goal is to achieve 100% pass rate (all tests passing).

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Incremental Sync, Hierarchical Locking, Memory Optimization, Batch API, Backend Migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Encryption at Rest, Quota Manager, Collaborative Editing |

These tasks test different software engineering skills while using the same codebase.
