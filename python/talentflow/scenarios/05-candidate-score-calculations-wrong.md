# Customer Escalation: Incorrect Candidate Match Scores

## Zendesk Ticket #93012

**Priority**: High
**Customer**: TalentAcquisition Partners (Enterprise Tier)
**Account Value**: $225,000 ARR
**CSM**: Michael Torres
**Created**: 2024-01-22 09:30 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> We've noticed that candidate match scores seem inconsistent and often lower than expected. We have a candidate who has ALL the required skills for a position with expert-level proficiency, but their match score shows as 0.79 instead of 1.0 or close to it.
>
> We're using these scores to prioritize which candidates to interview first, and if the scores are wrong, we might be missing our best candidates.

---

## Detailed Example from Customer

### Job: Senior Python Developer
**Required Skills**: Python (required), Django (required), PostgreSQL (required)
**Preferred Skills**: Redis, Docker

### Candidate: Alex Johnson
**Skills on Profile**:
- Python: Expert (5/5)
- Django: Expert (5/5)
- PostgreSQL: Advanced (4/5)
- Redis: Intermediate (3/5)
- Docker: Expert (5/5)

**Expected Score**: ~0.95-1.0 (has all required skills with high proficiency, plus both preferred skills)
**Actual Score**: 0.79

---

## Investigation

### Slack Thread: #eng-backend

**@dev.sarah** (10:15):
> Looking at the match score calculation. Something is off in the normalization.

**@dev.marcus** (10:20):
> Can you trace through a specific calculation?

**@dev.sarah** (10:25):
> Let me work through Alex Johnson's case:
> - 3 required skills, candidate has all 3
> - Required score should be: (1.0 + 1.0 + 0.84) = 2.84 for having all skills
> - But then it's divided by `len(required_skills) + 1` which is 4, not 3!

**@dev.marcus** (10:30):
> Wait, why is it adding 1 to the length?

**@dev.sarah** (10:33):
> Looking at the code:
> ```python
> required_normalized = required_score / (len(required_skills) + 1)
> ```
> This is dividing by 4 when there are 3 skills. That's wrong - it should just be `len(required_skills)`.

**@dev.marcus** (10:38):
> So even a perfect candidate can never get a perfect required score. With 3 skills, the max is 3.0 divided by 4 = 0.75. That's an artificial ceiling!

**@dev.sarah** (10:42):
> Exactly. And then that 0.75 gets multiplied by 0.8 (the required weight), giving max 0.6 from required skills. Add preferred bonus and you might get to 0.8, but never to 1.0.

---

## Code Analysis

### Matching Algorithm (apps/jobs/matching.py)

```python
def calculate_skill_match_score(candidate: Candidate, job: Job) -> float:
    required_skills = list(job.required_skills.all())
    # ...

    # Calculate required skills match
    for i in range(len(required_skills)):
        skill = required_skills[i]
        if skill.id in candidate_skills:
            proficiency = candidate_skills[skill.id]
            required_score += 0.2 + (proficiency / 5) * 0.8

    # BUG: Off-by-one error in normalization!
    required_normalized = required_score / (len(required_skills) + 1)  # Should be just len()
    # ...
```

### Impact of Bug

With 3 required skills and perfect proficiency:
- Expected: `3.0 / 3 = 1.0`
- Actual: `3.0 / 4 = 0.75`
- Maximum achievable: 75% of what it should be

---

## Additional Issues Found

### Floating Point Comparison

```python
def scores_equal(score1: float, score2: float) -> bool:
    """Check if two scores are equal."""
    return score1 == score2  # Direct equality comparison!
```

This fails for floating-point values like `0.79999999999` vs `0.80000000001`, which should be considered equal.

### Percentile Calculation Edge Case

```python
def calculate_percentile_rank(candidate_score: float, all_scores: list) -> float:
    if not all_scores:
        return 100.0  # Returns 100th percentile for empty list - misleading

    below_count = 0
    for score in all_scores:
        if score < candidate_score:  # Doesn't handle ties properly
            below_count += 1

    percentile = (below_count / len(all_scores)) * 100
    return percentile
```

If a candidate has the highest score but there are ties, they might not show as 100th percentile.

---

## Data Analysis

We analyzed 500 recent match score calculations:

| Issue | Occurrences | Impact |
|-------|-------------|--------|
| Off-by-one in normalization | 500 (100%) | All scores artificially low |
| Float comparison failures | 23 (4.6%) | Duplicate handling broken |
| Tied percentile errors | 67 (13.4%) | Rankings slightly off |

---

## Customer Impact

- **Match Score Accuracy**: All scores are 20-30% lower than they should be
- **Candidate Ranking**: Top candidates may not appear at top of lists
- **Hiring Decisions**: Customers may be rejecting qualified candidates

---

## Test Failures Observed

```
FAILED tests/unit/test_jobs.py::TestMatchScoring::test_perfect_match_score
    AssertionError: Expected score >= 0.99, got 0.79
    > Candidate with all required skills at max proficiency should score ~1.0

FAILED tests/unit/test_jobs.py::TestMatchScoring::test_score_normalization
    AssertionError: Scores not properly normalized to 0-1 range
    > Maximum achievable score is 0.85, not 1.0
```

---

## Reproduction Steps

1. Create a job with 3 required skills
2. Create a candidate with all 3 skills at proficiency 5/5
3. Calculate match score via `calculate_skill_match_score()`
4. Observe score is ~0.75 instead of expected ~1.0

---

## Files to Investigate

- `apps/jobs/matching.py` - Score calculation functions

---

## Business Impact

- Customer trust in AI-powered matching is eroding
- 3 enterprise customers have mentioned evaluating competitors
- Feature is core differentiator in sales process

---

**Status**: INVESTIGATING
**Assigned**: @dev.sarah
**Severity**: High - Core feature affected
**ETA**: 2024-01-22 EOD
