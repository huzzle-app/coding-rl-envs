using Xunit;

namespace StrataGuard.Tests;

public sealed class HyperMatrixTests
{
    public static IEnumerable<object[]> HyperCases()
    {
        for (var i = 0; i < 9181; i++)
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

        var cs = Routing.ChannelScore(route!.Latency + 1, 0.85, idx % 5 + 1);
        Assert.True(cs >= 0.0);
        var tt = Routing.EstimateTransitTime(100.0 + idx, 12.0);
        Assert.True(tt > 0.0);

        var src = idx % 2 == 0 ? "queued" : "allocated";
        var dst = src == "queued" ? "allocated" : "departed";
        Assert.True(Workflow.CanTransition(src, dst));
        Assert.False(Workflow.CanTransition("arrived", "queued"));

        var sp = Workflow.ShortestPath("queued", "arrived");
        Assert.NotNull(sp);
        Assert.True(Workflow.IsTerminalState("arrived"));
        Assert.False(Workflow.IsTerminalState("queued"));

        var policyState = Policy.NextPolicy(idx % 2 == 0 ? "normal" : "watch", 2 + (idx % 2));
        Assert.Contains(policyState, new[] { "watch", "restricted", "halted" });

        var prev = Policy.PreviousPolicy(policyState);
        Assert.NotNull(prev);
        var slaOk = Policy.CheckSlaCompliance(idx % 80, 60);
        Assert.Equal(idx % 80 <= 60, slaOk);

        var depth = (idx % 30) + 1;
        Assert.False(QueueGuard.ShouldShed(depth, 40, false));
        Assert.True(QueueGuard.ShouldShed(41, 40, false));

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

        var m = Statistics.Mean([1.0 + idx % 5, 2.0 + idx % 3, 3.0]);
        Assert.True(m > 0.0);
        var ma = Statistics.MovingAverage([1.0, 2.0, 3.0, 4.0], 2);
        Assert.True(ma.Count > 0);

        if (idx % 3 == 0)
        {
            var emaVals = new double[] { 1.0 + (idx % 10), 2.0 + (idx % 7), 3.0 + (idx % 5) };
            var ema = Statistics.ExponentialMovingAverage(emaVals, 0.5);
            if (ema.Count > 0)
            {
                Assert.Equal(emaVals[0], ema[0]);
            }
        }

        if (idx % 5 == 0)
        {
            var cpSeqBase = (idx % 20) + 1;
            var checkpoints = new Checkpoint[]
            {
                new($"cp-{idx}-a", cpSeqBase, 100),
                new($"cp-{idx}-b", cpSeqBase + 10, 200),
                new($"cp-{idx}-c", cpSeqBase + 20, 300),
            };
            var plan = Resilience.RecoveryPlan(checkpoints, cpSeqBase + 10);
            Assert.Contains(plan, c => c.Sequence == cpSeqBase + 10);
        }

        if (idx % 17 == 0)
        {
            var payload = $"manifest:{idx}";
            var digest = Security.Digest(payload);
            Assert.True(Security.VerifySignature(payload, digest, digest));
            Assert.False(Security.VerifySignature(payload, digest[1..], digest));

            var sig = Security.SignManifest(payload, "key");
            Assert.True(Security.VerifyManifest(payload, "key", sig));
            Assert.Equal("safe.txt", Security.SanitisePath("../safe.txt"));
        }

        var cost = Allocator.EstimateCost(idx % 5 + 1, slaA, 10.0);
        Assert.True(cost >= 0.0);
        var url = ServiceRegistry.GetServiceUrl("gateway");
        Assert.NotNull(url);

        var bucket = idx % 26;

        if (bucket == 0)
        {
            var cls = CargoOps.CargoClassification(30000);
            Assert.Equal("bulk", cls);
        }
        else if (bucket == 1)
        {
            var penalty = CargoOps.HazmatPenalty(10000, true);
            Assert.Equal(300.0, penalty);
        }
        else if (bucket == 2)
        {
            var band = CargoOps.PriorityBand(90);
            Assert.Equal("high", band);
        }
        else if (bucket == 3)
        {
            var m1 = new VesselManifest("V1", "Atlas", 50000, 1000, false);
            var m2 = new VesselManifest("V2", "Atlas", 50000, 1000, false);
            Assert.NotEqual(CargoOps.ManifestChecksum(m1), CargoOps.ManifestChecksum(m2));
        }
        else if (bucket == 4)
        {
            var vm = new VesselManifest("V1", "Atlas", 0, 100, false);
            Assert.NotNull(CargoOps.ValidateManifest(vm));
        }
        else if (bucket == 5)
        {
            Assert.Equal(120, CargoOps.MaxSlaForSeverity(2));
        }
        else if (bucket == 6)
        {
            Assert.True(CargoOps.IsExpedited(new DispatchOrder("x", 4, 30)));
        }
        else if (bucket == 7)
        {
            Assert.Equal(1, Allocator.OptimalBatchSize(10, 10));
        }
        else if (bucket == 8)
        {
            Assert.True(Allocator.UtilizationRate(3, 4) > 0.7);
        }
        else if (bucket == 9)
        {
            var sorted = Allocator.SortByPriority([
                new DispatchOrder("a", 1, 60), new DispatchOrder("b", 5, 60)]);
            Assert.Equal("b", sorted[0].Id);
        }
        else if (bucket == 10)
        {
            var congestion = Routing.CongestionScore(80, 100);
            Assert.True(congestion >= 0.7 && congestion <= 0.9);
        }
        else if (bucket == 11)
        {
            var ranked = Routing.RouteRank(
                [new Route("alpha", 5), new Route("beta", 3)],
                new HashSet<string> { "beta" });
            Assert.DoesNotContain(ranked, r => r.Channel == "beta");
        }
        else if (bucket == 12)
        {
            Assert.True(Routing.IsRouteFeasible(100.0, 100.0));
        }
        else if (bucket == 13)
        {
            var escalation = Policy.EscalationMatrix(5, 3);
            Assert.Equal(150.0, escalation);
        }
        else if (bucket == 14)
        {
            Assert.True(Policy.PolicyAuditRequired("normal", "halted"));
        }
        else if (bucket == 15)
        {
            Assert.Equal(80.0, Policy.ComplianceScore(80, 100));
        }
        else if (bucket == 16)
        {
            Assert.Equal("high", QueueGuard.BackpressureLevel(80, 100));
        }
        else if (bucket == 17)
        {
            Assert.True(QueueGuard.ShouldThrottle(100.0, 100.0));
        }
        else if (bucket == 18)
        {
            var hs = Resilience.HealthScore(7, 3);
            Assert.True(hs >= 0.6 && hs <= 0.8);
        }
        else if (bucket == 19)
        {
            Assert.Equal("healthy", ServiceOps.ServiceHealth("gw", 30, 50));
        }
        else if (bucket == 20)
        {
            var charge = CargoOps.DemurrageCharge(10000, 5, true);
            Assert.Equal(70.0, charge);
        }
        else if (bucket == 21)
        {
            var eng = new PolicyEngine();
            eng.StepwiseEscalate("restricted");
            Assert.Equal("restricted", eng.Current);
            Assert.Equal(2, eng.History.Count);
        }
        else if (bucket == 22)
        {
            var wfEngine = new WorkflowEngine();
            wfEngine.Register($"ft-{idx}");
            var ftResult = wfEngine.ForceTransition($"ft-{idx}", "allocated", idx);
            Assert.True(ftResult.Success);
            Assert.Equal("allocated", wfEngine.GetState($"ft-{idx}"));
        }
        else if (bucket == 23)
        {
            var manifests = new List<VesselManifest>
            {
                new("V1", "Light", 5000, 800, false),
                new("V2", "Heavy", 90000, 200, false),
            };
            var seq = CargoOps.LoadSequence(manifests);
            Assert.Equal("V2", seq[0].VesselId);
        }
        else if (bucket == 24)
        {
            var optRoutes = RouteSelection.SelectOptimalRoutes(
                new Route[] { new("a", 2), new("b", 100), new("c", 5) },
                new HashSet<string> { "b" }, 2);
            Assert.Equal(2, optRoutes.Count);
            Assert.DoesNotContain(optRoutes, r => r.Channel == "b");
        }
        else if (bucket == 25)
        {
            var cb = new CircuitBreaker(3, 3);
            cb.RecordFailure(); cb.RecordFailure(); cb.RecordFailure();
            cb.AttemptReset();
            cb.RecordSuccess(); cb.RecordSuccess();
            cb.RecordFailure();
            cb.AttemptReset();
            cb.RecordSuccess();
            Assert.Equal("half_open", cb.State);
        }
    }
}
