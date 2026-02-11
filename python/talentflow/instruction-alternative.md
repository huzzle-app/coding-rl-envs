# TalentFlow - Alternative Tasks

## Overview

This document contains 5 alternative engineering tasks for the TalentFlow Django talent management platform. These tasks cover feature development, refactoring, performance optimization, API extension, and migration.

## Environment

- **Language**: Python (Django)
- **Infrastructure**: PostgreSQL, Redis, Celery
- **Difficulty**: Senior Engineer

## Tasks

### Task 1: LinkedIn Profile Import (Feature Development)
Add the ability to import candidate profiles directly from LinkedIn URLs. Extract name, headline, experience, education, and skills from public profiles.

### Task 2: Extract Interview Scheduling Service (Refactoring)
Consolidate scattered scheduling logic from `apps/interviews/scheduling.py`, `apps/interviews/views.py`, and `apps/jobs/views.py` into a dedicated `InterviewSchedulingService` class.

### Task 3: Candidate Matching at Scale (Performance Optimization)
Optimize `calculate_overall_match_score` to handle 10,000+ candidates in under 5 seconds using batch queries and caching.

### Task 4: Bulk Candidate Import API (API Extension)
Add `POST /api/candidates/import/bulk` endpoint accepting CSV uploads with validation, partial success handling, and async processing for large files.

### Task 5: Async Email Notifications (Migration)
Migrate from synchronous `send_mail` to a queue-based `EmailService` with database templates, delivery tracking, and retry logic.

## Getting Started

```bash
docker compose up -d
pytest
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
