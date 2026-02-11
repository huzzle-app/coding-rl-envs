# TalentFlow - Alternative Tasks

Beyond debugging, these tasks test feature development, refactoring, optimization, API extension, and migration capabilities.

---

## Task 1: Feature Development - LinkedIn Profile Import

**Type:** Feature Development

**Description:**
Add the ability to import candidate profiles directly from LinkedIn. When a recruiter pastes a LinkedIn profile URL, the system should fetch the public profile data and create a new candidate record with pre-populated fields.

**Acceptance Criteria:**
- New endpoint `POST /api/candidates/import/linkedin` accepts a LinkedIn URL
- System extracts name, headline, experience, education, and skills from the profile
- Creates a Candidate record with `source='linkedin'` and stores the original URL
- Handles rate limiting from LinkedIn gracefully (retry with backoff)
- Returns the created candidate ID and a summary of imported fields
- Fails gracefully if profile is private or URL is invalid

**Test Command:**
```bash
python manage.py test apps.candidates.tests.test_linkedin_import
```

---

## Task 2: Refactoring - Extract Interview Scheduling Service

**Type:** Refactoring

**Description:**
The interview scheduling logic is currently spread across `apps/interviews/scheduling.py`, `apps/interviews/views.py`, and `apps/jobs/views.py`. Extract this into a dedicated `InterviewSchedulingService` class that encapsulates all scheduling logic with a clean interface.

**Acceptance Criteria:**
- New `InterviewSchedulingService` class in `apps/interviews/services.py`
- All scheduling logic consolidated: availability checking, conflict detection, timezone handling
- Views delegate to the service (no business logic in views)
- Service is stateless and can be easily mocked for testing
- All existing tests continue to pass
- No changes to API contracts or database schema

**Test Command:**
```bash
python manage.py test apps.interviews.tests
```

---

## Task 3: Performance Optimization - Candidate Matching at Scale

**Type:** Performance Optimization

**Description:**
The current `calculate_overall_match_score` function in `apps/jobs/matching.py` performs N database queries per candidate when ranking candidates for a job. Optimize this to handle 10,000+ candidates efficiently using batch queries, caching, or query optimization.

**Acceptance Criteria:**
- `rank_candidates_for_job` handles 10,000 candidates in under 5 seconds
- Reduces database queries from O(N) to O(1) or O(log N)
- Match scores remain identical to the original algorithm
- Memory usage stays under 500MB for large candidate pools
- Add a benchmark test that verifies performance requirements

**Test Command:**
```bash
python manage.py test apps.jobs.tests.test_matching_performance
```

---

## Task 4: API Extension - Bulk Candidate Import

**Type:** API Extension

**Description:**
Add a bulk import API that accepts a CSV file containing candidate data and creates multiple candidates in a single request. Support validation, partial success (some rows fail, others succeed), and progress tracking for large imports.

**Acceptance Criteria:**
- New endpoint `POST /api/candidates/import/bulk` accepts multipart CSV upload
- CSV columns: first_name, last_name, email, phone, source, skills (comma-separated), years_experience
- Validates all rows before importing (email format, required fields)
- Returns detailed results: success count, failure count, and per-row errors
- Handles files up to 10,000 rows
- Duplicate emails within the file or existing in DB are reported as errors
- Async processing with status endpoint for files > 1,000 rows

**Test Command:**
```bash
python manage.py test apps.candidates.tests.test_bulk_import
```

---

## Task 5: Migration - Async Email Notifications

**Type:** Migration

**Description:**
Currently, email notifications in `apps/candidates/tasks.py` use Django's `send_mail` synchronously within Celery tasks. Migrate to a queue-based async pattern using a dedicated email service that supports templates, tracking, and retry logic.

**Acceptance Criteria:**
- New `EmailService` class in `apps/notifications/services.py`
- All `send_mail` calls replaced with `EmailService.queue_email()`
- Email templates stored in database (EmailTemplate model) instead of hardcoded strings
- Track email status: queued, sent, delivered, bounced, opened
- Automatic retry with exponential backoff for failed sends
- New Celery task `process_email_queue` handles batch sending
- Admin interface to view email logs and template management

**Test Command:**
```bash
python manage.py test apps.notifications.tests
```
