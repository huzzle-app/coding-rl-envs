# Deploy Failure: Application Cannot Start

## Deployment Pipeline Alert

**Severity**: Critical (P0)
**Triggered**: 2024-02-20 08:45 UTC
**Environment**: staging
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: Deployment failed - health check timeout
Service: collabcanvas-api-staging
Pipeline: deploy-staging-v1.2.1
Status: FAILED
Stage: health_check
Timeout: 120 seconds exceeded

Container logs indicate startup failure. Rolling back to v1.2.0.
```

## Deployment Timeline

**08:42 UTC** - Deployment initiated for v1.2.1

**08:43 UTC** - Container image pulled successfully

**08:43 UTC** - Container started

**08:43 UTC** - Immediate crash detected
```
Error: Cannot read properties of undefined (reading 'pool')
    at Object.<anonymous> (/app/src/config/database.js:12:1)
```

**08:44 UTC** - Kubernetes restart attempt #1

**08:44 UTC** - Same crash pattern

**08:45 UTC** - Health check timeout reached, deployment marked failed

**08:46 UTC** - Automatic rollback to v1.2.0

## Container Logs

### First Boot Attempt

```
2024-02-20T08:43:12.123Z Starting CollabCanvas API v1.2.1
2024-02-20T08:43:12.234Z Loading configuration...

/app/node_modules/sequelize/lib/dialects/postgres/connection-manager.js:47
  throw new Error(`Invalid pool configuration: ${config.pool.max}`);
        ^

Error: Invalid pool configuration: undefined
    at ConnectionManager.initPools (/app/node_modules/sequelize/lib/dialects/postgres/connection-manager.js:47:11)
    at new ConnectionManager (/app/node_modules/sequelize/lib/dialects/postgres/connection-manager.js:23:10)
    at new PostgresDialect (/app/node_modules/sequelize/lib/dialects/postgres/index.js:15:30)
    at new Sequelize (/app/node_modules/sequelize/lib/sequelize.js:234:20)
    at Object.<anonymous> (/app/src/models/index.js:8:18)
    at Module._compile (node:internal/modules/cjs/loader:1198:14)
```

### Second Boot Attempt (after restart)

```
2024-02-20T08:44:01.567Z Starting CollabCanvas API v1.2.1
2024-02-20T08:44:01.678Z Loading configuration...

RangeError: Maximum call stack size exceeded
    at Object.<anonymous> (/app/src/config/index.js:3:1)
    at Module._compile (node:internal/modules/cjs/loader:1198:14)
    at Object.<anonymous> (/app/src/config/database.js:8:1)
    at Module._compile (node:internal/modules/cjs/loader:1198:14)
    at Object.<anonymous> (/app/src/config/index.js:3:1)
    ...
    (repeating pattern)
```

## Analysis from Logs

### Issue 1: Pool Configuration Type Error

Environment variables are strings, but Sequelize expects numbers:

```javascript
// In src/config/database.js
pool: {
  max: process.env.DB_POOL_SIZE || 10,  // If DB_POOL_SIZE='5', result is '5' (string)
  min: process.env.DB_POOL_MIN || 2,
}
```

When `DB_POOL_SIZE=5` is set in environment:
- `process.env.DB_POOL_SIZE` returns `'5'` (string)
- `'5' || 10` equals `'5'` (truthy string, not 10)
- Sequelize receives `'5'` instead of `5`
- Pool validation fails

### Issue 2: Circular Import

Stack trace shows `config/index.js` and `config/database.js` importing each other:

```
/app/src/config/index.js:3 -> requires database.js
/app/src/config/database.js:8 -> requires index.js
/app/src/config/index.js:3 -> requires database.js
... (infinite loop)
```

## Environment Configuration

### Staging Environment Variables

```bash
# Set in Kubernetes ConfigMap
NODE_ENV=staging
DB_HOST=postgres-staging.internal
DB_PORT=5432
DB_NAME=collabcanvas_staging
DB_USER=collabcanvas
DB_PASSWORD=**redacted**
DB_POOL_SIZE=5          # <-- This is a string!
DB_POOL_MIN=2           # <-- This is a string!
JWT_SECRET=staging-secret-key
REDIS_HOST=redis-staging.internal
```

### Production Environment (for comparison)

```bash
# Production doesn't have these set, so defaults are used
# DB_POOL_SIZE not set -> uses default 10 (number)
# This is why production works!
```

---

## Internal Slack Thread

**#eng-infra** - February 20, 2024

**@sre.chen** (08:47):
> Staging deploy failed again. Same issue as last week. Container crashes immediately on startup.

**@dev.jordan** (08:52):
> I see two separate issues in the logs:
> 1. Pool config says "undefined" but we have DB_POOL_SIZE=5 set
> 2. Stack overflow from circular imports

**@sre.chen** (08:55):
> Wait, the pool error is weird. If DB_POOL_SIZE=5 is set, why is pool.max undefined?

**@dev.jordan** (08:58):
> Oh I see it. The circular import causes config to partially load. When database.js runs, it tries to import index.js which isn't finished loading yet.

**@dev.emma** (09:02):
> And even without the circular import, there's the string issue:
```javascript
// process.env.DB_POOL_SIZE = '5' (string)
// '5' || 10 = '5' (doesn't trigger default)
// Sequelize expects number 5, gets string '5'
```

**@sre.chen** (09:05):
> Why does production work?

**@dev.jordan** (09:08):
> Production doesn't set DB_POOL_SIZE at all, so it falls through to the default `10` which is a number.

**@dev.emma** (09:12):
> So the bug only manifests when you explicitly set the env var. Classic "works on my machine" but with infrastructure.

**@sre.chen** (09:15):
> OK so we need:
> 1. Break the circular import between config/index.js and config/database.js
> 2. Parse env vars as integers: `parseInt(process.env.DB_POOL_SIZE, 10) || 10`

**@dev.jordan** (09:18):
> There might be more string-to-number issues. Let me check all the env var usages.

---

## Local Reproduction

```bash
# Set the env var that triggers the bug
export DB_POOL_SIZE=5

# Try to start the server
npm start

# Output:
# Error: Invalid pool configuration: 5
# (Note: Sequelize error message doesn't distinguish string '5' from number 5)

# Or if circular import triggers first:
# RangeError: Maximum call stack size exceeded
```

## Temporary Workarounds

### Workaround 1: Unset DB_POOL_SIZE

```bash
# Remove explicit pool size settings
unset DB_POOL_SIZE
unset DB_POOL_MIN

# Relies on defaults (which are numbers)
```

### Workaround 2: Use production config

```bash
# Copy production ConfigMap which doesn't have pool settings
kubectl get configmap collabcanvas-prod -o yaml > temp.yaml
# Edit and apply to staging
```

## Impact Assessment

- **Blocked**: All deployments to staging and new environments
- **Production**: Currently unaffected (doesn't set these vars)
- **Risk**: If anyone adds DB_POOL_SIZE to production, it will crash

## Files to Investigate

- `src/config/index.js` - Circular import with database.js
- `src/config/database.js` - String vs number env vars, circular import
- `src/models/index.js` - Where Sequelize is initialized

---

**Status**: BLOCKED
**Assigned**: @platform-team, @config-team
**Impact**: Staging deployments blocked
**Production Risk**: Low (currently), High (if config changes)
