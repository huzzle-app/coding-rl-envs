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
| Setup/DI Config (L) | 4 | Circular DI, AddSingleton vs AddScoped, IOptions mismatch, middleware ordering |
| Async/Await (A) | 5 | Task.Result deadlock, ConfigureAwait, async void, ValueTask double-await, fire-and-forget |
| Nullable/Value Types (B) | 4 | null! suppression, struct mutation via interface, default struct, boxed enum equality |
| LINQ/IQueryable (C) | 4 | Deferred execution, client-side eval, closure capture, IEnumerable vs IQueryable |
| IDisposable/Resources (D) | 4 | DbContext scope leak, event handler leak, HttpClient per-request, IAsyncDisposable |
| EF Core (E) | 4 | Change tracker stale cache, OwnsOne missing, Include cartesian explosion, nvarchar(max) |
| Security (I) | 4 | ExecuteSqlRaw injection, Path.Combine injection, JWT weak key, AllowAnonymous override |

## Key Notes

- Setup bugs (L1-L4) block startup - fix circular DI dependency first
- C#-specific pitfalls: Task.Result deadlocks, ValueTask can only be awaited once, struct boxing creates copies
- Some bugs have dependencies requiring specific fix ordering

## Success Criteria

All tests pass when running `dotnet test`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Patient Medical History Timeline, Notification Channel Consolidation, Appointment Query Optimization, Bulk Patient Operations, Redis Cache Migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Prescription Validation Service, Appointment Reminder System, Lab Results Integration |

These tasks test different software engineering skills while using the same codebase.
