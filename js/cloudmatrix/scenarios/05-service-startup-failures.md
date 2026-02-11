# Incident Report: Service Startup Cascade Failure

## PagerDuty Alert

**Severity**: Critical (P0)
**Triggered**: 2024-01-25 06:12 UTC
**Acknowledged**: 2024-01-25 06:15 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: Multiple services failing health checks
Affected: gateway, presence, search, auth, documents
Cluster: cloudmatrix-prod-us-west-2
Error: Service initialization timeout after 30s
```

## Timeline

**06:00 UTC** - Scheduled deployment begins (v3.2.2)

**06:08 UTC** - First pods start coming up, immediately crash

**06:12 UTC** - Alert fires: 5 services failing health checks

**06:15 UTC** - On-call engineer acknowledges, begins investigation

**06:18 UTC** - Rollback initiated to v3.2.1

**06:22 UTC** - Rollback complete, but services STILL failing

**06:25 UTC** - Discovery: v3.2.1 has same issue (was dormant, triggered by pod restart)

**06:30 UTC** - All hands incident declared

**06:45 UTC** - Root cause identified: Circular import chain in shared modules

**07:15 UTC** - Hotfix deployed, services recovering

---

## Initial Investigation

### Pod Logs (gateway-service)

```
2024-01-25T06:08:12.123Z [gateway] Starting CloudMatrix Gateway v3.2.2
2024-01-25T06:08:12.124Z [gateway] Loading shared modules...
2024-01-25T06:08:12.125Z [gateway] RangeError: Maximum call stack size exceeded
    at Object.<anonymous> (/app/shared/index.js:1:1)
    at require (internal/modules/cjs/loader.js:1234:12)
    at Object.<anonymous> (/app/shared/clients/index.js:8:24)
    at require (internal/modules/cjs/loader.js:1234:12)
    at Object.<anonymous> (/app/shared/events/index.js:5:20)
    at require (internal/modules/cjs/loader.js:1234:12)
    at Object.<anonymous> (/app/shared/utils/index.js:3:18)
    at require (internal/modules/cjs/loader.js:1234:12)
    at Object.<anonymous> (/app/shared/realtime/index.js:11:25)
    at require (internal/modules/cjs/loader.js:1234:12)
    ...
```

### Pod Logs (presence-service)

```
2024-01-25T06:08:14.456Z [presence] Starting CloudMatrix Presence Service v3.2.2
2024-01-25T06:08:14.789Z [presence] Initializing WebSocket server...
2024-01-25T06:08:14.790Z [presence] WebSocket server binding to port 3004...
2024-01-25T06:08:14.791Z [presence] Health check registered
2024-01-25T06:08:14.792Z [presence] Starting health check...
2024-01-25T06:08:14.793Z [presence] ERROR: WebSocket server not ready
2024-01-25T06:08:14.794Z [presence] Health check FAILED
```

### Pod Logs (search-service)

```
2024-01-25T06:08:16.123Z [search] Starting CloudMatrix Search Service v3.2.2
2024-01-25T06:08:16.456Z [search] Connecting to Elasticsearch...
2024-01-25T06:08:16.789Z [search] Connected to Elasticsearch cluster
2024-01-25T06:08:17.012Z [search] Checking index status...
2024-01-25T06:08:17.234Z [search] ERROR: Index 'documents' does not exist
2024-01-25T06:08:17.235Z [search] ERROR: Search queries will fail - index not initialized
```

### Pod Logs (events-handler)

```
2024-01-25T06:08:18.456Z [events] Starting CloudMatrix Event Handler v3.2.2
2024-01-25T06:08:18.789Z [events] Connecting to RabbitMQ...
2024-01-25T06:08:19.012Z [events] Connected to RabbitMQ
2024-01-25T06:08:19.123Z [events] Binding to exchange 'cloudmatrix.events'...
2024-01-25T06:08:19.456Z [events] Error: Channel closed by server: 404 (NOT-FOUND) - no exchange 'cloudmatrix.events' in vhost '/'
2024-01-25T06:08:19.457Z [events] FATAL: Cannot start without exchange
```

---

## Root Cause Analysis

### Issue 1: Circular Import Chain

The shared modules have a circular dependency chain:

```
shared/index.js
  -> requires shared/clients/index.js
     -> requires shared/events/index.js
        -> requires shared/utils/index.js
           -> requires shared/realtime/index.js
              -> requires shared/clients/index.js  <-- CIRCULAR!
