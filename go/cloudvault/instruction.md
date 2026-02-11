# CloudVault - Go Cloud Storage and File Sync Service

 in a cloud storage and file sync service built with Go 1.21, Gin, PostgreSQL, Redis, and MinIO.

## Bug Categories

| Category | Count | Description |
|----------|-------|-------------|
| Concurrency | 5 | Goroutine leaks, race conditions, channel deadlocks, WaitGroup misuse, mutex copy |
| Memory & Slices | 4 | Slice bounds, nil map write, slice aliasing, memory leak |
| Database | 4 | Transaction rollback, connection leak, prepared statement leak, N+1 query |
| Error Handling | 3 | Ignored errors, error shadowing, nil interface check |
| Security | 4 | Weak crypto (math/rand), path traversal, SQL injection, IDOR |
| Configuration | 5 | Init order, env type parsing, missing validation |

## Getting Started

1. Read `TASK.md` for detailed bug descriptions and testing instructions
2. Start services: `docker compose up -d`
3. Run tests: `go test -race -v ./...`
4. Fix bugs to increase test pass rate

## Success Criteria

- All tests passing
- No race conditions detected
- All security vulnerabilities patched
- Proper error handling throughout
- Configuration validated correctly

Estimated time: 2-4 hours (Senior difficulty)

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Folder sharing, multi-backend storage, sync optimization, versioning API, distributed rate limiter |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | File deduplication, thumbnail generation, full-text search indexer |

These tasks test different software engineering skills while using the same codebase.
