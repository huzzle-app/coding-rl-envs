# Customer Escalation: WebSocket Connection Failures

## Zendesk Ticket #91847

**Priority**: Urgent
**Customer**: GlobalTech Industries (Enterprise Tier)
**Account Value**: $380,000 ARR
**CSM**: Marcus Chen
**Created**: 2024-01-23 09:15 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> Our team has been experiencing severe connectivity issues with CloudMatrix over the past week. Users are constantly getting disconnected, seeing stale data, and unable to collaborate in real-time. This is a critical business impact as we rely on CloudMatrix for our global team coordination.

### Reported Symptoms

1. **Frequent Disconnections**: Users report getting disconnected every 15-30 minutes with no warning

2. **"Ghost Users"**: Presence indicator shows colleagues as "online" even after they've closed their browser hours ago

3. **Messages Out of Order**: Chat messages and document updates arrive in wrong order

4. **Connection Won't Reconnect**: After disconnection, app shows "Reconnecting..." forever, requires manual page refresh

5. **Memory Warnings**: Several users on older laptops report browser memory warnings after extended sessions

---

## Technical Details from Customer

### Browser Console Logs (Chrome)

```
[CloudMatrix WS] 09:15:32 Connected to wss://realtime.cloudmatrix.io
[CloudMatrix WS] 09:15:33 Joined room: doc-abc123
[CloudMatrix WS] 09:30:45 Heartbeat timeout - no pong received
[CloudMatrix WS] 09:30:45 Connection closed unexpectedly
[CloudMatrix WS] 09:30:45 Attempting reconnect (attempt 1)...
[CloudMatrix WS] 09:30:46 Reconnect delay: 1000ms
[CloudMatrix WS] 09:30:47 Attempting reconnect (attempt 2)...
[CloudMatrix WS] 09:30:48 Reconnect delay: 1000ms  <-- Same delay?
[CloudMatrix WS] 09:30:49 Attempting reconnect (attempt 3)...
[CloudMatrix WS] 09:30:50 Reconnect delay: 1000ms  <-- Still 1 second
...
[CloudMatrix WS] 09:35:12 Max reconnect attempts (100) reached
[CloudMatrix WS] 09:35:12 Please refresh the page
```

### Network Tab Observations

```
WebSocket frame log:
  09:15:33 -> {"type":"join_room","roomId":"doc-abc123","seq":1}
  09:15:33 <- {"type":"room_joined","roomId":"doc-abc123"}
  09:15:34 -> {"type":"broadcast","roomId":"doc-abc123","data":{"cursor":{}},"seq":2}
  09:15:35 -> {"type":"broadcast","roomId":"doc-abc123","data":{"edit":{}},"seq":3}
  09:15:40 -> {"type":"broadcast","roomId":"doc-abc123","data":{"cursor":{}},"seq":5}  <-- seq 4 missing?
  09:15:41 <- {"type":"broadcast","data":{"edit":{}}}  <-- Received out of order
```

### Memory Profile (from Chrome DevTools)

```
Session duration: 2 hours
Initial heap: 45 MB
Final heap: 312 MB
Growth rate: ~2.2 MB/minute

Top retained objects:
- WebSocket frame buffers: 89 MB
- Event listener closures: 67 MB
- Room subscription callbacks: 45 MB
```

---

## Internal Slack Thread

**#eng-support** - January 23, 2024

**@marcus.chen** (09:45):
> Urgent escalation from GlobalTech. They're having massive WebSocket issues - disconnects, ghost users, memory leaks. This is a $380k account and they're threatening to evaluate alternatives.

**@dev.sarah** (09:52):
> Looking at their logs. The reconnection delay is constant at 1000ms. Shouldn't we have exponential backoff?

**@dev.alex** (09:58):
> Checked the code - `getReconnectDelay()` always returns 1000. That's definitely wrong. With constant retry, we're probably overwhelming both the client and server during any network hiccup.

