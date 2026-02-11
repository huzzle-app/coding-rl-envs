# TalentFlow - Greenfield Implementation Tasks

## Overview

This document contains 3 greenfield implementation tasks for the TalentFlow Django talent management platform. Each task requires implementing a new module from scratch with full interface contracts provided.

## Environment

- **Language**: Python (Django)
- **Infrastructure**: PostgreSQL, Redis, Celery
- **Difficulty**: Senior Engineer

## Tasks

### Task 1: Onboarding Workflow Service
Create an `OnboardingService` that manages post-hire onboarding workflows including document collection, equipment provisioning, system access setup, and first-day scheduling.

**Interface**: `start_onboarding()`, `get_workflow_status()`, `complete_step()`, `get_pending_tasks()`, `send_reminder()`

### Task 2: Skills Assessment Engine
Create a `SkillsAssessmentEngine` that administers and scores technical assessments with multiple question types, timed attempts, and automated scoring.

**Interface**: `create_assessment()`, `start_attempt()`, `submit_answer()`, `complete_attempt()`, `get_candidate_results()`, `generate_assessment_report()`

### Task 3: Employee Referral Program Service
Create a `ReferralService` that manages employee referrals with duplicate detection, status tracking, reward calculations, and leaderboards.

**Interface**: `submit_referral()`, `get_referrer_dashboard()`, `update_referral_status()`, `calculate_reward()`, `process_reward()`, `get_referral_leaderboard()`

## Getting Started

```bash
docker compose up -d
pytest
```

## Success Criteria

Implementation meets the interface contracts and acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
