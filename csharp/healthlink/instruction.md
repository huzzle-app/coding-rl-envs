# HealthLink - Healthcare Appointment & Patient Management Platform

## Getting Started

```bash
# Start services
docker compose up -d

# Run tests
dotnet test
```

## Bug Categories

| Category | Count | Description |
|----------|-------|-------------|
| Setup/DI Config (L) | 4 | Circular DI, service lifetime, configuration binding, middleware ordering |
| Async/Await (A) | 5 | Deadlocks, async void, ValueTask misuse, fire-and-forget |
| Nullable/Value Types (B) | 4 | Null suppression, struct mutation, default values, boxed equality |
| LINQ/IQueryable (C) | 4 | Deferred execution, client-side eval, closure capture, return types |
| IDisposable/Resources (D) | 4 | Scope leaks, event handler leaks, HttpClient management, async disposal |
| EF Core (E) | 4 | Change tracker, value object mapping, query performance, column sizing |
| Security (I) | 4 | SQL injection, path traversal, JWT key strength, authorization bypass |

## Key Notes

- Setup bugs block startup - fix DI issues first
- C#-specific pitfalls: Task.Result deadlocks, ValueTask single-use, struct boxing
- Run `dotnet test` frequently to track progress

## Success Criteria

All tests pass when running `dotnet test`.
