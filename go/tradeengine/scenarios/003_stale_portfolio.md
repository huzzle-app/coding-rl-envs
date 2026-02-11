# Slack Thread: Portfolio Not Updating After Trades

## #platform-support Channel

---

**Sarah (Trading Desk)** - 10:15 AM
> Hey team, getting reports from users that their portfolio isn't showing recent trades. One customer says they bought 500 shares of AAPL 20 minutes ago but portfolio still shows old quantity. Trade confirmation email went out fine.

---

**Mike (Platform Eng)** - 10:18 AM
> Looking at it. Can you get me the user ID?

---

**Sarah (Trading Desk)** - 10:19 AM
> User ID: `usr_8a7b9c2d`. Trade ID: `trd_f3e4d5c6`

---

**Mike (Platform Eng)** - 10:22 AM
> Interesting. Checked the database directly:
> ```sql
> SELECT * FROM positions WHERE user_id = 'usr_8a7b9c2d' AND symbol = 'AAPL';
> -- Shows: quantity = 1500 (the updated amount)
>
> SELECT * FROM trades WHERE id = 'trd_f3e4d5c6';
> -- Shows: status = 'filled', quantity = 500
> ```
> Database looks correct. Trade was processed. Position updated.

---

**Sarah (Trading Desk)** - 10:24 AM
> But the UI still shows 1000 shares. Customer is getting frustrated.

---

**Mike (Platform Eng)** - 10:28 AM
> Checked Redis cache:
> ```
> GET portfolio:usr_8a7b9c2d
> ```
> Shows old data with 1000 shares. Cache isn't invalidated.

---

**Tom (SRE)** - 10:30 AM
> We might have a cache invalidation issue. What's the TTL on portfolio cache?

---

**Mike (Platform Eng)** - 10:32 AM
> Checking... oh interesting. There's no TTL set on the Redis keys:
> ```
> TTL portfolio:usr_8a7b9c2d
> -1
> ```
> These are persisting forever until something invalidates them.

---

**Sarah (Trading Desk)** - 10:33 AM
> Is there a manual way to clear it for now? Customer is escalating.

---

**Mike (Platform Eng)** - 10:35 AM
> Yeah, I can DELETE the key manually. Done. Can you ask them to refresh?

---

**Sarah (Trading Desk)** - 10:37 AM
> That worked! But we can't do this for every trade...

---

**Tom (SRE)** - 10:40 AM
> Looking at the portfolio service code. There's a GetPortfolio method that:
> 1. Checks in-memory cache first
> 2. If miss, checks Redis
> 3. If miss, loads from DB
>
> But I don't see where cache invalidation happens after trades.

---

**Mike (Platform Eng)** - 10:45 AM
> Found the invalidation code in `internal/portfolio/manager.go`:
> ```go
> func (m *Manager) InvalidateCache(ctx context.Context, userID string) {
>     // Delete from Redis
>     m.redis.Del(ctx, "portfolio:"+userID)
>     // What about in-memory cache?
> }
> ```
> It only invalidates Redis, not the in-memory cache.

---

**Tom (SRE)** - 10:48 AM
> :facepalm: So if a user hits the same pod twice, they get stale in-memory cache even after Redis is invalidated.

---

**Mike (Platform Eng)** - 10:50 AM
> Actually it's worse. Looking at `GetPortfolio`:
> ```go
> // Check Redis cache
> cached, err := m.redis.Get(ctx, cacheKey).Result()
> if err == nil {
>     var portfolio Portfolio
>     if json.Unmarshal([]byte(cached), &portfolio) == nil {
>         // Returns data but doesn't update in-memory cache
>         return &portfolio, nil
>     }
> }
> ```
> When we fetch from Redis, we don't refresh the in-memory cache. So the in-memory cache is always stale after first load.

---

**Sarah (Trading Desk)** - 10:52 AM
> How many customers are affected?

---

**Tom (SRE)** - 10:55 AM
> Checking logs... we have about 3 portfolio pods with sticky sessions disabled. Any user making trades will see stale data if they hit the same pod twice within... well, forever, since there's no TTL or invalidation.

---

**Mike (Platform Eng)** - 10:58 AM
> Also found another issue. When a position update comes in via NATS:
> ```go
> func (m *Manager) handlePositionUpdate(msg *nats.Msg) {
>     // Parse message
>     var update PositionUpdate
>     json.Unmarshal(msg.Data, &update)
>
>     // This only invalidates Redis, not in-memory
>     m.InvalidateCache(context.Background(), update.UserID)
> }
> ```
> The invalidation is called but doesn't clear the local cache.

---

**Alex (Backend Lead)** - 11:05 AM
> @Mike what about the thundering herd protection? If we fix invalidation and everyone's cache gets cleared at once...

---

**Mike (Platform Eng)** - 11:08 AM
> Good point. The Redis code has no singleflight or mutex. If cache is cold and 100 requests come in simultaneously, we'd have 100 DB queries.
>
> Looking at the refresh logic:
> ```go
> // BUG: No thundering herd protection
> portfolio, err := m.loadPortfolioFromDB(ctx, userID)
> ```
> We should really have singleflight here.

---

**Tom (SRE)** - 11:12 AM
> For now can we just add a short TTL to Redis keys? That way stale data at least expires eventually.

---

**Mike (Platform Eng)** - 11:15 AM
> We could, but then we need to handle the N+1 problem too. Every portfolio load does:
> ```go
> for _, position := range positions {
>     price, _ := m.getLatestPrice(ctx, position.Symbol)
>     position.CurrentPrice = price
> }
> ```
> That's a separate Redis/DB call per position. Some portfolios have 50+ positions.

---

**Sarah (Trading Desk)** - 11:18 AM
> Customers are still complaining. Can we hotfix something today?

---

**Alex (Backend Lead)** - 11:20 AM
> Let's disable the in-memory cache for now (just comment it out) and add a 60-second TTL to Redis keys. That's a safe first step. We'll need a proper fix for the invalidation logic and thundering herd later.

---

**Mike (Platform Eng)** - 11:25 AM
> Working on it. Summary of issues found:
> 1. In-memory cache never invalidated after trades
> 2. Redis cache not refreshed from in-memory cache
> 3. No TTL on Redis cache keys
> 4. No thundering herd protection on cache miss
> 5. N+1 queries for price lookups

---

**Tom (SRE)** - 11:28 AM
> Adding to technical debt tracker. This is the third caching incident this quarter.

---

## Related Files

- `internal/portfolio/manager.go` - Portfolio caching logic
- Message handlers for position updates
- Redis cache configuration
