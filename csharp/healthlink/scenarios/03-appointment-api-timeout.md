# Customer Escalation: Appointment API Requests Hanging

## Zendesk Ticket #89234

**Priority**: Urgent
**Customer**: Regional Medical Center (Enterprise Tier)
**Account Value**: $180,000 ARR
**CSM**: David Park
**Created**: 2024-02-15 09:42 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> Our front desk staff are experiencing severe issues with the HealthLink appointment system. When they try to look up individual appointments, the request hangs indefinitely and eventually times out. This is causing 10-15 minute delays for patient check-ins.

### Reported Symptoms

1. **Individual Appointment Lookup Freezes**: `GET /api/appointment/{id}` requests never return. Staff have to close the browser tab after 30+ seconds of waiting.

2. **Bulk Appointment List Works**: Strangely, `GET /api/appointment` (list all) works fine and returns quickly.

3. **Intermittent Pattern**: The issue happens consistently for single appointment lookups but the system works fine for other operations.

4. **No Error Messages**: The browser just shows "Loading..." indefinitely. No error toast or message.

---

## Technical Investigation

### Browser Network Tab (from customer screenshot)

```
Name                    Status    Time      Size
GET /api/appointment/123  (pending)  30.2s    -
GET /api/appointment/456  (pending)  28.7s    -
GET /api/appointment/789  (failed)   60.0s    net::ERR_TIMED_OUT
```

### Server-Side Metrics (from APM Dashboard)

```
Endpoint: GET /api/appointment/{id}
Avg Response Time: 60,000ms (timeout)
99th Percentile: 60,000ms
Active Threads: 147 (unusually high)
Thread Pool Queue: 89 items waiting

# Compare with working endpoint:
Endpoint: GET /api/appointment
Avg Response Time: 45ms
99th Percentile: 120ms
```

### Application Logs

```
2024-02-15T09:45:12.123Z [INFO] Request started: GET /api/appointment/123
2024-02-15T09:45:12.125Z [DEBUG] AppointmentController.GetAppointment called with id=123
# ... no further logs for this request ...
# Request eventually times out at 60s with no completion log

# Working endpoint for comparison:
2024-02-15T09:45:14.001Z [INFO] Request started: GET /api/appointment
2024-02-15T09:45:14.003Z [DEBUG] AppointmentController.GetAllAppointments called
2024-02-15T09:45:14.048Z [INFO] Request completed: 200 OK in 45ms
```

### Thread Dump Analysis

During the incident, a thread dump shows many threads in this state:

```
Thread 47 (System.Threading.ThreadPoolWorkItem):
  System.Threading.Monitor.Wait(Object, Int32)
  System.Threading.ManualResetEventSlim.Wait(Int32, CancellationToken)
  System.Threading.Tasks.Task.SpinThenBlockingWait(Int32, CancellationToken)
  System.Threading.Tasks.Task.InternalWait(Int32, CancellationToken)
  System.Threading.Tasks.Task`1.GetResultCore(Boolean)
  HealthLink.Api.Controllers.AppointmentController.GetAppointment(Int32)
```

---

## Internal Slack Thread

**#eng-support** - February 15, 2024

**@david.park** (09:55):
> Regional Medical is having a meltdown. Their appointment lookups are hanging indefinitely. Can someone look at this urgently? Patient check-in queues are out the door.

**@dev.sarah** (10:05):
> Looking at the APM. Interesting - the `GetAppointment` endpoint is blocking but `GetAllAppointments` works fine. Let me check the controller code.

**@dev.sarah** (10:12):
> Found something suspicious. The `GetAppointment` method is synchronous but calls an async service method. There's a `.Result` call that might be causing a deadlock.

**@dev.marcus** (10:18):
> Classic ASP.NET deadlock pattern. If there's a SynchronizationContext and you block on `.Result` while the continuation needs to marshal back to the same context... deadlock city.

**@dev.sarah** (10:22):
> But wait, ASP.NET Core doesn't have a SynchronizationContext by default. Let me check if something's configuring one...

**@dev.marcus** (10:25):
> Could also be thread pool exhaustion. If enough requests pile up blocking on `.Result`, you can starve the pool and nothing can make progress.

**@sre.kim** (10:30):
> Thread pool stats confirm high utilization. 147 active threads, 89 queued items. Normal baseline is ~20 active threads.

---

## Additional Observations

### Reproduction Steps (from QA)

1. Start the application fresh
2. Make several concurrent requests to `GET /api/appointment/{id}`
3. Observe requests hanging
4. Note that `GET /api/appointment` (list all) continues working

### Related Errors in Event Log

```
Event ID: 1026
Application: HealthLink.Api
Warning: ThreadPool threads are being used up. Consider increasing MinThreads.
Queue length: 89
```

---

## Impact Assessment

- **Users Affected**: ~200 front desk staff at Regional Medical
- **Patient Impact**: 10-15 minute delays for check-in
- **Volume**: ~500 appointment lookups per hour during peak

---

## Files to Investigate

Based on the thread dump and symptoms:
- `src/HealthLink.Api/Controllers/AppointmentController.cs` - The `GetAppointment` method
- `src/HealthLink.Api/Services/AppointmentService.cs` - Async service methods

---

**Assigned**: @dev.sarah, @dev.marcus
**Deadline**: EOD February 15, 2024
**Follow-up**: Customer call scheduled for 14:00 UTC
