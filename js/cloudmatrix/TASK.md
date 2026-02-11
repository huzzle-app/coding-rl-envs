# CloudMatrix - Real-Time Collaborative Workspace Platform Debug Challenge

## Objective

You are debugging a real-time collaborative workspace platform built with Node.js microservices. The application has **120 intentional bugs** that cause tests to fail. Your goal is to identify and fix all bugs to achieve **100% test pass rate**.

**Difficulty Level**: Distinguished Engineer (24-48 hours expected)

## Getting Started

```bash
# Install dependencies
npm install

# Start services with Docker
docker compose up -d

# Run tests (will fail initially)
npm test

# Or with Docker
docker compose -f docker-compose.test.yml up --build
```

## Architecture

```
cloudmatrix/
├── services/
│ ├── gateway/ # API Gateway (port 3000)
│ ├── auth/ # Authentication (port 3001)
│ ├── users/ # User Profiles & Teams (port 3002)
│ ├── documents/ # Document CRUD & Versioning (port 3003)
│ ├── presence/ # Real-Time Presence & Cursors (port 3004)
│ ├── comments/ # Threaded Comments (port 3005)
│ ├── versions/ # Version History & Branching (port 3006)
│ ├── search/ # Full-Text Search & Indexing (port 3007)
│ ├── notifications/ # Push/Email/In-App Notifications (port 3008)
│ ├── storage/ # File Uploads & CDN (port 3009)
│ ├── analytics/ # Usage Analytics (port 3010)
│ ├── billing/ # Subscriptions & Pricing (port 3011)
│ ├── permissions/ # ACL & Sharing (port 3012)
│ ├── webhooks/ # Event Webhooks (port 3013)
│ └── admin/ # Admin Dashboard (port 3014)
├── shared/ # Shared modules (clients, events, utils, realtime)
├── tests/ # 750+ tests
│ ├── unit/
│ ├── integration/
│ ├── contract/
│ ├── chaos/
│ ├── security/
│ ├── performance/
│ └── system/
└── environment/ # RL environment wrapper
```

## Infrastructure

- **RabbitMQ 3.13** - Message queue (port 5672)
- **PostgreSQL 16** x4 - docs_db (5432), users_db (5433), analytics_db (5434), billing_db (5435)
- **Redis 7** - Caching, pub/sub, presence (port 6379)
- **Consul 1.17** - Service discovery (port 8500)
- **MinIO** - S3-compatible file storage (port 9000)
- **Elasticsearch 8** - Full-text search (port 9200)

## Known Issues

The codebase needs attention. Failures span configuration, service logic, and integration points.

## Key Challenges

1. **Real-Time Collaboration**: CRDT/OT merge logic, cursor synchronization, operational transform composition
2. **15-Service Architecture**: Bugs span multiple services with complex interactions and message flows
3. **WebSocket Management**: Connection lifecycle, reconnection, presence tracking, binary frames
4. **Event Sourcing**: Temporal bugs requiring specific event sequences and ordering guarantees
5. **Distributed Systems**: Race conditions, split-brain, lock timeouts, saga compensation
6. **No Single Entry Point**: Setup bugs block different services independently

## Test Categories

| Category | Tests | Weight |
| Unit | 250 | 1.0x |
| Integration | 150 | 1.5x |
| Contract | 50 | 2.0x |
| Chaos | 75 | 3.0x |
| Security | 75 | 2.5x |
| Performance | 50 | 2.0x |
| System | 100 | 3.0x |

## Hints

### Setup Bugs (Fix These First!)

1. **L1**: Check `shared/index.js` - circular import chain between clients, events, utils, and realtime
2. **L2**: Check RabbitMQ exchange declarations in event handlers - exchange not declared before binding
3. **L9**: Check WebSocket server setup in presence service - missing await on bind
4. **L13**: Check search service - Elasticsearch index mapping not created on startup

### Common Bug Patterns

- **CRDT merge**: Concurrent operations produce different results depending on order
- **OT composition**: Transform function not commutative leads to divergence
- **Missing await**: Async operations not awaited especially in initialization
- **Float precision**: Cursor positions and billing calculations
- **Race conditions**: Concurrent document edits, permission checks, cache updates
- **Type coercion**: process.env values are always strings
- **Prototype pollution**: Document merge using Object.assign with user input

### Key Files to Examine

## Success Criteria

- All 750+ tests pass
- All 15 services start without errors
- No security vulnerabilities detected
- Real-time collaboration maintains consistency
- Event sourcing maintains ordering guarantees
- Distributed locks prevent split-brain

## Reward Function

```
Pass Rate -> Reward (Very Sparse)
< 10% -> 0.00
10-25% -> 0.05
25-40% -> 0.12
40-55% -> 0.22
55-70% -> 0.38
70-85% -> 0.55
85-95% -> 0.78
100% -> 1.00
```

Additional bonuses:
- Category completion: +0.03 per fully passing category
- Chaos test bonus: +0.10 for all chaos tests passing
- Bug fix bonus: up to +0.10 for fixing specific bugs
- Efficiency bonus: +0.05 for fast completion (only at 100%)
- Regression penalty: -0.15 for breaking previously passing tests

## Debugging Scenarios

For realistic debugging practice, see the [scenarios/](./scenarios/) directory which contains production-style incidents and reports:

| Scenario | Type | Focus Areas |
| [01-realtime-collaboration-incident](./scenarios/01-realtime-collaboration-incident.md) | PagerDuty | CRDT merge, OT composition, cursor tracking, undo stack |
| [02-security-audit-report](./scenarios/02-security-audit-report.md) | Security Audit | SQL injection, SSRF, prototype pollution, ReDoS, JWT |
| [03-websocket-connection-issues](./scenarios/03-websocket-connection-issues.md) | Customer Escalation | Connection leaks, reconnection backoff, presence cleanup |
| [04-search-indexing-failures](./scenarios/04-search-indexing-failures.md) | Slack Thread | Search injection, index pipeline, autocomplete cache |
| [05-service-startup-failures](./scenarios/05-service-startup-failures.md) | PagerDuty | Circular imports, async initialization, missing exchanges |

These scenarios describe **symptoms only** - use them to practice realistic debugging workflows.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Usage-based billing, shared permissions engine, search optimization, audit logging, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Usage Analytics Aggregator, Team Management Service, Webhook Delivery System |

These tasks test different software engineering skills while using the same codebase.

Good luck!
