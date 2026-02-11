# Support Escalation: Candidate Match Scores Not Calculating

## Zendesk Ticket #91847

**Priority**: Urgent
**Customer**: Enterprise HR Solutions (Enterprise Tier)
**Account Value**: $380,000 ARR
**CSM**: Rachel Martinez
**Created**: 2024-01-20 10:45 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> We're using TalentFlow's batch scoring feature to calculate match scores for all candidates against our open positions. The `calculate_match_scores_for_job` task completes successfully according to the logs, but when we check the results, all candidates show a match score of 0 or null.
>
> We've tried running the batch job multiple times over the past three days with the same result. Individual scoring through the UI seems to work, but batch scoring through the async task returns nothing.
>
> This is critical for us - we have 500+ candidates and 30 open positions, and we can't manually score each combination.

---

## Investigation Timeline

**2024-01-20 11:00 UTC**: Initial investigation started

**11:15 UTC**: Confirmed task execution in Celery logs
```
[2024-01-20 11:02:15,234] INFO Task apps.jobs.tasks.calculate_match_scores_for_job[abc123] started
[2024-01-20 11:02:15,567] INFO Scoring 50 candidates for job 'Senior Engineer'
[2024-01-20 11:02:18,891] INFO Task apps.jobs.tasks.calculate_match_scores_for_job[abc123] succeeded
```

**11:20 UTC**: Checked database - match_score column is NULL for all affected candidates

**11:30 UTC**: Attempted manual reproduction with internal test data - same issue

---

## Technical Analysis

### Slack Thread: #eng-backend

**@dev.sarah** (11:35):
> Looking at the Celery task code. It uses a chord pattern - fans out scoring to individual candidates, then aggregates results.

**@dev.marcus** (11:40):
> Can you check the individual task results? Maybe the scoring tasks are failing silently?

**@dev.sarah** (11:45):
> That's the weird part. Looking at `score_single_candidate` task... it has `ignore_result=True` decorator. That breaks chord patterns!

**@dev.marcus** (11:48):
> Oh no. With `ignore_result=True`, the chord header tasks don't store their results in the backend. So when the callback runs, it gets a list of None values.

**@dev.sarah** (11:52):
> Let me trace through:
> 1. `calculate_match_scores_for_job` creates chord with many `score_single_candidate` tasks
> 2. Each `score_single_candidate` runs and calculates score correctly
> 3. But `ignore_result=True` means results are discarded
> 4. Chord callback `aggregate_scores` receives `[None, None, None, ...]`
> 5. Function tries to process null results, writes nothing to DB

**@dev.marcus** (11:55):
> Can you confirm by checking Flower or the result backend?

**@dev.sarah** (11:58):
> Confirmed. In Flower, I can see `score_single_candidate` tasks completing with "SUCCESS" but result shows as "None" for every single one.

---

## Flower Dashboard Output

```
Task: apps.jobs.tasks.score_single_candidate
State: SUCCESS
Result: None  # <-- Should be the score dictionary!
Runtime: 0.234s
Worker: celery@worker-1

Task: apps.jobs.tasks.score_single_candidate
State: SUCCESS
Result: None  # <-- All tasks return None despite "SUCCESS"
Runtime: 0.189s
Worker: celery@worker-1

Task: apps.jobs.tasks.aggregate_scores (chord callback)
State: SUCCESS
Result: {"processed": 0, "errors": ["No valid scores to aggregate"]}
Runtime: 0.012s
```

---

## Code Analysis

### Current Task Definition
```python
@shared_task(ignore_result=True)  # <-- THIS IS THE PROBLEM
def score_single_candidate(candidate_id: int, job_id: int) -> dict:
    """Score a single candidate for a job."""
    # ... scoring logic that returns valid dict ...
    return {
        'candidate_id': candidate_id,
        'score': calculated_score,
        'timestamp': now.isoformat()
    }
```

### Chord Pattern Usage
```python
@shared_task
def calculate_match_scores_for_job(job_id: int) -> dict:
    """Calculate match scores for all candidates."""
    candidates = Candidate.objects.filter(...)

    # Create chord: score all candidates, then aggregate
    workflow = chord(
        group(score_single_candidate.s(c.id, job_id) for c in candidates),
        aggregate_scores.s(job_id)  # This receives [None, None, None...]
    )

    return workflow.apply_async()
```

### Aggregate Function Receiving Nulls
```python
@shared_task
def aggregate_scores(results: list, job_id: int) -> dict:
    """Aggregate individual scoring results."""
    # results = [None, None, None, ...] due to ignore_result=True!

    valid_results = [r for r in results if r is not None]
    # valid_results is empty!

    if not valid_results:
        return {'error': 'No valid scores to aggregate'}

    # ... rest of aggregation never runs
```

---

## Customer Impact

- **Affected Customers**: All enterprise customers using batch scoring
- **Feature Broken**: Candidate-job batch matching
- **Workaround**: None - manual scoring not practical at scale
- **Revenue Risk**: $380K account threatening to evaluate competitors

---

## Reproduction Steps

1. Create a job with required skills
2. Create 10+ candidates with various skill profiles
3. Call API endpoint: `POST /api/v1/jobs/{job_id}/calculate-scores/`
4. Wait for async task completion
5. Query candidates: Match scores are all NULL despite task "success"

---

## Files to Investigate

- `apps/jobs/tasks.py` - Celery task definitions (specifically `score_single_candidate`)

---

## Root Cause

The `score_single_candidate` task has `ignore_result=True` which discards task results. When used in a chord pattern, the callback receives null values instead of actual scores.

---

**Status**: ROOT CAUSE IDENTIFIED
**Assigned**: @dev.sarah
**ETA**: 2024-01-20 EOD
