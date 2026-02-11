# Slack Discussion: Rate Limiter Not Working

## #backend-eng - January 13, 2024

---

**@sre.alex** (09:15):
> Heads up everyone - we're seeing some weird patterns in our traffic analytics. The rate limiter doesn't seem to be doing its job properly under certain conditions.

**@sre.alex** (09:16):
> Screenshot from Grafana showing request rates:
```
Time Window: 09:00-09:15
IP: 203.0.113.42
Requests/sec: 847
Expected limit: 100 RPS
Rate limit rejections: 12
```

**@dev.jordan** (09:22):
> That's strange. We're definitely applying rate limiting via the middleware. What's the pattern you're seeing?

**@sre.alex** (09:25):
> It's inconsistent. During normal load (single-threaded testing), the rate limiter works fine. But when we have burst traffic from the same IP, requests seem to slip through.

**@sre.alex** (09:27):
> I ran a quick load test:
```bash
# Sequential requests - rate limiting works
for i in {1..200}; do curl -s api.cloudvault.io/health; done
# Result: 100 succeeded, 100 rejected (429 Too Many Requests)

# Concurrent requests - rate limiting fails
for i in {1..20}; do
  for j in {1..10}; do curl -s api.cloudvault.io/health & done
  wait
done
# Result: 195 succeeded, 5 rejected (expected ~100 to be rejected)
```

---

**@dev.emma** (09:35):
> I think I might know what's happening. Let me check the rate limiter code...

**@dev.emma** (09:42):
> Yeah, found the issue in `ratelimit.go`. Look at the `Allow` function:
```go
func (r *RateLimiter) Allow(key string) bool {
    r.mu.Lock()
    b, exists := r.buckets[key]
    // ... create bucket if not exists ...
    r.mu.Unlock()  // <-- We unlock here

    // <-- Then modify the bucket without any lock!
    now := time.Now()
    elapsed := now.Sub(b.lastFill).Seconds()
    b.tokens = min(float64(r.capacity), b.tokens+elapsed*float64(r.rate))
    b.lastFill = now
    // ...
}
```

**@dev.emma** (09:44):
> We're releasing the global lock before modifying the bucket. Multiple goroutines can grab the same bucket and all modify it concurrently. Classic race condition.

**@dev.jordan** (09:48):
> Oh that's bad. But wait, each bucket has its own mutex too, right?

**@dev.emma** (09:51):
> It does, but we're never using it. Look:
```go
type bucket struct {
    tokens    float64
    lastFill  time.Time
    mu        sync.Mutex  // This is never locked!
}
```

**@dev.jordan** (09:55):
> And I bet the bucket mutex is a value, not a pointer. So if the bucket is ever copied, the mutex becomes useless.

**@dev.emma** (09:58):
> Exactly. There's actually another mutex issue in the main RateLimiter struct too:
```go
type RateLimiter struct {
    buckets  map[string]*bucket
    rate     int
    capacity int
    mu       sync.Mutex  // Value, not pointer - will be copied
}
```

---

**@sre.alex** (10:05):
> Is this also causing the memory growth I'm seeing in the rate limiter? The cleanup goroutine seems to not be cleaning up properly.

**@dev.emma** (10:08):
> Let me check... oh no:
```go
func (r *RateLimiter) StartCleanup() {
    go func() {
        ticker := time.NewTicker(10 * time.Minute)
        for range ticker.C {
            r.CleanupOldBuckets()
        }
    }()  // <-- This never stops!
}
```

**@dev.emma** (10:10):
> Every time `RateLimit` middleware is called, if `globalLimiter == nil`, it creates a new limiter. If the limiter is somehow nil'd (maybe during hot reload or testing), we'd start accumulating cleanup goroutines.

---

**@dev.jordan** (10:15):
> There's also the sliding window limiter. Has anyone tested that?

**@sre.alex** (10:18):
> I tried instantiating it in our test environment and it immediately panicked:
```
panic: assignment to entry in nil map

goroutine 1 [running]:
internal/middleware.(*SlidingWindowLimiter).Allow(0xc0000a6000, {0x7f8c2d, 0x7})
    /app/internal/middleware/ratelimit.go:152 +0x1a7
```

**@dev.emma** (10:22):
> Makes sense. `NewSlidingWindowLimiter` doesn't initialize the `windows` map:
```go
func NewSlidingWindowLimiter(windowSize time.Duration, limit int) *SlidingWindowLimiter {
    return &SlidingWindowLimiter{
        // windows map not initialized!
        windowSize: windowSize,
        limit: limit,
    }
}
```

---

**@security.chen** (10:30):
> This is a security concern. If rate limiting is bypassable, we're vulnerable to brute-force attacks and DoS.

**@sre.alex** (10:32):
> Agreed. We need to fix this before someone exploits it. Adding to the sprint as P0.

**@dev.emma** (10:35):
> I'll put together a fix. Need to:
1. Use the per-bucket mutex properly
2. Consider making mutexes pointers
3. Initialize the windows map in sliding window limiter
4. Add a way to stop the cleanup goroutine

**@dev.jordan** (10:38):
> Don't forget to run `go test -race ./internal/middleware/...` after the fix. That should catch any remaining races.

---

## Summary of Issues

1. **Token bucket race condition**: Bucket tokens modified outside of any lock
2. **Mutex by value**: Both `RateLimiter.mu` and `bucket.mu` are values, not pointers
3. **Goroutine leak**: Cleanup goroutine runs forever with no stop mechanism
4. **Nil map panic**: SlidingWindowLimiter.windows never initialized

## Files to Fix

- `internal/middleware/ratelimit.go`
