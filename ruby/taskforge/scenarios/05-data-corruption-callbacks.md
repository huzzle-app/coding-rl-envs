# Bug Report: Data Corruption and Silent Failures

## JIRA Ticket TASK-4521

**Priority**: High
**Type**: Bug
**Reporter**: QA Team
**Created**: 2024-01-24
**Sprint**: Q1 Hardening

---

## Summary

QA has identified multiple data integrity issues during regression testing. Tasks are being duplicated with corrupted data, parent-child relationships are breaking, and some operations silently fail without any error indication to users.

---

## Issue 1: Task Duplication Creates Corrupted Copies

### Steps to Reproduce

1. Create a task with tags: `["frontend", "urgent"]` and metadata: `{"sprint": "Q1"}`
2. Duplicate the task using the duplicate feature
3. Modify the original task's tags to `["frontend", "urgent", "reviewed"]`
4. Check the duplicated task's tags

### Expected Result
- Duplicated task retains original tags: `["frontend", "urgent"]`

### Actual Result
- Duplicated task also shows: `["frontend", "urgent", "reviewed"]`
- Tags and metadata are shared between original and duplicate
- Modifying one affects the other

### Additional Observations
- The issue persists even after page refresh
- Database inspection shows both tasks reference the same array/hash in memory
- This suggests shallow copying rather than deep copying

---

## Issue 2: Recursive Stack Overflow on Task Completion

### Steps to Reproduce

1. Create parent task "Epic A"
2. Create subtask "Story 1" under Epic A
3. Create subtask "Story 2" under Epic A
4. Complete Story 1, then Story 2
5. System attempts to auto-complete Epic A

### Expected Result
- Epic A is marked as completed when all subtasks are done

### Actual Result
- Application crashes with `SystemStackError: stack level too deep`
- Error occurs in task completion callback
- Recovery requires manual database intervention

### Stack Trace (truncated)
```
SystemStackError: stack level too deep
  from app/models/task.rb:131:in `complete_parent_if_all_subtasks_done'
  from app/models/task.rb:48:in `block in <class:Task>'
  from app/models/task.rb:131:in `complete_parent_if_all_subtasks_done'
  from app/models/task.rb:48:in `block in <class:Task>'
  ... 8000 more lines ...
```

---

## Issue 3: Silent Failure on Task Creation

### Steps to Reproduce

1. Create a task with invalid data (e.g., priority = "invalid")
2. Check if the task was created
3. Check server logs

### Expected Result
- API returns error message explaining validation failure
- Task is not created

### Actual Result
- API returns HTTP 200 with null/empty response
- No error message displayed to user
- Task is not created but user has no indication of failure
- Server logs show error but response doesn't reflect it

### API Response
```json
null
```

---

## Issue 4: Premature Notification Before Transaction Commits

### Steps to Reproduce

1. Create a task with an assignee
2. Simultaneously trigger a database constraint violation (in test harness)
3. Check if notification was sent

### Expected Result
- Notification should only be sent after task is successfully saved

### Actual Result
- Notification is sent inside the transaction
- If transaction rolls back, user receives notification for non-existent task
- Clicking notification link leads to 404 error

### User Report
> "I got an email saying I was assigned to a task, but when I click the link it says the task doesn't exist. This has happened three times this week."

---

## Issue 5: Transaction Atomicity Violation in Task Move

### Steps to Reproduce

1. Create a task with 3 subtasks and 5 comments in Project A
2. Move the task to Project B
3. Simulate a network timeout during the move operation

### Expected Result
- Either all data moves to Project B, or nothing moves (atomic)

### Actual Result
- Task moves to Project B
- Some subtasks remain in Project A
- Comments are split between projects
- Data is in inconsistent state

### Database State After Partial Failure
```sql
-- Task moved to new project
SELECT project_id FROM tasks WHERE id = 123;
-- Returns: 2 (Project B)

-- Some subtasks still in old project
SELECT project_id FROM tasks WHERE parent_id = 123;
-- Returns: 1, 1, 2 (mixed!)

-- Comments split
SELECT project_id FROM comments WHERE task_id = 123;
-- Returns: 1, 1, 2, 2, 1 (mixed!)
```

---

## Issue 6: Frozen String Modification Error

### Steps to Reproduce

1. Perform a search with query "test"
2. View comment results

### Expected Result
- Search results display correctly

### Actual Result
- Intermittent `FrozenError: can't modify frozen String`
- Occurs when processing comment results
- Error is not consistent - depends on Ruby optimization

### Error Details
```
FrozenError: can't modify frozen String: "test"
  from app/services/search_service.rb:93:in `truncate'
  from app/services/search_service.rb:93:in `comment_result'
```

---

## Impact Assessment

| Issue | Severity | Frequency | User Impact |
|-------|----------|-----------|-------------|
| Tag corruption | High | Every duplicate | Data integrity |
| Stack overflow | Critical | Rare edge case | Crash |
| Silent failures | High | ~5% of creates | User confusion |
| Premature notifications | Medium | Race condition | Trust erosion |
| Transaction split | High | On timeout | Data corruption |
| Frozen string | Medium | Intermittent | Error page |

---

## Files to Investigate

- `app/services/task_service.rb` - Duplication and move logic
- `app/models/task.rb` - Callbacks and completion logic
- `app/services/search_service.rb` - String handling

---

**Assigned**: Backend Team
**Sprint Goal**: Fix all issues before Q1 release
**Due Date**: 2024-01-31
