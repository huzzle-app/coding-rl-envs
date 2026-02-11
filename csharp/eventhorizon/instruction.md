# EventHorizon - Distributed Event Ticketing Platform

## Architecture

10 ASP.NET Core microservices + shared library:

| Service | Port | Purpose |
|---------|------|---------|
| Gateway | 5000 | REST API entry point, rate limiting |
| Auth | 5001 | JWT authentication, RBAC |
| Events | 5002 | Event CRUD, scheduling |
| Tickets | 5003 | Ticket inventory, seat maps |
| Orders | 5004 | Order lifecycle, sagas |
| Payments | 5005 | Payment processing, refunds |
| Venues | 5006 | Venue management, layouts |
| Notifications | 5007 | SignalR real-time push |
| Analytics | 5008 | Sales analytics, reporting |
| Search | 5009 | Full-text search, filtering |

## Getting Started

```bash
# Start services
docker compose up -d

# Run tests
dotnet test

# Or run in Docker
docker compose -f docker-compose.test.yml up --build
```

## Key Notes

- Setup bugs block startup - fix circular DI and DbContext registration first
- 67% of bugs have explicit prerequisites with chains up to depth 5
- Bugs span multiple services - a fix in shared library may unblock downstream tests

## Success Criteria

All tests pass when running `dotnet test`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Dynamic Pricing, Order Saga, Search Caching, Bulk Ops, Event Sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Waitlist Management, Ticket Transfer, Venue Optimizer |

These tasks test different software engineering skills while using the same codebase.
