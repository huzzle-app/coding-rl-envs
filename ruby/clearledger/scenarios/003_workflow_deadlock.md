# Slack Discussion: Workflow State Machine and Routing Issues

**Channel**: #clearledger-incidents
**Date**: 2024-01-16

---

**@maria.chen** [09:14 AM]
Hey team, we're seeing weird behavior in the settlement workflow. A bunch of transactions are stuck in `canceled` state but the `terminal_state?` check is returning false for them.

**@david.kumar** [09:16 AM]
That's strange. `canceled` should definitely be terminal. What's the actual check showing?

**@maria.chen** [09:17 AM]
```ruby
Workflow.terminal_state?(:canceled)
# => false
Workflow.terminal_state?(:reported)
# => true
```
Only `reported` is being treated as terminal.

**@david.kumar** [09:19 AM]
Oh wow, so the completion tracking is broken too then? Let me check...

**@david.kumar** [09:22 AM]
Yep, `pending_count` is also wrong:
```ruby
entities = [:reported, :canceled, :drafted]
Workflow.pending_count(entities)
# Expected: 1 (just :drafted is pending)
# Actual: 2 (treating :canceled as pending too)
```

**@sarah.patel** [09:25 AM]
This is causing the batch controller to keep retrying canceled transactions. We've got 847 canceled items being requeued every cycle.

---

**@james.wong** [09:31 AM]
I'm looking at a separate issue in routing - feasible_routes is returning the wrong set of routes.

**@maria.chen** [09:33 AM]
What do you mean?

**@james.wong** [09:35 AM]
We have routes with latencies `{a: 50, b: 150, c: 200}` and max_latency of 100ms. It should return routes a and b (under 100ms), but it's returning b and c instead (over 100ms).

```ruby
routes = { a: 50, b: 150, c: 200 }
Routing.feasible_routes(routes, 100)
# Expected: { a: 50 } or maybe { a: 50, b: 150 }
# Actual: { b: 150, c: 200 }
```

**@sarah.patel** [09:37 AM]
So it's selecting INfeasible routes? That explains why EU settlement is routing through the high-latency Asia hub.

---

**@david.kumar** [09:42 AM]
Found another one. The `shortest_path` function in Workflow isn't returning the shortest path.

```ruby
Workflow.shortest_path(:drafted, :reported)
# Should return: [:drafted, :validated, :risk_checked, :settled, :reported]
# Sometimes returns nil or a longer path
```

**@maria.chen** [09:44 AM]
BFS should find shortest path. Is the algorithm wrong?

**@david.kumar** [09:47 AM]
Looking at the code... it's storing the path when it finds the destination but it's calling the variable `longest` and it's not breaking out of the loop. It keeps searching.

**@james.wong** [09:50 AM]
The congestion_score also seems inverted:
```ruby
Routing.congestion_score(80, 100)
# Expected: 0.8 (80% utilized)
# Actual: 1.25 (inverted ratio)
```

**@sarah.patel** [09:52 AM]
So low-congestion routes are scored as high-congestion and vice versa? That's why the load balancer is avoiding our fastest routes!

---

**@maria.chen** [10:01 AM]
Let me summarize what we've found:
1. `terminal_state?` only recognizes `:reported`, not `:canceled`
2. `pending_count` doesn't exclude `:canceled` items
3. `shortest_path` may not return actual shortest path (variable naming suggests it's finding longest?)
4. `feasible_routes` returns routes OVER max_latency instead of UNDER
5. `congestion_score` ratio is inverted

**@david.kumar** [10:03 AM]
I'll create a ticket. These all look like comparison/filter direction issues.

**@sarah.patel** [10:05 AM]
Impact assessment:
- Canceled transactions being reprocessed (847 items)
- EU traffic misrouted to Asia (200ms added latency)
- Load balancer avoiding optimal routes
- Workflow stuck in non-terminal states

**@james.wong** [10:07 AM]
Priority should be P1 - this is affecting settlement SLAs across all regions.

---

**@maria.chen** [10:15 AM]
One more thing - the `partition_impact` function in Resilience also seems inverted:
```ruby
Resilience.partition_impact(20, 100)
# Expected: 0.2 (20% of nodes affected)
# Actual: 5.0 (inverted)
```

We're getting alerts for 500% partition impact which is obviously wrong.

**@david.kumar** [10:18 AM]
OK adding that to the ticket. Definitely a pattern of inverted division operands in multiple modules.
