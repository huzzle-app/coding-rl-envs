using Xunit;

namespace AegisCore.Tests;

public sealed class HyperMatrixTests
{
    public static IEnumerable<object[]> HyperCases()
    {
        for (var i = 0; i < 9200; i++)
        {
            yield return new object[] { i };
        }
    }

    [Theory]
    [MemberData(nameof(HyperCases))]
    public void HyperMatrixCase(int idx)
    {
        var severityA = (idx % 7) + 1;
        var severityB = ((idx * 3) % 7) + 1;
        var slaA = 20 + (idx % 90);
        var slaB = 20 + ((idx * 2) % 90);

        var orderA = new DispatchOrder($"a-{idx}", severityA, slaA);
        var orderB = new DispatchOrder($"b-{idx}", severityB, slaB);

        var planned = Allocator.PlanDispatch(
            [
                new DispatchOrder(orderA.Id, orderA.UrgencyScore(), slaA),
                new DispatchOrder(orderB.Id, orderB.UrgencyScore(), slaB),
                new DispatchOrder($"c-{idx}", (idx % 50) + 2, 40 + (idx % 30))
            ],
            2);

        Assert.InRange(planned.Count, 1, 2);
        if (planned.Count == 2)
        {
            Assert.True(planned[0].Urgency >= planned[1].Urgency);
        }

        // DispatchBatch + ValidateOrder
        var (bPlanned, bRejected) = Allocator.DispatchBatch(
            [orderA, orderB], 1);
        Assert.True(bPlanned.Count + bRejected.Count == 2);
        // UrgencyScore must never go negative (catches AGS-URG: minus vs plus)
        Assert.True(orderA.UrgencyScore() >= 0);
        var vErr = OrderFactory.ValidateOrder(orderA);
        if (severityA >= 1 && severityA <= 5)
            Assert.Null(vErr);

        var blocked = idx % 5 == 0 ? new HashSet<string> { "beta" } : new HashSet<string>();
        var route = Routing.ChooseRoute(
            [
                new Route("alpha", 2 + (idx % 9)),
                new Route("beta", idx % 3),
                new Route("gamma", 4 + (idx % 4))
            ],
            blocked);

        Assert.NotNull(route);
        if (blocked.Contains("beta"))
        {
            Assert.NotEqual("beta", route!.Channel);
        }

        // ChannelScore + TransitTime
        var cs = Routing.ChannelScore(route!.Latency + 1, 0.85, idx % 5 + 1);
        var expectedCs = (0.85 * (idx % 5 + 1)) / (double)(route.Latency + 1);
        Assert.Equal(expectedCs, cs, 6);
        var tt = Routing.EstimateTransitTime(100.0 + idx, 12.0);
        Assert.True(tt > 0.0);

        // RouteCost must include port fee (catches AGS-COST)
        if (idx % 11 == 0)
        {
            Assert.Equal(250.0, Routing.EstimateRouteCost(100.0, 2.0, 50.0));
        }

        // Multi-leg fuel uses Sum, not Max (catches AGS-FUEL)
        if (idx % 29 == 0)
        {
            var fuelCost = RouteOptimizer.ComputeMultiLegFuelCost(
                [new Waypoint("A", 50.0), new Waypoint("B", 30.0)], 2.0, [10.0, 15.0]);
            Assert.Equal(185.0, fuelCost);
        }

        var src = idx % 2 == 0 ? "queued" : "allocated";
        var dst = src == "queued" ? "allocated" : "departed";
        Assert.True(Workflow.CanTransition(src, dst));
        Assert.False(Workflow.CanTransition("arrived", "queued"));
        // Departed vessels cannot be cancelled (catches AGS0018)
        Assert.False(Workflow.CanTransition("departed", "cancelled"));

        // ShortestPath + IsTerminalState
        var sp = Workflow.ShortestPath("queued", "arrived");
        Assert.NotNull(sp);
        Assert.True(Workflow.IsTerminalState("arrived"));
        Assert.False(Workflow.IsTerminalState("queued"));

        var policyState = Policy.NextPolicy(idx % 2 == 0 ? "normal" : "watch", 2 + (idx % 2));
        Assert.Contains(policyState, new[] { "watch", "restricted", "halted" });

        // Single failure must NOT trigger escalation (catches AGS0008)
        if (idx % 3 == 0)
        {
            var noEscalate = Policy.NextPolicy("normal", 1);
            Assert.Equal("normal", noEscalate);
        }

        // PreviousPolicy + CheckSlaCompliance
        var prev = Policy.PreviousPolicy(policyState);
        Assert.NotNull(prev);
        var slaOk = Policy.CheckSlaCompliance(idx % 80, 60);
        Assert.Equal(idx % 80 <= 60, slaOk);

        var depth = (idx % 30) + 1;
        Assert.False(QueueGuard.ShouldShed(depth, 40, false));
        Assert.True(QueueGuard.ShouldShed(41, 40, false));
        // Emergency threshold boundary (catches AGS0010)
        Assert.True(QueueGuard.ShouldShed(32, 40, true));

        // QueueHealth + EstimateWaitTime
        var health = QueueHealthMonitor.Check(depth, 40);
        Assert.NotNull(health.Status);
        var wt = QueueGuard.EstimateWaitTime(depth, 2.0);
        Assert.Equal((double)depth / 2.0, wt, 6);

        var replayed = Resilience.Replay(
        [
            new ReplayEvent($"k-{idx % 17}", 1),
            new ReplayEvent($"k-{idx % 17}", 2),
            new ReplayEvent($"z-{idx % 13}", 1)
        ]);

        Assert.True(replayed.Count >= 2);
        Assert.True(replayed.Last().Sequence >= 1);

        // Deduplicate + ReplayConverges
        var deduped = Resilience.Deduplicate(
        [
            new ReplayEvent($"d-{idx}", 1),
            new ReplayEvent($"d-{idx}", 2),
            new ReplayEvent($"e-{idx}", 1)
        ]);
        Assert.Equal(2, deduped.Count);
        Assert.True(Resilience.ReplayConverges(replayed, replayed));

        // Percentile exact value (catches AGS-PERC)
        int[] percInput = [idx % 11, (idx * 7) % 11, (idx * 5) % 11, (idx * 3) % 11];
        var p50 = Statistics.Percentile(percInput, 50);
        var sortedPerc = (int[])percInput.Clone();
        Array.Sort(sortedPerc);
        Assert.Equal(sortedPerc[1], p50);

        // Mean + MovingAverage
        var m = Statistics.Mean([1.0 + idx % 5, 2.0 + idx % 3, 3.0]);
        Assert.True(m > 0.0);
        var ma = Statistics.MovingAverage([1.0, 2.0, 3.0, 4.0], 2);
        Assert.True(ma.Count > 0);

        // EMA recurrence must use previous EMA, not raw value (catches AGS-EMA)
        if (idx % 13 == 0)
        {
            var ema = AdvancedStatistics.ExponentialMovingAverage([1.0, 3.0, 2.0], 0.5);
            Assert.Equal(2.0, ema[2], 6);
        }

        if (idx % 17 == 0)
        {
            var payload = $"manifest:{idx}";
            var digest = Security.Digest(payload);
            Assert.True(Security.VerifySignature(payload, digest, digest));
            Assert.False(Security.VerifySignature(payload, digest[1..], digest));

            // SignManifest + VerifyManifest + SanitisePath
            var sig = Security.SignManifest(payload, "key");
            Assert.True(Security.VerifyManifest(payload, "key", sig));
            Assert.Equal("safe.txt", Security.SanitisePath("..././safe.txt"));
        }

        // Snapshot must deep-copy state (catches AGS-SNAP)
        if (idx % 19 == 0)
        {
            var proj = new EventProjection();
            proj.Apply(new ReplayEvent("k1", 1));
            proj.TakeSnapshot(1);
            proj.Apply(new ReplayEvent("k2", 2));
            Assert.True(proj.HasDivergedFromSnapshot());
        }

        // Register must not overwrite existing entity state (catches AGS-REG)
        if (idx % 23 == 0)
        {
            var wfEngine = new WorkflowEngine();
            wfEngine.Register("test-reg");
            wfEngine.Transition("test-reg", "allocated", 100);
            wfEngine.Register("test-reg");
            Assert.Equal("allocated", wfEngine.GetState("test-reg"));
        }

        // EstimateCost + ServiceRegistry
        var cost = Allocator.EstimateCost(idx % 5 + 1, slaA, 10.0);
        Assert.True(cost >= 0.0);

        // ComputeLoadFactor at capacity must return >= 1.0 (catches AGS-LOAD)
        if (idx % 7 == 0)
        {
            Assert.Equal(1.0, DispatchOptimizer.ComputeLoadFactor(10, 10));
        }

        // Empty utilization history returns base limit (catches AGS-DYN)
        if (idx % 31 == 0)
        {
            Assert.Equal(100, AdaptiveQueue.ComputeDynamicLimit(100, Array.Empty<double>()));
        }

        // Risk score must never exceed 1.0 (catches AGS-RISK)
        if (idx % 37 == 0)
        {
            Assert.True(RiskAssessment.ComputeRiskScore("halted", 1.0, 0.0) <= 1.0);
        }

        // Dependency chain must list service AFTER its dependencies (catches AGS-DEPCHAIN)
        if (idx % 41 == 0)
        {
            var chain = EndpointResolver.ResolveDependencyChain("analytics");
            Assert.Equal("analytics", chain[^1]);
        }

        // Lease renewal must extend from current time, not original (catches AGS-RENEW)
        if (idx % 43 == 0)
        {
            var lm = new LeaseManager();
            lm.Acquire("r1", "h1", 100, 200);
            lm.Renew("r1", "h1", 150, 200);
            Assert.Equal(350, lm.GetLease("r1")!.ExpiresAt);
        }

        var url = ServiceRegistry.GetServiceUrl("gateway");
        Assert.NotNull(url);
        Assert.Contains(":8150", url!);
    }
}
