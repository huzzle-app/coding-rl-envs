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
        Assert.True(cs >= 0.0);
        var tt = Routing.EstimateTransitTime(100.0 + idx, 12.0);
        Assert.True(tt > 0.0);

        var src = idx % 2 == 0 ? "queued" : "allocated";
        var dst = src == "queued" ? "allocated" : "departed";
        Assert.True(Workflow.CanTransition(src, dst));
        Assert.False(Workflow.CanTransition("arrived", "queued"));

        // ShortestPath + IsTerminalState
        var sp = Workflow.ShortestPath("queued", "arrived");
        Assert.NotNull(sp);
        Assert.True(Workflow.IsTerminalState("arrived"));
        Assert.False(Workflow.IsTerminalState("queued"));

        var policyState = Policy.NextPolicy(idx % 2 == 0 ? "normal" : "watch", 2 + (idx % 2));
        Assert.Contains(policyState, new[] { "watch", "restricted", "halted" });

        // PreviousPolicy + CheckSlaCompliance
        var prev = Policy.PreviousPolicy(policyState);
        Assert.NotNull(prev);
        var slaOk = Policy.CheckSlaCompliance(idx % 80, 60);
        Assert.Equal(idx % 80 <= 60, slaOk);

        var depth = (idx % 30) + 1;
        Assert.False(QueueGuard.ShouldShed(depth, 40, false));
        Assert.True(QueueGuard.ShouldShed(41, 40, false));

        // QueueHealth + EstimateWaitTime
        var health = QueueHealthMonitor.Check(depth, 40);
        Assert.NotNull(health.Status);
        var wt = QueueGuard.EstimateWaitTime(depth, 2.0);
        Assert.True(wt >= 0.0);

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

        var p50 = Statistics.Percentile([idx % 11, (idx * 7) % 11, (idx * 5) % 11, (idx * 3) % 11], 50);
        Assert.True(p50 >= 0);

        // Mean + MovingAverage
        var m = Statistics.Mean([1.0 + idx % 5, 2.0 + idx % 3, 3.0]);
        Assert.True(m > 0.0);
        var ma = Statistics.MovingAverage([1.0, 2.0, 3.0, 4.0], 2);
        Assert.True(ma.Count > 0);

        if (idx % 17 == 0)
        {
            var payload = $"manifest:{idx}";
            var digest = Security.Digest(payload);
            Assert.True(Security.VerifySignature(payload, digest, digest));
            Assert.False(Security.VerifySignature(payload, digest[1..], digest));

            // SignManifest + VerifyManifest + SanitisePath
            var sig = Security.SignManifest(payload, "key");
            Assert.True(Security.VerifyManifest(payload, "key", sig));
            Assert.Equal("safe.txt", Security.SanitisePath("../safe.txt"));
        }

        // EstimateCost + ServiceRegistry
        var cost = Allocator.EstimateCost(idx % 5 + 1, slaA, 10.0);
        Assert.True(cost >= 0.0);
        var url = ServiceRegistry.GetServiceUrl("gateway");
        Assert.NotNull(url);
    }
}
