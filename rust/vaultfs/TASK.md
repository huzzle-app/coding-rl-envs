# VaultFS - Distributed File Storage Service

## Task Description

You are debugging a distributed file storage service built with Rust. The application provides secure file storage, synchronization, and sharing capabilities similar to cloud storage services.

The codebase contains issues across multiple categories that need to be identified and fixed. All tests must pass before the task is complete.

## Getting Started

```bash
# Start infrastructure services
docker compose up -d

# Build the project
cargo build

# Run all tests
cargo test

# Run with specific test output
cargo test -- --nocapture

# Run the server
cargo run --bin vaultfs

# Run with race detection (requires nightly)
RUSTFLAGS="-Z sanitizer=thread" cargo +nightly test
```

## Architecture

VaultFS is a Rust web service with the following components:

| Component | Purpose |
|-----------|---------|
| Axum API | REST API endpoints |
| PostgreSQL | User data, file metadata |
| Redis | Caching, sessions, rate limiting |
| MinIO | S3-compatible object storage |
| Tokio | Async runtime |

### Key Modules

- **handlers/** - HTTP request handlers
- **services/** - Business logic (storage, sync, versioning)
- **models/** - Data structures and database models
- **middleware/** - Authentication, rate limiting
- **repository/** - Database access layer
- **storage/** - MinIO/S3 integration
- **sync/** - File synchronization logic

## Key Files to Examine

## Test Categories

| Category | Tests | Focus |
|----------|-------|-------|
| Setup | 9 | Configuration, runtime, shutdown |
| Storage/Models | 34 | Ownership, error handling, memory |
| Concurrency | 14 | Send bounds, lifetimes, error conversion |
| Lock Manager | 8 | Deadlock prevention, lock ordering |
| Cache | 9 | Lifetime issues, owned return types |
| Security | 16 | Injection, traversal, timing, mmap |

## Success Criteria

- All 90 tests pass
- No compiler warnings
- `cargo clippy` passes without errors
- No panics under normal operation
- Thread-safe concurrent access
- No memory leaks (checked with Valgrind/Miri)

## Rust-Specific Patterns to Watch

```rust
// Use after move (BUG)
let data = get_data();
process(data);
println!("{}", data); // Error: value moved

// Borrowed value doesn't live long enough (BUG)
fn get_ref<'a>() -> &'a str {
 let s = String::from("hello");
 &s // Error: s dropped here
}

// Deadlock from lock ordering (BUG)
let a = Mutex::new(1);
let b = Mutex::new(2);
// Thread 1: locks a then b
// Thread 2: locks b then a
// Deadlock!

// Blocking in async (BUG)
async fn bad() {
 std::thread::sleep(Duration::from_secs(1)); // Blocks executor!
}
// Should use: tokio::time::sleep(Duration::from_secs(1)).await;

// Unwrap panic (BUG)
let value = map.get("key").unwrap(); // Panics if key missing
// Should use: map.get("key").ok_or(Error::NotFound)?;

// Path traversal (BUG)
let path = format!("/files/{}", user_input);
// user_input = "../../../etc/passwd" -> security issue
// Should validate and sanitize path
```

## Debugging Scenarios

Realistic debugging scenarios are available in the [scenarios/](./scenarios/) directory. These simulate production incidents, security audits, and customer escalations:

| Scenario | Type | Description |
| [01-server-startup-failures](./scenarios/01-server-startup-failures.md) | PagerDuty Incident | Server panics on startup |
| [02-security-penetration-test](./scenarios/02-security-penetration-test.md) | Security Audit | Path traversal, SQL injection findings |
| [03-async-runtime-deadlocks](./scenarios/03-async-runtime-deadlocks.md) | Customer Escalation | Service freezes under load |
| [04-borrow-checker-crashes](./scenarios/04-borrow-checker-crashes.md) | Grafana Alert | Runtime ownership panics |
| [05-resource-leaks-and-drops](./scenarios/05-resource-leaks-and-drops.md) | DataDog Anomaly | Memory growth, file descriptor exhaustion |

Each scenario describes **symptoms only** - the observable behavior from an operator or user perspective. Use these to practice realistic debugging workflows.

## Hints

1. Start with L category bugs - the server may not start correctly
2. Use `cargo check` frequently to catch borrow checker errors
3. `cargo clippy` can identify many common issues
4. For async issues, check if you're blocking the runtime
5. For lifetime issues, consider if you need `'static` or owned types
6. Watch for `.unwrap()` calls - they're often the source of panics
7. Use `Arc<Mutex<T>>` carefully - nested locks cause deadlocks
8. Path inputs should always be validated against traversal attacks

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Incremental Sync, Hierarchical Locking, Memory Optimization, Batch API, Backend Migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Encryption at Rest, Quota Manager, Collaborative Editing |

These tasks test different software engineering skills while using the same codebase.
