# Customer Escalation: Task Ordering Issues in Kanban Board

## Zendesk Ticket #89234

**Priority**: Urgent
**Customer**: GlobalTech Industries (Enterprise Tier)
**Account Value**: $180,000 ARR
**CSM**: Michael Torres
**Created**: 2024-01-20 11:42 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> Our project managers are reporting serious issues with the Kanban board. When multiple team members add tasks at the same time, the task ordering gets completely messed up. We've had duplicate position numbers, tasks appearing in wrong order, and even tasks disappearing from view. This is happening across multiple projects and it's severely impacting our sprint planning.

### Reported Symptoms

1. **Duplicate Task Positions**: Multiple tasks end up with the same position number, causing display issues in the Kanban board.

2. **Race During Bulk Import**: When using CSV import to create multiple tasks, the resulting positions are not sequential.

3. **Tasks Vanishing from Board**: Occasionally tasks don't appear on the board until page refresh - they seem to get "stuck" with invalid position values.

4. **Concurrent Edit Conflicts**: When two users create tasks in the same project simultaneously, one task sometimes gets position 0 or a duplicate position.

---

## Technical Details from Customer Logs

### Browser Console Errors

```
2024-01-20T11:23:45.123Z [WARN] Task position conflict detected: tasks 892 and 893 both have position 47
2024-01-20T11:23:45.234Z [ERROR] Failed to render Kanban column: duplicate key in task list
2024-01-20T11:24:12.567Z [WARN] Task 894 has null position, falling back to created_at ordering
```

### API Response Anomalies

```http
POST /api/v1/projects/456/tasks HTTP/1.1
# Request 1 from User A at 11:30:00.000
{"title": "Design review", ...}
Response: {"id": 901, "position": 48, ...}

# Request 2 from User B at 11:30:00.050 (50ms later)
{"title": "Code review", ...}
Response: {"id": 902, "position": 48, ...}  # Same position!
```

---

## Internal Slack Thread

**#eng-support** - January 20, 2024

**@michael.torres** (11:45):
> Hey team, GlobalTech is having major issues with task positioning in their Kanban boards. Multiple tasks getting the same position, causing rendering problems. This is their 2nd escalation in a week.

**@dev.priya** (11:52):
> Looking at the Task model now. I see we calculate position in a `before_save` callback by finding the max position and adding 1. That's definitely not thread-safe.

**@dev.alex** (11:55):
> Right - if two requests hit at the same time, they both read the same max position, then both try to save with the same new position. Classic TOCTOU race condition.

**@dev.priya** (11:58):
> Confirmed in staging. I created two tasks simultaneously using curl and they both got position 24. The second one should have been 25.

**@sre.kim** (12:02):
> This explains why the problem got worse last week - GlobalTech onboarded 50 new users and now has much higher concurrency. We probably always had this bug but it rarely manifested before.

**@dev.alex** (12:05):
> The position calculation needs to be atomic. Either:
> 1. Use a database-level sequence/auto-increment
> 2. Use `INSERT ... RETURNING` with a subquery
> 3. Use pessimistic locking (slower)

**@dev.priya** (12:08):
> Also noticing the stats calculation has a similar pattern with `@stats ||= ...`. Not thread-safe either if we're using Puma with multiple threads.

---

## Reproduction Steps (from QA)

1. Set up a project with existing tasks (positions 1-10)
2. Open two browser windows logged in as different users
3. Click "Add Task" in both windows at exactly the same time
4. Observe both tasks receive the same position number
5. Refresh the Kanban board - tasks appear stacked/overlapping

**Success Rate**: ~60% reproduction with simultaneous requests

### Alternate Reproduction (CSV Import)

1. Create a CSV with 20 new tasks
2. Import while another user is also creating tasks manually
3. Observe position gaps and duplicates in the resulting task list

---

## Additional Context

GlobalTech runs sprint planning sessions where 5-10 PMs simultaneously create and organize tasks. The problem becomes severe during these high-concurrency periods.

They also noticed that the project dashboard sometimes shows stale statistics that don't update immediately after tasks are modified.

---

## Impact Assessment

- **Users Affected**: ~200 active project managers at GlobalTech
- **Data Integrity Risk**: Medium - task ordering metadata is corrupted
- **User Experience**: Severe - Kanban boards unusable during high activity
- **Revenue Risk**: Customer evaluating competitor solutions

---

## Files to Investigate

Based on the symptoms:
- `app/models/task.rb` - Position calculation in callback
- `app/models/project.rb` - Stats memoization pattern
- Any bulk task creation endpoints

---

**Assigned**: @dev.priya, @dev.alex
**Deadline**: EOD January 21, 2024
**Follow-up Call**: Scheduled with customer for January 22, 2024 10:00 PST
