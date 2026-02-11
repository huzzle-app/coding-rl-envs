# MediaFlow - Distributed Video Streaming Platform Debug Challenge

## Objective

You are debugging a distributed video streaming platform built with Node.js microservices. The application has **90 intentional bugs** that cause tests to fail. Your goal is to identify and fix all bugs to achieve **100% test pass rate**.

**Difficulty Level**: Principal/Staff Engineer (8-16 hours expected)

## Getting Started

```bash
# Install dependencies
npm install

# Start services with Docker
docker compose up -d

# Run tests (will fail initially)
npm test

# Or with Docker
docker compose --profile test up --build
```

## Architecture

```
mediaflow/
├── services/
│ ├── gateway/ # API Gateway (port 3000)
│ ├── auth/ # Authentication (port 3001)
│ ├── users/ # User Management (port 3002)
│ ├── upload/ # Video Uploads (port 3003)
│ ├── transcode/ # Video Transcoding (port 3004)
│ ├── catalog/ # Video Metadata (port 3005)
│ ├── streaming/ # Video Delivery/CDN (port 3006)
│ ├── recommendations/ # ML Recommendations (port 3007)
│ ├── billing/ # Subscriptions (port 3008)
│ └── analytics/ # View Tracking (port 3009)
├── shared/ # Shared modules (clients, events, utils)
├── infrastructure/ # Service configs
├── tests/
│ ├── unit/ # Unit tests
│ ├── integration/ # Integration tests
│ ├── contract/ # Contract tests
│ ├── chaos/ # Chaos engineering tests
│ ├── security/ # Security tests
│ ├── performance/ # Performance tests
│ └── system/ # System tests
└── environment/ # RL environment wrapper
```

## Infrastructure

- **RabbitMQ 3.12** - Message queue (port 5672)
- **PostgreSQL 15** x2 - Main DB (5432), Analytics DB (5433)
- **Redis 7** - Caching (port 6379)
- **MinIO** - S3-compatible storage (port 9000)
- **Consul 1.16** - Service discovery (port 8500)

## Known Issues

The test suite has multiple failures across core modules. Issues appear to span business logic and infrastructure layers.

## Key Challenges

1. **Multi-Service Debugging**: Bugs span multiple services with complex interactions
2. **Event Sourcing**: Temporal bugs requiring specific event sequences
3. **Distributed Systems**: Race conditions, split-brain, lock timeouts
4. **Cascading Failures**: Fixing one bug reveals others
5. **No Single Entry Point**: Setup bugs block different services independently

## Test Categories

| Category | Tests | Weight |
| Unit | 150 | 1.0x |
| Integration | 120 | 1.5x |
| Contract | 50 | 2.0x |
| Chaos | 40 | 3.0x |
| Security | 60 | 2.5x |
| Performance | 40 | 2.0x |
| System | 50 | 3.0x |

## Hints

### Setup Bugs (Fix These First!)

1. **L1**: Check `shared/index.js` - circular import chain
2. **L2**: Check RabbitMQ exchange declarations in event handlers
3. **L4**: Check `services/gateway/src/services/registry.js` - startup race

### Common Bug Patterns

- **Off-by-one**: Circuit breaker uses `>` instead of `>=`
- **Float precision**: Bitrate and currency calculations
- **Missing await**: Async operations not awaited
- **Race conditions**: Concurrent updates without locking
- **Type coercion**: process.env values are strings

### Key Files to Examine

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter:

| Scenario | Type | Description |
| [01-video-quality-complaints.md](./scenarios/01-video-quality-complaints.md) | Customer Reports | Poor video quality in high-motion content |
| [02-billing-discrepancies.md](./scenarios/02-billing-discrepancies.md) | Customer Escalation | Proration errors and double charges |
| [03-cache-stampede-incident.md](./scenarios/03-cache-stampede-incident.md) | PagerDuty Incident | Cache miss thundering herd during popular release |
| [04-security-audit-findings.md](./scenarios/04-security-audit-findings.md) | Security Report | SQL injection and JWT validation weaknesses |
| [05-distributed-system-failures.md](./scenarios/05-distributed-system-failures.md) | Incident Report | Split-brain and event ordering violations |

Each scenario describes **symptoms only** without revealing the fixes. Use them to practice realistic debugging workflows.

## Success Criteria

- All 531 tests pass
- All 10 services start without errors
- No security vulnerabilities detected
- Event sourcing maintains consistency
- Distributed locks prevent split-brain

## Reward Function

```
Pass Rate → Reward (Very Sparse)
< 10% → 0.00
10-25% → 0.05
25-40% → 0.12
40-55% → 0.22
55-70% → 0.38
70-85% → 0.55
85-95% → 0.78
100% → 1.00
```

Additional bonuses:
- Category completion: +0.03 per fully passing category
- Chaos test bonus: +0.10 for all chaos tests passing
- Bug fix bonus: up to +0.10 for fixing specific bugs
- Efficiency bonus: +0.05 for fast completion (only at 100%)
- Regression penalty: -0.15 for breaking previously passing tests

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | DVR Support, Billing Precision, Adaptive Bitrate, Watchlist API, Event Schema |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Content Recommender, Video Clip Generator, Content Moderation |

These tasks test different software engineering skills while using the same codebase.
