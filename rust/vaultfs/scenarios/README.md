# VaultFS Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, security audits, and operational alerts you might encounter as an engineer on the VaultFS team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, and user reports. Your task is to:

1. Reproduce the issue (if possible)
2. Investigate root cause
3. Identify the buggy code
4. Implement a fix
5. Verify the fix doesn't cause regressions

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-server-startup-failures.md](./01-server-startup-failures.md) | PagerDuty Incident | Critical | Server panics on startup, runtime-in-runtime errors |
| [02-security-penetration-test.md](./02-security-penetration-test.md) | Security Report | Critical | Path traversal, SQL injection, timing attacks |
| [03-async-runtime-deadlocks.md](./03-async-runtime-deadlocks.md) | Customer Escalation | High | Service freezes, deadlocks, blocking async calls |
| [04-borrow-checker-crashes.md](./04-borrow-checker-crashes.md) | Grafana Alert | High | Runtime panics from ownership violations |
| [05-resource-leaks-and-drops.md](./05-resource-leaks-and-drops.md) | DataDog Anomaly | Critical | Memory growth, file descriptor exhaustion |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1-2**: Clear symptoms pointing to specific subsystems (startup/security)
- **Scenario 3-4**: Concurrency and ownership issues requiring Rust expertise
- **Scenario 5**: Cross-cutting resource management affecting multiple components

## Bug Categories Covered

| Scenario | Bug Categories |
|----------|---------------|
| 01 | L: Setup/Configuration |
| 02 | F: Security |
| 03 | C: Concurrency/Async |
| 04 | A: Ownership/Borrowing, B: Lifetime Issues |
| 05 | E: Memory/Resource, D: Error Handling |

## Tips for Investigation

1. **Build and test frequently**: `cargo build` and `cargo test` catch many issues
2. **Use Rust tooling**: `cargo clippy` for linting, `cargo check` for fast compilation checks
3. **Run with race detection**: `RUSTFLAGS="-Z sanitizer=thread" cargo +nightly test`
4. **Check for panics**: Search for `.unwrap()` and `.expect()` calls on potentially-None values
5. **Understand ownership**: Use `--explain` on compiler errors (e.g., `rustc --explain E0382`)
6. **Profile memory**: Use heaptrack or valgrind to identify leaks

## Rust-Specific Patterns to Watch

```rust
// Deadlock from lock ordering
let a = lock_a.lock(); // Holds lock_a
let b = lock_b.lock(); // Thread 2 might hold lock_b and wait for lock_a

// Blocking in async context
async fn bad() {
    std::thread::sleep(Duration::from_secs(1)); // Blocks executor!
}

// Use after move
let data = vec![1, 2, 3];
process(data);      // data moved
println!("{:?}", data); // Error: data moved

// RefCell panics at runtime
let cell = RefCell::new(1);
let a = cell.borrow_mut();
let b = cell.borrow_mut(); // Panic: already borrowed

// Rc cycles leak memory
struct Node { parent: Rc<Node>, children: Vec<Rc<Node>> }
// Parent and children reference each other - never freed
```

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `tests/` directory contain assertions that exercise these bugs
