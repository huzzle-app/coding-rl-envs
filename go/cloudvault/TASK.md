# CloudVault - Cloud Storage Debugging Challenge

## Overview

CloudVault is a cloud storage and file synchronization service built in Go. The codebase contains issues across 6 categories that are blocking production deployment. Your task is to identify and fix these bugs to get all tests passing.

## Difficulty

**Senior Engineer Level** - Expected time: 2-4 hours

## Technology Stack

- **Language**: Go 1.21
- **Framework**: Gin (HTTP router)
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Object Storage**: MinIO (S3-compatible)
- **Testing**: Go's built-in testing with testify

## Getting Started

```bash
# Start the infrastructure
docker compose up -d

# Wait for services to be healthy
docker compose ps

# Run tests
go test -race -v ./...

# Run specific test category
go test -race -v ./tests/unit/...
go test -race -v ./tests/integration/...
go test -race -v ./tests/security/...
```

## Bug Categories

### Category A: Concurrency Bugs
Go's concurrency model is powerful but error-prone. Look for:
- **A1**: Goroutine leaks - goroutines that never terminate
- **A2**: Race conditions - concurrent map access without synchronization
- **A3**: Channel deadlocks - blocking sends/receives
- **A4**: WaitGroup misuse - Add() called in wrong place
- **A5**: Mutex copy - passing mutex by value instead of pointer

**Tip**: Run tests with `-race` flag to detect race conditions.

### Category B: Memory & Slice Bugs
Go's slice semantics can be tricky:
- **B1**: Slice bounds errors - off-by-one in indexing
- **B2**: Nil map writes - writing to uninitialized map
- **B3**: Slice aliasing - modifications affect original
- **B4**: Memory leaks in append patterns

### Category C: Database Bugs
Common database anti-patterns:
- **C1**: Transaction rollback issues
- **C2**: Connection leaks - rows.Close() not called
- **C3**: Prepared statement leaks
- **C4**: N+1 query patterns

### Category D: Error Handling Bugs
Go's explicit error handling requires discipline:
- **D1**: Ignored errors - `err` not checked
- **D2**: Error shadowing - `:=` creates new variable
- **D3**: Nil interface checks - `err != nil` edge cases

### Category E: Security Bugs
Critical security vulnerabilities:
- **E1**: Weak cryptography - math/rand vs crypto/rand
- **E2**: Path traversal - insufficient validation
- **E3**: SQL injection - string interpolation in queries
- **E4**: IDOR - missing authorization checks

### Category F/L: Configuration Bugs
Setup and configuration issues:
- **L1**: Init order dependency - init() runs before main()
- **L2/F2**: Environment parsing - type conversion errors
- **F3**: Integer parsing - Atoi vs ParseInt
- **F4**: Missing validation - required fields not checked

## Test Structure

| Category | Tests | Weight |
|----------|-------|--------|
| Unit | 55 | 1.0x |
| Integration | 35 | 1.5x |
| Security | 20 | 2.0x |
| Race Detection | 15 | 2.5x |
| **Total** | **125** | |

## Key Files to Investigate

| File | Bug Categories |
|------|---------------|
| `cmd/server/main.go` | L1, F1 |
| `internal/config/config.go` | F2, F3, F4 |
| `internal/services/storage/storage.go` | A1, A4 |
| `internal/services/storage/chunker.go` | B1, B3, B4 |
| `internal/services/sync/sync.go` | A2, D1, D2 |
| `internal/services/sync/conflict.go` | B2 |
| `internal/services/notification/notify.go` | A3 |
| `internal/services/versioning/version.go` | C1 |
| `internal/repository/file_repo.go` | C2, C3, E3 |
| `internal/middleware/auth.go` | D1, D3 |
| `internal/middleware/ratelimit.go` | A2, A5, B2 |
| `internal/handlers/files.go` | D1, E4 |
| `pkg/crypto/encrypt.go` | E1 |
| `pkg/utils/path.go` | E2 |

