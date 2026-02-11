# Support Ticket: Patient Data Inconsistencies and Performance Issues

## ServiceNow Ticket #INC0045892

**Priority**: High
**Reported By**: Clinical Operations Team
**Created**: 2024-02-18 11:15 UTC
**Category**: Data Integrity
**Status**: Under Investigation

---

## Issue Description

Multiple clinics have reported that patient data displayed in HealthLink does not match what was just entered or updated. Additionally, the patient list page seems slower than expected and is hitting the database more often than it should.

---

## Reported Symptoms

### Symptom 1: Stale Patient Data

**Reporter**: Nurse Station at Clinic #47

> We updated a patient's allergy information at 10:30 AM. When the doctor pulled up the same patient record at 10:32 AM on a different workstation, the old allergy list was displayed. The doctor almost prescribed a medication the patient is allergic to. This is a patient safety issue.

**Additional details**:
- Updates made by one user aren't immediately visible to other users
- Refreshing the page sometimes helps, sometimes doesn't
- The problem occurs more frequently during busy periods
- Direct database queries show the correct (updated) data

### Symptom 2: Slow Patient List Loading

**Reporter**: Front Desk Supervisor at Clinic #23

> The "Active Patients" list takes 2-3 seconds to load now. It used to be instant. Our database team says they're seeing duplicate queries running for the same data.

**Database team observation**:
```sql
-- Query log shows these running back-to-back for same request:
-- Query 1:
SELECT COUNT(*) FROM "Patients" WHERE "IsActive" = true;
-- Query 2 (100ms later, same connection):
SELECT * FROM "Patients" WHERE "IsActive" = true;
```

### Symptom 3: Patient Creation Failures

**Reporter**: Registration Desk at Clinic #15

> When we try to register new patients, sometimes we get a "NullReferenceException" error. It happens when the patient name field is filled in but something about how it's processed fails. The error message mentions "Object reference not set to an instance of an object."

**Screenshot of error toast**:
```
Error creating patient record
Technical details: System.NullReferenceException: Object reference not set to an instance of an object.
   at HealthLink.Api.Services.PatientService.CreateAsync(Patient patient)
```

### Symptom 4: Appointment Status Not Updating Correctly

**Reporter**: Scheduling Team at Clinic #31

> We changed an appointment from "Pending" to "Confirmed" but when we view the appointment list, it still shows as "Pending". It's like the status comparison isn't working right.

---

## Internal Investigation Notes

### Database Query Analysis

DBA team analysis from slow query log:

```
2024-02-18T10:45:23.123Z
Query: SELECT COUNT(*) FROM "Patients" WHERE "IsActive" = true
Duration: 234ms
Rows Examined: 45,892

2024-02-18T10:45:23.357Z
Query: SELECT * FROM "Patients" WHERE "IsActive" = true
Duration: 1,245ms
Rows Examined: 45,892

Note: Both queries executed for single API call to GetAllAsync()
Expected: Single query with ToList() materialization
```

### Change Tracker Investigation

Developer notes:
```
Tested locally:
1. Open two browser tabs with same patient
2. Update patient in Tab A, save successfully
3. Refresh Tab B - still shows OLD data
4. Check database directly - NEW data is present
5. Restart application - Tab B now shows NEW data

Conclusion: EF Core change tracker is returning cached entities
instead of fresh data from database
```

### NullReferenceException Stack Trace

Full exception from application logs:
```
System.NullReferenceException: Object reference not set to an instance of an object.
   at System.String.ToUpper()
   at HealthLink.Api.Services.PatientService.CreateAsync(Patient patient) in /app/src/Services/PatientService.cs:line 56
   at HealthLink.Api.Controllers.PatientController.CreatePatient(Patient patient)

# Line 56 context:
# var normalizedName = patient.Name.ToUpper();
# Note: patient.Name appears to be null despite being "set"
```

---

## Slack Thread Excerpt

**#eng-bugs** - February 18, 2024

**@dev.marcus** (11:30):
> Looking at the stale data issue. The PatientService uses `FindAsync` which goes through the change tracker. If an entity is already tracked, EF returns the cached version instead of querying the DB.

**@dev.sarah** (11:35):
> And the double query issue - I see `GetAllAsync` returns an `IEnumerable` that gets enumerated twice. First for `Count()`, then for `ToList()`. Each enumeration hits the DB.

**@dev.marcus** (11:42):
> The NRE is interesting. The Patient model has `Name` declared as `string Name = null!;` - that `null!` suppression tells the compiler "trust me, this won't be null" but it clearly can be null at runtime.

**@dev.sarah** (11:48):
> And the appointment status issue might be related to boxed enum comparison. If we're comparing `object.Equals()` on boxed enum values, that could behave unexpectedly.

---

## Affected Areas

| Issue | Frequency | Severity | Patient Safety |
|-------|-----------|----------|----------------|
| Stale data | ~20 reports/day | High | Yes - medication errors possible |
| Double queries | Every list load | Medium | No - performance only |
| NullReferenceException | ~5 reports/day | Medium | No - registration fails safely |
| Status comparison | ~10 reports/day | Medium | No - scheduling confusion |

---

## Files to Investigate

Based on symptoms and stack traces:
- `src/HealthLink.Api/Services/PatientService.cs` - Change tracker, deferred execution, null handling
- `src/HealthLink.Api/Services/AppointmentService.cs` - Enum comparison logic
- `src/HealthLink.Api/Models/Patient.cs` - Null suppression on Name property
- `src/HealthLink.Api/Repositories/PatientRepository.cs` - Query patterns

---

**Status**: INVESTIGATING
**Assigned**: @dev.marcus, @dev.sarah
**Review Meeting**: February 19, 2024 09:00 UTC
**Customer Communication**: Sent interim update acknowledging issue
