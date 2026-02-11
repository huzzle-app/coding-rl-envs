# Incident Report: Server Fails to Start in Production

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-02-18 02:15 UTC
**Acknowledged**: 2024-02-18 02:18 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: vaultfs-api-prod deployment failing
Namespace: production
Deployment: vaultfs-api
Replicas: 0/3 ready
Last restart reason: CrashLoopBackOff
```

## Timeline

**02:15 UTC** - Deployment rollout initiated for version v2.4.7

**02:17 UTC** - All pods entering CrashLoopBackOff state

**02:20 UTC** - Kubernetes logs showing immediate container exits

**02:25 UTC** - Rollback to v2.4.6 initiated, same behavior observed

**02:30 UTC** - Discovered config changes were applied between deployments

## Container Logs

```
2024-02-18T02:15:32Z INFO  Starting VaultFS server...
2024-02-18T02:15:32Z INFO  Loading configuration from environment...
thread 'main' panicked at src/main.rs:45:10:
Cannot start a runtime from within a runtime. This happens because a function (like `block_on`) attempted to block the current thread while the thread is being used to drive asynchronous tasks.

note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
```

**02:32 UTC** - Second pod logs:

```
2024-02-18T02:32:15Z INFO  Starting VaultFS server...
thread 'main' panicked at src/config/mod.rs:28:45:
called `Result::unwrap()` on an `Err` value: ParseIntError { kind: InvalidDigit }

note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
```

## Extended Backtrace (RUST_BACKTRACE=1)

```
stack backtrace:
   0: std::panicking::begin_panic_handler
   1: core::panicking::panic_fmt
   2: core::result::unwrap_failed
   3: vaultfs::config::Config::from_env
             at ./src/config/mod.rs:28
   4: vaultfs::main
             at ./src/main.rs:18
   5: std::rt::lang_start
   ...
```

## Environment Variables Diff

Between working deployment and failing:

```diff
  DATABASE_URL=postgres://...
  REDIS_URL=redis://...
  MINIO_ENDPOINT=http://minio:9000
- POOL_SIZE=25
+ POOL_SIZE=25connections
  JWT_SECRET=***
- RATE_LIMIT=1000
+ RATE_LIMIT=
```

## Customer Impact

- **Downtime Duration**: 47 minutes
- **Users Affected**: All (~12,000 active users during incident window)
- **Failed API Requests**: ~15,000
- **Support Tickets**: 23 urgent tickets opened

---

## SRE Observations

**@sre.marcus** (02:40):
> The runtime-within-runtime error suggests we're calling blocking tokio code from an already-async context. The config parsing panic is separate - invalid env var format.

**@sre.kim** (02:45):
> Also noticed there's no graceful shutdown. When we send SIGTERM, the process just dies without draining connections. Clients are getting connection reset errors.

**@sre.marcus** (02:50):
> Database connection pool also seems misconfigured for async. Seeing warnings about blocking pool operations:

```
2024-02-18T02:48:12Z WARN  Blocking operation in async context detected
2024-02-18T02:48:12Z WARN  Consider using sqlx::Pool with runtime::spawn_blocking
```

---

## Attempted Mitigations

1. Reverted to previous Docker image - same issue (config was the problem)
2. Fixed POOL_SIZE and RATE_LIMIT env vars - runtime panic still occurs
3. Increased container memory - no effect
4. Disabled health checks temporarily to get container running - crashes before healthcheck even runs

---

## Questions for Investigation

1. Why is the server trying to create a tokio runtime inside an existing one?
2. Why does config parsing panic on invalid input instead of returning an error?
3. Why is there no graceful shutdown handler for SIGTERM/SIGINT?
4. Is the database pool configured correctly for async operations?

---

## Files to Investigate

Based on stack traces:
- `src/main.rs` - Runtime initialization issues
- `src/config/mod.rs` - Environment variable parsing panics
- `src/config/database.rs` - Pool configuration for async

---

**Status**: INVESTIGATING
**Assigned**: @backend-team
**Incident Commander**: @sre.marcus
