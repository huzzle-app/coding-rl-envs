# Incident Report: Memory Leak in Presence Service

## Grafana Alert

**Severity**: Critical (P1)
**Triggered**: 2024-02-15 02:17 UTC
**Acknowledged**: 2024-02-15 02:21 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: collabcanvas-api-prod-1 memory usage at 92%
Host: collabcanvas-api-prod-1.us-east-1.internal
Metric: container_memory_usage_bytes
Threshold: >90% for 5 minutes
Current Value: 92.4%
```

## Timeline

**02:17 UTC** - Initial alert fired for pod memory exceeding 90%

**02:35 UTC** - Second pod (collabcanvas-api-prod-2) also breaching threshold

**02:48 UTC** - First pod OOM-killed by Kubernetes
```
reason: OOMKilled
exitCode: 137
restartCount: 1
```

**02:52 UTC** - Pod restarted, memory immediately starts climbing

**03:10 UTC** - Memory back at 75% after just 18 minutes of uptime

## Grafana Dashboard Observations

### Memory Profile

```
Time Window: 00:00 - 03:00 UTC

00:00  512MB (baseline after deploy)
00:30  623MB
01:00  748MB
01:30  891MB
02:00  1,047MB
02:30  1,198MB
02:48  1,284MB (OOM kill at 1.3GB limit)
```

**Growth Rate**: ~40MB every 15 minutes regardless of load

### Event Listener Count (via Node.js diagnostics)

```
Metric: nodejs_eventloop_listeners_count{event="heartbeat"}
Time: 00:00 - 03:00 UTC

00:00     47 listeners
00:30    234 listeners
01:00    512 listeners
01:30    847 listeners
02:00  1,203 listeners
02:30  1,647 listeners
02:48  1,892 listeners
```

**Observation**: Heartbeat listeners growing unbounded even as users disconnect.

### WebSocket Connection Metrics

```
websocket.connection.total: 8,234
websocket.connection.active: 312
websocket.disconnect.total: 7,922

# Mismatch: 7,922 disconnects but only ~300 listener cleanups
socket.listener.removed: 298
```

## Heap Dump Analysis

Memory allocation hotspots from heap snapshot:

```
Retained Size by Constructor:

Object                   Count      Size (MB)
-----------------------------------------------
EventEmitter listeners   1,892      142.3
(closure)                4,231      98.7
PresenceService          1          45.2
Socket instances         312        23.1
Map entries             24,891      18.4
```

Closure references keeping objects alive:
```javascript
// Found in heap dump - closures not being released
<closure> @ presence.handler.js:32
  - References: socket, presenceService, currentBoard
  - Retained by: EventEmitter._events.heartbeat[847]

<closure> @ presence.service.js:57
  - References: key, this (PresenceService)
  - Retained by: Socket._events.heartbeat
```

## Application Logs

```
2024-02-15T01:00:12.123Z [WS] User connected socket=sock_a1b2c3
2024-02-15T01:00:12.234Z [PRESENCE] Tracking user on board board_xyz
2024-02-15T01:00:12.235Z [PRESENCE] Added heartbeat listener socket=sock_a1b2c3

2024-02-15T01:15:45.567Z [WS] User disconnected socket=sock_a1b2c3
2024-02-15T01:15:45.568Z [PRESENCE] Removing user from board board_xyz
2024-02-15T01:15:45.569Z [PRESENCE] User removed from tracking
# Note: No log for "Removed heartbeat listener"

2024-02-15T01:16:00.000Z [PRESENCE] Heartbeat received socket=sock_a1b2c3
# Note: Heartbeat still being received for disconnected socket!

2024-02-15T01:17:00.000Z [PRESENCE] Heartbeat received socket=sock_a1b2c3
2024-02-15T01:18:00.000Z [PRESENCE] Heartbeat received socket=sock_a1b2c3
# Pattern continues...
```

## Reproduction Steps

### Test Scenario

```javascript
// Automated test that reproduces the leak
async function testPresenceMemoryLeak() {
  const initialMemory = process.memoryUsage().heapUsed;

  // Simulate 100 users joining and leaving
  for (let i = 0; i < 100; i++) {
    const socket = createMockSocket();
    await presenceService.trackUser(socket, 'board-1', { id: `user-${i}` });
    // Simulate heartbeats
    socket.emit('heartbeat');
    socket.emit('heartbeat');
    // User leaves
    await presenceService.removeUser(socket, 'board-1', `user-${i}`);
    socket.disconnect();
  }

  // Force GC
  global.gc();

  const finalMemory = process.memoryUsage().heapUsed;
  const leaked = finalMemory - initialMemory;

  console.log(`Memory leaked: ${(leaked / 1024 / 1024).toFixed(2)} MB`);
  // Output: Memory leaked: 12.34 MB (should be ~0)
}
```

### Manual Reproduction

1. Start CollabCanvas server with memory monitoring
2. Open 50 browser tabs, each joining a board
3. Close all 50 tabs (disconnect WebSocket)
4. Observe memory does not decrease
5. Open Chrome DevTools on server: Event listeners still registered

## Internal Slack Thread

**#eng-backend** - February 15, 2024

**@sre.kim** (02:25):
> Another OOM kill on prod. This is the third time this week. Memory just keeps growing.

**@dev.alex** (02:32):
> I see the pattern. EventEmitter listener count is growing unbounded. We're adding `heartbeat` listeners when users join boards but not removing them on disconnect.

**@dev.alex** (02:38):
> Found it. In `presence.service.js`, the `trackUser` method adds a listener:
```javascript
socket.on('heartbeat', heartbeatHandler);
```
> But `removeUser` never calls `socket.off('heartbeat', ...)`.

**@dev.sarah** (02:45):
> Same issue in the presence handler. We add `cursor-move` and `selection-change` listeners when user joins a board, but those never get cleaned up either.

**@dev.alex** (02:48):
> There's also a closure problem. The handlers capture `currentBoard` by reference:
```javascript
socket.on('cursor-move', (position) => {
  presenceService.updateCursor(currentBoard, ...);
});
```
> Even if the user switches boards, this handler keeps using the old board.

**@sre.kim** (02:52):
> How bad is it? How many listeners are we leaking?

**@dev.alex** (02:55):
> Every join-board adds 3 listeners. None are removed. With our traffic (~500 board joins per hour), we're leaking about 1,500 listeners per hour.

**@dev.sarah** (03:01):
> This explains the cursor position bugs too. If a user switches from Board A to Board B, their cursor movements still get sent to Board A because the old listener is still active.

## Customer Impact

- Users report "ghost cursors" - seeing other users' cursors on boards they left
- Cursor positions appearing on wrong boards
- Sporadic 502 errors during pod restarts

## Attempted Mitigations

1. **Increased pod memory limit** from 1.3GB to 2GB - just delayed the OOM
2. **Scheduled pod restarts** every 4 hours - band-aid that causes brief outages
3. **Reduced heartbeat frequency** - didn't help since listeners still accumulate

## Files to Investigate

Based on analysis:
- `src/services/collaboration/presence.service.js` - Event listener not removed in `removeUser`
- `src/websocket/handlers/presence.handler.js` - Stale closure capturing `currentBoard`

---

**Status**: INVESTIGATING
**Assigned**: @sync-team, @platform-team
**Mitigation**: Pod restart every 4 hours until fix deployed