```

This circular import causes:
- Stack overflow on fresh pod startup
- Intermittent behavior depending on module load order
- Complete service failure on any pod restart

### Issue 2: Missing Await on WebSocket Bind

```javascript
// presence/src/services/presence.js
async initializeWebSocket(server) {
  const wss = new WebSocket.Server({ server });
  // Missing await! Server not ready when function returns
  return wss;
}
```

The health check runs before WebSocket is actually bound:
- Service reports "ready"
- Load balancer sends traffic
- First WebSocket connections fail
- Health check eventually fails
- Pod gets killed, restarts, cycle repeats

### Issue 3: Exchange Not Declared Before Binding

```javascript
// events/index.js
async connect() {
  const channel = await connection.createChannel();
  // Tries to bind to exchange that doesn't exist
  await channel.bindQueue(queue, 'cloudmatrix.events', routingKey);
  // Should have declared exchange first:
  // await channel.assertExchange('cloudmatrix.events', 'topic', { durable: true });
}
```

### Issue 4: Elasticsearch Index Not Created on Startup

```javascript
// search/index.js
async initialize() {
  await this.connectToElasticsearch();
  // createIndex() is never called!
  // Index doesn't exist, all searches fail
}
```

---

## Cascade Effect Analysis

The failures cascade through the system:

```
1. shared/index.js circular import
   -> gateway cannot start
   -> no API requests served

2. presence WebSocket race
   -> presence service unhealthy
   -> real-time collaboration unavailable
   -> users see "disconnected" state

3. events exchange missing
   -> event handlers crash
   -> no document change events processed
   -> search index not updated
   -> notifications not sent

4. search index missing
   -> all search queries return errors
   -> users cannot find documents
```

---

## Slack Thread During Incident

**#incident-2024-01-25** (06:20):

**@sre.oncall** (06:20):
> Rollback to v3.2.1 didn't fix it. This issue was already in v3.2.1, we just hadn't restarted pods since it was introduced.

**@dev.marcus** (06:25):
> Looking at the stack trace. It's a circular import. `shared/realtime/index.js` requires `shared/clients` which requires `shared/events` which requires... it's a loop.

**@dev.sarah** (06:28):
> Found when this was introduced - commit 2 weeks ago added a new feature that needed ServiceClient in realtime module. That created the cycle.

**@sre.oncall** (06:30):
> We have 4 distinct startup issues:
> 1. Circular import (gateway, all services using shared)
> 2. WebSocket bind race (presence)
> 3. Exchange not declared (events)
> 4. Index not created (search)

**@dev.alex** (06:35):
> The WebSocket issue is subtle. The `initialize()` function is async but we're not awaiting the server.listen() call inside it. By the time health check runs, the port isn't actually bound yet.

**@dev.marcus** (06:40):
> I can fix the circular import by lazy-loading ServiceClient in realtime module. Working on patch now.

**@sre.oncall** (06:45):
> Customer impact update:
> - 100% of real-time collaboration unavailable
> - 100% of search unavailable
> - API gateway returning 503 for 60% of requests
> - ~45,000 active users affected

**@dev.sarah** (06:50):
> Events fix ready. Need to assert the exchange exists before binding:
> ```javascript
> await channel.assertExchange('cloudmatrix.events', 'topic', { durable: true });
> await channel.bindQueue(queue, 'cloudmatrix.events', routingKey);
> ```

**@dev.alex** (06:55):
> Search fix ready. Added `createIndex()` call to initialization:
> ```javascript
> async initialize() {
>   await this.connectToElasticsearch();
>   await this.createIndex(); // Now we create the index if it doesn't exist
> }
> ```

**@dev.marcus** (07:00):
> Circular import fix ready. Changed realtime/index.js to use delayed require:
> ```javascript
> // Instead of top-level require:
> // const { ServiceClient } = require('../clients');
>
> // Use lazy loading:
> function getServiceClient() {
>   return require('../clients').ServiceClient;
> }
> ```

**@sre.oncall** (07:10):
> All fixes merged into hotfix branch. Deploying v3.2.3.

**@sre.oncall** (07:15):
> v3.2.3 deploying. First pods coming up... gateway healthy! presence healthy! search healthy! events healthy!

**@sre.oncall** (07:20):
> All services recovered. Incident resolved.

---

## Post-Incident Action Items

1. **Add startup dependency tests** - CI should catch circular imports
2. **Add proper health check timing** - Health checks should verify all async initialization complete
3. **Infrastructure as Code for exchanges/indexes** - Don't rely on application code to create infrastructure
4. **Canary deployment** - Would have caught this before full rollout

---

## Files to Investigate

- `shared/index.js` - Entry point, circular import
- `shared/clients/index.js` - Client initialization
- `shared/events/index.js` - Event bus, exchange binding
- `shared/utils/index.js` - Part of circular chain
- `shared/realtime/index.js` - WebSocket manager, circular import source
- `services/presence/src/services/presence.js` - WebSocket bind race
- `services/search/src/services/search.js` - Index creation

---

**Status**: RESOLVED
**Duration**: 1 hour 15 minutes
**Root Cause**: Multiple initialization bugs (circular import, race conditions, missing setup)
**Customer Impact**: ~45,000 users, 100% real-time/search unavailable for 1+ hour