## Scoring

Your score is based on the percentage of tests passing:

| Pass Rate | Reward |
|-----------|--------|
| < 10% | 0.00 |
| 10-24% | 0.00 |
| 25-39% | 0.05 |
| 40-54% | 0.12 |
| 55-69% | 0.22 |
| 70-84% | 0.38 |
| 85-94% | 0.55 |
| 95-99% | 0.78 |
| 100% | 1.00 |

### Bonuses
- +0.05 for fixing race conditions (detected by -race flag)
- +0.08 for each security fix
- +0.10 for fixing all concurrency bugs
- +0.15 for complete fix (all bugs)

### Penalties
- -0.15 for regressions (breaking previously passing tests)

## Hints

1. **Start with Setup**: Fix L1 (init order) first - many tests depend on proper initialization

2. **Use the Race Detector**: `go test -race` will catch concurrency issues immediately

3. **Check Error Handling**: Search for `_ = ` and `err :=` patterns in nested scopes

4. **Review Deferred Calls**: Look for `defer rows.Close()` patterns - are they always reached?

5. **Crypto Review**: `math/rand` should never be used for cryptographic purposes

6. **Path Validation**: Consider URL encoding, null bytes, and symlinks

## Verification

After making fixes, verify with:

```bash
# Run all tests with race detection
go test -race -v ./...

# Run specific test
go test -race -v ./tests/unit/storage_test.go

# Run tests with coverage
go test -race -coverprofile=coverage.out ./...
go tool cover -html=coverage.out

# Check for race conditions specifically
go test -race ./... 2>&1 | grep -A 10 "DATA RACE"
```

## Architecture Notes

```
cloudvault/
├── cmd/server/ # Application entry point
├── internal/
│ ├── config/ # Configuration loading
│ ├── handlers/ # HTTP handlers
│ ├── middleware/ # Auth, rate limiting
│ ├── models/ # Data models
│ ├── repository/ # Database access
│ └── services/ # Business logic
│ ├── storage/ # File storage operations
│ ├── sync/ # Synchronization logic
│ ├── versioning/ # File versioning
│ └── notification/# Real-time notifications
├── pkg/
│ ├── crypto/ # Encryption utilities
│ └── utils/ # Path utilities
├── tests/
│ ├── unit/ # Unit tests
│ ├── integration/ # Integration tests
│ └── security/ # Security tests
└── environment/ # RL environment wrapper
```

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter. Each scenario describes symptoms, not solutions - use them to practice investigation skills:

| Scenario | Type | Description |
|----------|------|-------------|
| [01-memory-leak-incident.md](scenarios/01-memory-leak-incident.md) | PagerDuty Alert | Memory growing unbounded, goroutine counts increasing, OOM kills |
| [02-security-audit-findings.md](scenarios/02-security-audit-findings.md) | Security Report | Pentest findings including weak crypto, path traversal, IDOR, SQLi |
| [03-sync-race-conditions.md](scenarios/03-sync-race-conditions.md) | Customer Escalation | Data corruption during concurrent sync operations |
| [04-rate-limiter-bypass.md](scenarios/04-rate-limiter-bypass.md) | Slack Discussion | Rate limiting ineffective under concurrent load |
| [05-database-connection-exhaustion.md](scenarios/05-database-connection-exhaustion.md) | Grafana Alert | Connection pool exhausted, query timeouts |

These scenarios are designed to help you:
- Practice reading production logs and stack traces
- Identify patterns that indicate specific bug categories
- Understand how bugs manifest as user-visible symptoms
- Connect symptoms to root causes in code

Good luck! Remember: Go's error handling is explicit for a reason. Don't ignore those errors!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Folder sharing, multi-backend storage, sync optimization, versioning API, distributed rate limiter |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | File deduplication, thumbnail generation, full-text search indexer |

These tasks test different software engineering skills while using the same codebase.
