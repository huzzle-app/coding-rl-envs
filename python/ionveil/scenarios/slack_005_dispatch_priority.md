# Slack Thread: #ionveil-engineering

---

**Marcus Chen** [Platform Engineer] - Today at 2:14 PM

yo anyone else seeing weird dispatch ordering in staging? I'm testing the new batch import feature and the planned orders don't look right

---

**Sarah Martinez** [QA Lead] - Today at 2:16 PM

What kind of "not right"? We've had a few test failures in that area

---

**Marcus Chen** [Platform Engineer] - Today at 2:17 PM

so I have three orders:
- Order A: urgency 1, eta 09:30
- Order B: urgency 3, eta 10:00
- Order C: urgency 3, eta 08:30

capacity is 2, so it should pick the top 2 by urgency (higher = more urgent) and then by ETA for ties

---

**Marcus Chen** [Platform Engineer] - Today at 2:18 PM

expected output would be B and C (both urgency 3), with C first because earlier ETA

but I'm getting C and B with... wait let me check again

---

**Raj Patel** [Senior Backend] - Today at 2:19 PM

yeah we've been seeing `test_plan_dispatch_limits_capacity` fail intermittently. well, not intermittently - it fails consistently but only in certain test runs

---

**Sarah Martinez** [QA Lead] - Today at 2:20 PM

@Raj Patel it's not intermittent, it's failing 100% of the time. I ran the full suite this morning:

```
FAIL: tests/unit/dispatch_test.py::DispatchTests::test_plan_dispatch_limits_capacity
AssertionError: Lists differ: ['b', 'c'] != ['c', 'b']
```

---

**Marcus Chen** [Platform Engineer] - Today at 2:22 PM

wait so my test case shows `["c", "b"]` which is... C first then B. That's actually correct for same-urgency ordering by ETA

but the test expects `["c", "b"]` and it's failing? let me look at the actual assertion

---

**Sarah Martinez** [QA Lead] - Today at 2:24 PM

the test file says:
```python
self.assertEqual([o["id"] for o in out], ["c", "b"])
```

and we're getting `["b", "c"]` back

---

**Marcus Chen** [Platform Engineer] - Today at 2:25 PM

OH. so the urgency 3 ones should be first (higher urgency = higher priority), and C should come before B because 08:30 < 10:00

but we're getting B before C

---

**Raj Patel** [Senior Backend] - Today at 2:27 PM

looked at the sort in `plan_dispatch`:
```python
sorted_orders = sorted(
    orders,
    key=lambda o: (-int(o.get("urgency", 0)), str(o.get("eta", ""))),
)
```

that looks right to me? negative urgency for descending, then eta string for ascending

---

**Emily Watson** [Dispatch Team Lead] - Today at 2:29 PM

jumping in here - we've been getting complaints from the Oakland EOC about dispatch ordering. their supervisors say high-priority incidents are being planned in the wrong sequence

not sure if related but timing seems suspicious

---

**Marcus Chen** [Platform Engineer] - Today at 2:31 PM

@Emily Watson definitely could be related. what are they seeing specifically?

---

**Emily Watson** [Dispatch Team Lead] - Today at 2:33 PM

they had two severity-5 (critical) incidents come in within 2 minutes of each other. incident A had urgency score 88, incident B had urgency score 91

B should have been dispatched first but A went out ahead

---

**Raj Patel** [Senior Backend] - Today at 2:35 PM

wait that's the opposite problem. in Marcus's case we're getting B (later ETA) before C (earlier ETA). in Emily's case we're getting lower urgency before higher urgency

unless... are both of these the same root cause?

---

**Sarah Martinez** [QA Lead] - Today at 2:37 PM

just ran a bigger test set. looking at the stress test failures:

```
FAIL: tests/stress/hyper_matrix_test.py::test_case_00002
  assert planned[0]["urgency"] >= planned[1]["urgency"]
  AssertionError
```

so the first planned order has LOWER urgency than the second. sort is definitely wrong somehow

---

**Marcus Chen** [Platform Engineer] - Today at 2:40 PM

could there be something weird with how we're returning from the sort? like taking from the wrong end?

---

**Raj Patel** [Senior Backend] - Today at 2:42 PM

```python
return sorted_orders[:capacity]
```

that takes the first N after sorting. if sorting is descending by urgency (which `-urgency` should give us), the first elements should be highest urgency

unless `sorted()` is being weird with the key somehow?

---

**Lisa Park** [SRE] - Today at 2:44 PM

not to derail but we're also seeing the `choose_route` function selecting high-latency channels. could there be a pattern here with sort directions?

---

**Sarah Martinez** [QA Lead] - Today at 2:45 PM

:eyes: that's interesting. both dispatch and routing doing unexpected ordering

---

**Marcus Chen** [Platform Engineer] - Today at 2:47 PM

I'm going to do a deep dive on the sorting logic. something's not adding up. the code LOOKS correct but the behavior is wrong

@Sarah Martinez can you share the full list of test failures in the dispatch/routing area? want to see if there's a pattern

---

**Sarah Martinez** [QA Lead] - Today at 2:49 PM

here's the summary from this morning's run:

Dispatch ordering failures: ~3,100 tests
Route selection failures: ~1,200 tests
Combined in stress suite: ~6,200 tests

basically anything that relies on "pick the best/highest/lowest from a sorted list" is broken

---

**Raj Patel** [Senior Backend] - Today at 2:52 PM

I bet this is biting us in multiple places. anywhere we sort and expect min we get max, and vice versa

should probably check:
- dispatch ordering (confirmed broken)
- route selection (confirmed broken)
- priority queue dequeue order
- any scoring functions that pick top-N

---

**Emily Watson** [Dispatch Team Lead] - Today at 2:54 PM

is there a timeline for a fix? Oakland is asking if they need to do manual dispatch sequencing as a workaround

---

**Marcus Chen** [Platform Engineer] - Today at 2:56 PM

working on it now. the bug seems straightforward once we find it - just inverted sort direction somewhere. but it might be in multiple places

will update here when I have something

---

**Sarah Martinez** [QA Lead] - Today at 2:58 PM

FYI I'm blocking the release pipeline until this is fixed. we can't ship with 6k+ test failures

---

**Marcus Chen** [Platform Engineer] - Today at 3:15 PM

update: found something interesting in `routing.py:choose_route`. the sort key is:
```python
key=lambda r: (-int(r["latency"]), str(r["channel"]))
```

negative latency means highest latency first. that's... backwards? we want lowest latency

checking dispatch now

---

**Raj Patel** [Senior Backend] - Today at 3:18 PM

for dispatch we WANT highest urgency first, so negative urgency in the key is correct

but for routing we want LOWEST latency first, so it should be positive latency in the key

or maybe the issue is we're taking `[0]` when we should take `[-1]`? or the comparison operators are flipped?

---

**Marcus Chen** [Platform Engineer] - Today at 3:22 PM

digging more. will report back. this might be a few different bugs that all manifest as "wrong order"

---
