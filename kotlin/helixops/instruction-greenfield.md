# HelixOps - Greenfield Implementation Tasks

## Overview

HelixOps supports 3 greenfield implementation tasks requiring new modules from scratch while following existing architectural patterns. Each task implements enterprise-grade functionality integrating with core services: SSO integration for federated authentication, document templates for parameterized document generation, and API usage analytics for consumption tracking and billing.

## Environment

- **Language**: Kotlin
- **Infrastructure**: Docker compose with PostgreSQL, Redis, and Ktor
- **Difficulty**: Apex-Principal (new modules use production patterns from auth, documents, and gateway)

## Tasks

### Task 1: SSO Integration Service (Greenfield)

Implement a new `sso/` module supporting SAML 2.0 and OIDC federated authentication. The service initiates authentication flows, processes responses with assertion validation, manages identity provider configurations, and handles Single Logout. Integration points include calling `AuthService.issueToken()`, using `JwtProvider` for signing, publishing events via `EventBus`, and caching metadata via `CacheManager`.

**Interface**: 11 core methods covering AuthnRequest initiation, response processing (SAML assertions, OIDC authorization codes), provider CRUD, metadata refresh, SLO initiation/processing, event streaming, and session validation. Sealed exception hierarchy for domain errors (ProviderNotFoundException, InvalidAssertionException, etc.).

**Acceptance**: All interface methods, 30+ unit tests (SAML/OIDC flows, provider operations, metadata, SLO, errors), integration tests with mock IdPs, thread-safe provider registry, event audit trail, tests pass with `./gradlew test`.

### Task 2: Document Template Engine (Greenfield)

Implement a new `templates/` module for parameterized document generation. The service creates templates from source, parses syntax (variables, conditionals, loops, includes), renders with data context to multiple formats, and saves rendered documents. Integration points include storing via `DocumentService`, caching via `CacheManager`, event publishing, and observability logging.

**Interface**: 10 core methods covering template CRUD (create, update, get, list, delete), rendering with context, render-and-save, validation, schema extraction, preview, and cloning. Template syntax includes `{{variable}}`, `{{#if}}`, `{{#each}}`, includes, and 6 built-in helpers (uppercase, lowercase, dateFormat, numberFormat, truncate, join).

**Acceptance**: All interface methods, 40+ unit tests (CRUD, variable substitution, conditionals, loops, includes, helpers, errors), integration tests with DocumentService, parser resilience, render stats/warnings, tests pass with `./gradlew test`.

### Task 3: API Usage Analytics Service (Greenfield)

Implement a new `usage/` module for request tracking, rate limiting, quota management, and billing. The service records requests, enforces 4 rate limit algorithms (fixed window, sliding window, token bucket, leaky bucket), tracks quotas, aggregates usage by period/granularity, detects anomalies, and generates billing reports. Integration points include gateway middleware interception, billing integration, event publishing, and metrics export.

**Interface**: 12 core methods covering request recording, rate limit checks/configuration, usage statistics (by period/endpoint/history), quota configuration/status, rate limit resets, billing report generation, event streaming, top consumer ranking, and anomaly detection.

**Acceptance**: All interface methods, 45+ unit tests (recording, 4 algorithms, quotas, aggregation, billing, anomalies, concurrency, edge cases), load testing (10x capacity improvement), rate limit checks <1ms, memory-bounded with eviction, tests pass with `./gradlew test`.

## Getting Started

```bash
./gradlew test
```

## Success Criteria

Implementation meets interface contracts and acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md), following architectural patterns from existing modules (auth, documents, gateway, billing).
