# MediaFlow - Greenfield Implementation Tasks

## Overview

MediaFlow supports three comprehensive greenfield implementation tasks that test the ability to build new services from scratch within an existing distributed architecture. Each task requires implementing a complete microservice following Express + Jest patterns, RabbitMQ event integration, and the shared service module structure.

## Environment

- **Language**: JavaScript (Node.js)
- **Infrastructure**: RabbitMQ, PostgreSQL, Redis, MinIO, Consul
- **Difficulty**: Principal (8-16 hours)

## Tasks

### Task 1: Content Recommendation Engine

Implement a machine learning-inspired recommendation service (`services/content-recommender/`, port 3010) that provides personalized video suggestions using collaborative filtering and content-based similarity algorithms. The engine tracks user interactions (views, likes, shares, completes, skips), computes video similarity scores, and surfaces trending content with time decay.

**Service Interface**:
- `ContentRecommendationEngine`: Provides personalized recommendations with configurable context (home, watch_next, search), records user interactions for model updates, computes inter-video similarity (0.0-1.0 scores), rebuilds user preference models, and retrieves trending videos with time decay.
- `SimilarityCalculator`: Calculates content-based similarity from metadata, collaborative similarity from co-viewing patterns (Jaccard coefficient), and builds similarity matrices.
- `TrendingTracker`: Records engagement signals (views, likes, comments, shares), computes trending scores with configurable half-life decay (6 hours default), and returns top trending videos with ranking velocity.

**Requirements**: 25+ unit tests (similarity accuracy, trending decay, user models, edge cases), 10+ integration tests (end-to-end flow, event consumption, cache invalidation), similarity matrix <100ms for 1000 videos, recommendation latency <50ms cached.

### Task 2: Video Clip Generator Service

Implement a clip generation service (`services/clip-generator/`, port 3011) that creates short-form video clips from full-length videos, supporting automatic highlight detection and social media format exports (Instagram Reels 9:16 max 90s, TikTok 9:16 max 3min, YouTube Shorts 9:16 max 60s, Twitter/X 16:9 or 1:1 max 2:20).

**Service Interface**:
- `ClipGeneratorService`: Creates clips from source videos with configurable quality/audio/fade/watermark settings, tracks job status (pending, processing, completed, failed, cancelled), cancels pending jobs, detects highlight moments, exports to target formats, and lists available export formats.
- `HighlightDetector`: Analyzes audio peaks, detects scene changes with configurable threshold (0.3 default), scores segments by engagement potential, and generates automatic highlights with duration/clip count bounds.
- `ClipExporter`: Exports clips to Instagram Reels, TikTok, YouTube Shorts, Twitter/X with aspect ratio conversion, smart crop options (horizontal: center/left/right/auto, vertical: center/top/bottom/auto, face detection), and generates thumbnails at specified timestamps.

**Requirements**: 30+ unit tests (request validation, highlight algorithms, format specs, state machine), 15+ integration tests (end-to-end creation, job queue processing, storage integration, event emission), 5+ contract tests (transcode service API, storage API), async job processing via RabbitMQ, MinIO storage integration.

### Task 3: Content Moderation Queue

Implement a moderation service (`services/moderation/`, port 3012) that manages a content review workflow with automated pre-screening, human review with SLA tracking, and enforcement action execution (remove, age-restrict, warning, strike, suspend, terminate).

**Service Interface**:
- `ModerationQueueManager`: Submits content for review, retrieves cases by ID, fetches pending cases for reviewers with filtering (by status, priority, violation type, date range), assigns cases to reviewers, submits review decisions, escalates to senior reviewers, and computes queue statistics.
- `ContentPrescreener`: Pre-screens videos before human review, checks metadata against policy rules (spam, harassment, hate_speech, violence, nudity, copyright, misinformation, dangerous), analyzes thumbnails for compliance, calculates risk scores (0.0-1.0), and supports custom rule addition with priority-based evaluation.
- `ReviewWorkflowManager`: Manages review sessions with SLA configuration, checks SLA deadline status for pending cases, computes reviewer performance metrics (cases reviewed, avg time, accuracy rate, escalation rate, decision breakdown), and auto-assigns cases based on reviewer availability/expertise.
- `EnforcementActionHandler`: Executes enforcement actions, removes videos with reason logging, age-restricts content, issues creator warnings, applies strikes with history tracking, and processes appeals with audit logging.

**Requirements**: 35+ unit tests (rule evaluation, risk scoring, state machine, SLA calculation, strike accumulation), 20+ integration tests (full workflow, event consumption for video.uploaded, enforcement execution, appeal flow), 5+ security tests (reviewer authorization, audit integrity, action authorization), priority queue via RabbitMQ, case state machine (pending→in_review→escalated→decided→appealed→closed).

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/js/mediaflow
docker compose up -d
npm install
npm test
```

Review existing service patterns in `services/` directory and the shared module structure in `shared/`. Each new service must:
- Export Express app in `src/index.js`
- Implement `GET /health` endpoint returning `{ status: 'healthy', service: '<name>' }`
- Use `EventBus` from `shared/events/` for pub/sub
- Use `ServiceClient` from `shared/clients/` for inter-service communication
- Follow Jest patterns in `tests/` with `beforeEach` isolation, mocked dependencies, and `global.testUtils` helpers

## Success Criteria

Each task is complete when:
1. All unit, integration, and contract/security tests pass
2. Service implements the full interface contract with proper JSDoc comments
3. Error handling and edge cases are covered (empty history, new users, cold start, buffer exhaustion, SLA overdue)
4. Services integrate properly with RabbitMQ event bus and inter-service communication
5. Performance targets are met (similarity <100ms, recommendations <50ms, moderation rule checks <1s)
6. Code follows existing patterns for consistency with the platform

Detailed requirements and acceptance criteria for each task are defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