**@dev.sarah** (10:05):
> Found the ghost user issue too. When a WebSocket closes, we're deleting the connection from our map, but we're NOT:
> 1. Cleaning up room subscriptions
> 2. Removing presence state from Redis
> 3. Notifying other users that this user left

**@sre.kim** (10:12):
> Server-side metrics show goroutine accumulation:
> ```
> ws_active_connections: 2,341
> ws_room_subscriptions: 8,923 (should be ~2x connections, not 4x)
> ws_orphaned_subscriptions: 3,241
> ```

**@dev.alex** (10:18):
> I see the issue with message ordering too. We're tracking sequence numbers but not actually enforcing them:
> ```javascript
> const seq = message.seq;
> const expectedSeq = (this.messageSequence.get(connectionId) || 0) + 1;
> // BUG: We just update to whatever seq came in, don't validate or buffer
> this.messageSequence.set(connectionId, seq);
> ```
> If messages arrive out of order (network jitter), we process them that way.

**@dev.sarah** (10:25):
> And the heartbeat issue - we check if the client sent a ping recently, but we never actually SEND pings from the server. The client-side heartbeat interval is 15 seconds, but our server check interval is 30 seconds. By the time we check, the connection is already considered dead by the client.

**@sre.kim** (10:30):
> Also noticed there's no max connection limit per server. During their peak usage, one server had 12,000 connections. No wonder it was struggling.

**@dev.alex** (10:35):
> Memory leak explained too - when connections close abnormally (error handler), we don't clean up at all:
> ```javascript
> ws.on('error', () => {
>   // Error handler doesn't clean up - connection just leaks
> });
> ```

**@marcus.chen** (10:40):
> Can we get a timeline for fixes? Customer call is at 14:00 UTC.

**@dev.sarah** (10:45):
> Let me list what we need to fix:
> 1. Exponential backoff for reconnection
> 2. Connection cleanup on close (rooms, presence)
> 3. Message ordering/buffering
> 4. Server-side ping implementation
> 5. Max connection limits
> 6. Error handler cleanup

---

## Reproduction Steps (from QA)

### Ghost Users
1. User A joins document
2. User A closes browser tab (doesn't explicitly disconnect)
3. User B checks presence - User A still shows as online
4. Wait 5+ minutes - User A still shows as online (should timeout after 30s)

### Reconnection Flood
1. Simulate network disconnect
2. Observe reconnection attempts
3. All retries at 1-second intervals (no backoff)
4. Server receives 100 connection attempts in ~100 seconds

### Memory Leak
1. Join a busy document with 10+ collaborators
2. Monitor browser memory
3. Memory grows continuously even with no activity
4. After 2 hours, browser becomes sluggish

---

## Server Metrics During Incident

```
Time: 09:00 - 11:00 UTC

ws_connections_total: 15,234 (peak)
ws_connection_errors: 4,521
ws_abnormal_closes: 2,891
ws_room_leave_failures: 2,891 (matches abnormal closes - cleanup not working)

memory_heap_mb:
  09:00  512 MB
  10:00  1,247 MB
  11:00  2,103 MB (triggering OOM warnings)

event_loop_lag_ms:
  09:00  12ms
  10:00  89ms
  11:00  234ms
```

---

## Impact Assessment

- **Users Affected**: ~1,200 at GlobalTech
- **Sessions Disrupted**: Estimated 4,500 disconnections per hour
- **Data Sync Issues**: Unknown number of lost updates
- **Revenue Risk**: $380k account considering alternatives

---

## Files to Investigate

Based on the symptoms:
- `shared/realtime/index.js` - WebSocket manager, heartbeat, room management
- `services/presence/src/services/presence.js` - Presence tracking and cleanup

---

**Status**: INVESTIGATING
**Assigned**: @realtime-team
**Customer Call**: 2024-01-23 14:00 UTC
