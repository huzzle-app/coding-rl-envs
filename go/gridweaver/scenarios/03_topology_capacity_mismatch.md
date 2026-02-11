# Slack Discussion: Grid Topology Capacity Reporting Issues

**Channel**: #grid-engineering
**Date**: 2024-03-20

---

**@sarah.chen** [09:14 AM]
Hey team, getting some weird reports from field ops. They're saying our capacity numbers don't match what they're seeing on the substations. Anyone else noticing this?

**@mike.rodriguez** [09:17 AM]
Yeah, actually. I was looking at the TotalCapacity report for the western region yesterday. It showed 4800 MW but when I manually counted the transformer ratings, I only got 2400 MW. Exactly half.

**@sarah.chen** [09:19 AM]
Half? That's suspicious. Are we double-counting something?

**@mike.rodriguez** [09:21 AM]
Possibly. We have bidirectional links in the topology graph (A->B and B->A for tie lines). Maybe we're counting both directions?

**@david.kim** [09:25 AM]
I ran into something related. The NodeCount() function is returning the wrong number. We have 47 substations in the test region, but NodeCount says 312. That's way off.

**@sarah.chen** [09:27 AM]
312... that sounds like it might be counting edges instead of nodes?

**@david.kim** [09:28 AM]
:thinking_face: Let me check... yeah, we have exactly 312 transmission lines in that region. It's definitely returning edge count, not node count.

**@priya.patel** [09:32 AM]
Adding to the pile: I'm seeing negative remaining capacity on some lines that should have headroom. The Cascadia tie line has 500 MW capacity, 400 MW in use, but RemainingCapacity() returns -100 MW.

**@mike.rodriguez** [09:34 AM]
Negative? That doesn't make sense. Even if it were overloaded, shouldn't it clamp to zero or at least show the actual remaining (100 MW in your case)?

**@priya.patel** [09:36 AM]
Right, something is backwards in the math. I think it's doing `used - capacity` instead of `capacity - used`.

**@lisa.wong** [09:41 AM]
I've got a pathfinding issue to add. FindPath() between substation-alpha and substation-omega returns a path, but the path is reversed. It gives me [omega, delta, gamma, beta, alpha] instead of [alpha, beta, gamma, delta, omega].

**@sarah.chen** [09:43 AM]
So we're navigating the grid backwards? That would explain why some of the dispatch routing seems off.

**@david.kim** [09:47 AM]
The MaxFlowEstimate is also broken. I have a path with a 200 MW bottleneck but the function returns ~66 MW. It looks like it's dividing the bottleneck by the path length for some reason.

**@mike.rodriguez** [09:49 AM]
Why would you divide by path length? Max flow through a path should just be the minimum edge capacity along that path. Length shouldn't factor in.

**@david.kim** [09:51 AM]
Exactly. 200 MW bottleneck, 3-hop path, returns 200/3 = 66.67 MW. Classic off-by-one thinking or something.

**@priya.patel** [09:55 AM]
Found another one. ConstrainedTransfer is rejecting transfers that are exactly at the available capacity. If I have 100 MW available and request exactly 100 MW, it fails. Only works if I request 99.9 MW.

**@sarah.chen** [09:57 AM]
Boundary condition bug. Using `>` instead of `>=` probably.

**@lisa.wong** [10:02 AM]
ValidateTopology is giving false confidence too. I have a node with 5 edges, one of which has invalid capacity (negative). The function returns valid because it only checks the first edge of each node.

**@mike.rodriguez** [10:05 AM]
:facepalm: So if the first edge is valid, it stops checking? That's a recipe for missed errors.

**@david.kim** [10:08 AM]
BalanceLoad is truncating too aggressively. With 1000 MW across 3 nodes, it should give 333.33 MW each. Instead it gives 333 MW each (999 total), losing 1 MW. With 7 nodes and 1000 MW, we lose 6 MW to integer truncation.

**@sarah.chen** [10:12 AM]
Let me guess - it's doing integer division before converting to float?

**@david.kim** [10:13 AM]
:point_up: Exactly that pattern.

**@priya.patel** [10:18 AM]
TransferCost is way higher than expected too. For a 100km transfer, the cost is 100x what our model predicts. Feels like distance is being squared somewhere when it should be linear.

**@sarah.chen** [10:22 AM]
OK let me summarize what we're seeing:
1. TotalCapacity double-counting bidirectional edges
2. NodeCount returning edge count instead
3. RemainingCapacity returning negative values
4. FindPath returning reversed paths
5. MaxFlowEstimate dividing by path length incorrectly
6. ConstrainedTransfer rejecting boundary-exact values
7. ValidateTopology only checking first edge per node
8. BalanceLoad using integer division
9. TransferCost squaring distance

All of this is in the topology package. @team-leads can we prioritize a review of `internal/topology/graph.go`?

**@alex.thompson** [10:25 AM]
:alert: This is concerning. Capacity mismatches at this scale could lead to overloads if we're dispatching based on inflated capacity numbers. I'm escalating to the safety review board.

**@sarah.chen** [10:27 AM]
Agreed. I'll file tickets for each issue. Can someone check if there are concurrent access issues too? I saw a race detector warning from AddEdge recently.

**@mike.rodriguez** [10:29 AM]
I'll run `go test -race` on the topology package and report back.

---

**Thread: Race Condition Follow-up**

**@mike.rodriguez** [11:45 AM]
Confirmed data race in AddEdge. The function modifies the graph's edge map without acquiring the write lock. Concurrent topology updates from multiple regions are corrupting each other.

**@sarah.chen** [11:47 AM]
Adding that to the list. Ten bugs in one package - this is going to be a long day.

---

**Files Mentioned**:
- `internal/topology/graph.go`
