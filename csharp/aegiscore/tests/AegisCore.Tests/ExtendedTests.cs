using Xunit;

namespace AegisCore.Tests;

public sealed class ExtendedTests
{
    // === Domain / Model Tests ===

    [Fact]
    public void SeverityClassifyEmergency()
    {
        Assert.Equal(Severity.Critical, Severity.Classify("EMERGENCY at port"));
        Assert.Equal(Severity.High, Severity.Classify("urgent repair"));
        Assert.Equal(Severity.Medium, Severity.Classify("moderate delay"));
        Assert.Equal(Severity.Low, Severity.Classify("minor maintenance"));
        Assert.Equal(Severity.Info, Severity.Classify("routine check"));
    }

    [Fact]
    public void SeveritySlaByLevel()
    {
        Assert.Equal(15, Severity.SlaByLevel(5));
        Assert.Equal(30, Severity.SlaByLevel(4));
        Assert.Equal(60, Severity.SlaByLevel(3));
        Assert.Equal(120, Severity.SlaByLevel(2));
        Assert.Equal(240, Severity.SlaByLevel(1));
        Assert.Equal(60, Severity.SlaByLevel(99));
    }

    [Fact]
    public void VesselManifestAttributes()
    {
        var heavy = new VesselManifest("V1", "Atlas", 60000.0, 1200, true);
        var light = new VesselManifest("V2", "Hermes", 20000.0, 800, false);
        Assert.True(heavy.IsHeavy);
        Assert.False(light.IsHeavy);
        Assert.Equal(50.0, heavy.ContainerWeightRatio);
        Assert.Equal(25.0, light.ContainerWeightRatio);
    }

    [Fact]
    public void OrderFactoryCreateBatch()
    {
        var orders = OrderFactory.CreateBatch(["a", "b", "c"], 4, 30);
        Assert.Equal(3, orders.Count);
        Assert.All(orders, o => Assert.Equal(4, o.Urgency));
        Assert.All(orders, o => Assert.Equal(30, o.SlaMinutes));
    }

    [Fact]
    public void OrderFactoryValidateOrder()
    {
        Assert.Null(OrderFactory.ValidateOrder(new DispatchOrder("valid", 3, 60)));
        Assert.NotNull(OrderFactory.ValidateOrder(new DispatchOrder("", 3, 60)));
        Assert.NotNull(OrderFactory.ValidateOrder(new DispatchOrder("x", 0, 60)));
        Assert.NotNull(OrderFactory.ValidateOrder(new DispatchOrder("x", 3, 0)));
    }

    // === Allocator Tests ===

    [Fact]
    public void DispatchBatchSplitsCorrectly()
    {
        var (planned, rejected) = Allocator.DispatchBatch(
        [
            new DispatchOrder("a", 5, 10),
            new DispatchOrder("b", 2, 90),
            new DispatchOrder("c", 4, 20)
        ], 2);

        Assert.Equal(2, planned.Count);
        Assert.Single(rejected);
        Assert.Equal("b", rejected[0].Id);
    }

    [Fact]
    public void EstimateCostScalesWithSeverity()
    {
        var low = Allocator.EstimateCost(1, 120, 100.0);
        var high = Allocator.EstimateCost(5, 120, 100.0);
        Assert.True(high > low);
    }

    [Fact]
    public void AllocateCostsDividesBudget()
    {
        var orders = new List<DispatchOrder>
        {
            new("a", 2, 60), new("b", 3, 60)
        };
        var costs = Allocator.AllocateCosts(orders, 100.0);
        Assert.Equal(2, costs.Count);
        Assert.True(Math.Abs(costs.Sum(c => c.Cost) - 100.0) < 1.0);
    }

    [Fact]
    public void EstimateTurnaroundHazmatMultiplier()
    {
        var normal = Allocator.EstimateTurnaround(500, false);
        var hazmat = Allocator.EstimateTurnaround(500, true);
        Assert.Equal(normal * 1.5, hazmat);
    }

    [Fact]
    public void ValidateBatchDetectsDuplicates()
    {
        var err = Allocator.ValidateBatch([new DispatchOrder("a", 3, 60), new DispatchOrder("a", 4, 30)]);
        Assert.Contains("duplicate", err!);
    }

    [Fact]
    public void BerthPlannerConflictDetection()
    {
        var a = new BerthSlot("B1", 8, 14, true, "V1");
        var b = new BerthSlot("B1", 10, 16, true, "V2");
        var c = new BerthSlot("B2", 10, 16, true, "V3");
        Assert.True(BerthPlanner.HasConflict(a, b));
        Assert.False(BerthPlanner.HasConflict(a, c));
    }

    [Fact]
    public void RollingWindowSchedulerLifecycle()
    {
        var sched = new RollingWindowScheduler(60);
        sched.Submit(100, "o1");
        sched.Submit(110, "o2");
        Assert.Equal(2, sched.Count);
        var expired = sched.Flush(170);
        Assert.Single(expired);
        Assert.Equal(1, sched.Count);
    }

    // === Routing Tests ===

    [Fact]
    public void ChannelScoreComposite()
    {
        Assert.Equal(0.0, Routing.ChannelScore(0, 0.9, 5));
        var score = Routing.ChannelScore(10, 0.8, 5);
        Assert.True(score > 0);
    }

    [Fact]
    public void EstimateTransitTimeCalculation()
    {
        var hours = Routing.EstimateTransitTime(100.0, 20.0);
        Assert.Equal(5.0, hours);
        Assert.Equal(double.MaxValue, Routing.EstimateTransitTime(100.0, 0.0));
    }

    [Fact]
    public void MultiLegPlannerAggregatesTotalDistance()
    {
        var plan = MultiLegPlanner.Plan(
            [new Waypoint("A", 50.0), new Waypoint("B", 30.0), new Waypoint("C", 20.0)],
            10.0);
        Assert.Equal(100.0, plan.TotalDistance);
        Assert.Equal(10.0, plan.EstimatedHours);
        Assert.Equal(3, plan.Legs.Count);
    }

    [Fact]
    public void RouteTableCRUD()
    {
        var table = new RouteTable();
        table.Add(new Route("north", 5));
        table.Add(new Route("south", 12));
        Assert.Equal(2, table.Count);
        Assert.NotNull(table.Get("north"));
        Assert.Equal(5, table.Get("north")!.Latency);
        table.Remove("north");
        Assert.Equal(1, table.Count);
        Assert.Null(table.Get("north"));
    }

    [Fact]
    public void CompareRoutesOrdering()
    {
        var a = new Route("alpha", 5);
        var b = new Route("beta", 10);
        Assert.True(Routing.CompareRoutes(a, b) < 0);
        Assert.True(Routing.CompareRoutes(b, a) > 0);
    }

    // === Policy Tests ===

    [Fact]
    public void PreviousPolicyDeescalates()
    {
        Assert.Equal("restricted", Policy.PreviousPolicy("halted"));
        Assert.Equal("watch", Policy.PreviousPolicy("restricted"));
        Assert.Equal("normal", Policy.PreviousPolicy("normal"));
    }

    [Fact]
    public void ShouldDeescalateThresholds()
    {
        Assert.True(Policy.ShouldDeescalate(10, "halted"));
        Assert.False(Policy.ShouldDeescalate(9, "halted"));
        Assert.True(Policy.ShouldDeescalate(7, "restricted"));
        Assert.True(Policy.ShouldDeescalate(5, "watch"));
        Assert.False(Policy.ShouldDeescalate(100, "normal"));
    }

    [Fact]
    public void SlaComplianceCalculation()
    {
        Assert.True(Policy.CheckSlaCompliance(30, 60));
        Assert.False(Policy.CheckSlaCompliance(90, 60));
        var pct = Policy.SlaPercentage([(30, 60), (90, 60), (50, 60)]);
        Assert.True(Math.Abs(pct - 66.666) < 1.0);
    }

    [Fact]
    public void PolicyEngineEscalateDeescalate()
    {
        var engine = new PolicyEngine();
        Assert.Equal("normal", engine.Current);
        engine.Escalate(3);
        Assert.Equal("watch", engine.Current);
        engine.Escalate(3);
        Assert.Equal("restricted", engine.Current);
        engine.Deescalate();
        Assert.Equal("watch", engine.Current);
        Assert.Equal(3, engine.History.Count);
        engine.Reset();
        Assert.Equal("normal", engine.Current);
    }

    [Fact]
    public void PolicyMetadataLookup()
    {
        var meta = PolicyMetadataStore.GetMetadata("halted");
        Assert.NotNull(meta);
        Assert.Equal(0, meta!.MaxRetries);
        Assert.Null(PolicyMetadataStore.GetMetadata("unknown"));
    }

    // === Queue Tests ===

    [Fact]
    public void PriorityQueueOrdering()
    {
        var pq = new PriorityQueue(10);
        pq.Enqueue(new QueueItem("low", 1));
        pq.Enqueue(new QueueItem("high", 9));
        pq.Enqueue(new QueueItem("mid", 5));
        var first = pq.Dequeue();
        Assert.Equal("high", first!.Id);
        Assert.Equal(9, first.Priority);
    }

    [Fact]
    public void PriorityQueueHardLimit()
    {
        var pq = new PriorityQueue(2);
        Assert.True(pq.Enqueue(new QueueItem("a", 1)));
        Assert.True(pq.Enqueue(new QueueItem("b", 2)));
        Assert.False(pq.Enqueue(new QueueItem("c", 3)));
    }

    [Fact]
    public void RateLimiterTokenBucket()
    {
        var limiter = new RateLimiter(3.0, 1.0);
        Assert.True(limiter.TryAcquire(0));
        Assert.True(limiter.TryAcquire(0));
        Assert.True(limiter.TryAcquire(0));
        Assert.False(limiter.TryAcquire(0));
        Assert.True(limiter.TryAcquire(2));
    }

    [Fact]
    public void QueueHealthMonitorStatuses()
    {
        Assert.Equal("healthy", QueueHealthMonitor.Check(10, 100).Status);
        Assert.Equal("elevated", QueueHealthMonitor.Check(65, 100).Status);
        Assert.Equal("warning", QueueHealthMonitor.Check(85, 100).Status);
        Assert.Equal("critical", QueueHealthMonitor.Check(100, 100).Status);
    }

    [Fact]
    public void EstimateWaitTimeInfiniteForZeroRate()
    {
        Assert.Equal(double.MaxValue, QueueGuard.EstimateWaitTime(10, 0.0));
        Assert.Equal(5.0, QueueGuard.EstimateWaitTime(10, 2.0));
    }

    // === Security Tests ===

    [Fact]
    public void SignManifestAndVerify()
    {
        var payload = "cargo:containers:1200";
        var key = "secret-key";
        var sig = Security.SignManifest(payload, key);
        Assert.True(Security.VerifyManifest(payload, key, sig));
        Assert.False(Security.VerifyManifest("tampered", key, sig));
    }

    [Fact]
    public void SanitisePathRemovesTraversal()
    {
        Assert.Equal("data/file.txt", Security.SanitisePath("../../../data/file.txt"));
        Assert.Equal("file.txt", Security.SanitisePath("/file.txt"));
    }

    [Fact]
    public void IsAllowedOriginCheck()
    {
        Assert.True(Security.IsAllowedOrigin("https://aegiscore.internal"));
        Assert.False(Security.IsAllowedOrigin("https://evil.com"));
    }

    [Fact]
    public void TokenStoreLifecycle()
    {
        var store = new TokenStore();
        store.Store("user1", "tok123", 1000, 60);
        Assert.True(store.Validate("user1", "tok123", 1050));
        Assert.False(store.Validate("user1", "tok123", 1070));
        Assert.False(store.Validate("user1", "wrong", 1050));
        Assert.Equal(1, store.Count);
        store.Revoke("user1");
        Assert.Equal(0, store.Count);
    }

    [Fact]
    public void TokenStoreCleanup()
    {
        var store = new TokenStore();
        store.Store("a", "t1", 100, 10);
        store.Store("b", "t2", 200, 10);
        var cleaned = store.Cleanup(115);
        Assert.Equal(1, cleaned);
        Assert.Equal(1, store.Count);
    }

    // === Resilience Tests ===

    [Fact]
    public void DeduplicateKeepsFirst()
    {
        var events = Resilience.Deduplicate(
        [
            new ReplayEvent("a", 1),
            new ReplayEvent("a", 2),
            new ReplayEvent("b", 1)
        ]);
        Assert.Equal(2, events.Count);
        Assert.Equal(1, events.First(e => e.Id == "a").Sequence);
    }

    [Fact]
    public void ReplayConvergenceCheck()
    {
        var a = new ReplayEvent[] { new("x", 1), new("x", 2), new("y", 1) };
        var b = new ReplayEvent[] { new("y", 1), new("x", 2), new("x", 1) };
        Assert.True(Resilience.ReplayConverges(a, b));
    }

    [Fact]
    public void CircuitBreakerTransitions()
    {
        var cb = new CircuitBreaker(3, 2);
        Assert.Equal(CircuitBreakerState.Closed, cb.State);
        Assert.True(cb.IsCallPermitted);
        cb.RecordFailure();
        cb.RecordFailure();
        cb.RecordFailure();
        Assert.Equal(CircuitBreakerState.Open, cb.State);
        Assert.False(cb.IsCallPermitted);
        cb.AttemptReset();
        Assert.Equal(CircuitBreakerState.HalfOpen, cb.State);
        Assert.True(cb.IsCallPermitted);
        cb.RecordSuccess();
        cb.RecordSuccess();
        Assert.Equal(CircuitBreakerState.Closed, cb.State);
    }

    [Fact]
    public void CheckpointManagerRecordAndGet()
    {
        var mgr = new CheckpointManager(10);
        mgr.Record(new Checkpoint("cp1", 5, 1000));
        Assert.Equal(1, mgr.Count);
        var cp = mgr.Get("cp1");
        Assert.NotNull(cp);
        Assert.Equal(5, cp!.Sequence);
        Assert.True(mgr.ShouldCheckpoint(20, 5));
        Assert.False(mgr.ShouldCheckpoint(12, 5));
        mgr.Reset();
        Assert.Equal(0, mgr.Count);
    }

    // === Statistics Tests ===

    [Fact]
    public void MeanVarianceStdDev()
    {
        double[] data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];
        var mean = Statistics.Mean(data);
        Assert.Equal(5.0, mean);
        var variance = Statistics.Variance(data);
        Assert.True(Math.Abs(variance - 4.0) < 0.01);
        var stddev = Statistics.StdDev(data);
        Assert.True(Math.Abs(stddev - 2.0) < 0.01);
    }

    [Fact]
    public void MedianEvenOdd()
    {
        Assert.Equal(3.0, Statistics.Median([1.0, 3.0, 5.0]));
        Assert.Equal(2.5, Statistics.Median([1.0, 2.0, 3.0, 4.0]));
        Assert.Equal(0.0, Statistics.Median(Array.Empty<double>()));
    }

    [Fact]
    public void MovingAverageWindowed()
    {
        double[] values = [1.0, 2.0, 3.0, 4.0, 5.0];
        var ma = Statistics.MovingAverage(values, 3);
        Assert.Equal(3, ma.Count);
        Assert.Equal(2.0, ma[0]);
        Assert.Equal(3.0, ma[1]);
        Assert.Equal(4.0, ma[2]);
    }

    [Fact]
    public void ResponseTimeTrackerPercentiles()
    {
        var tracker = new ResponseTimeTracker(100);
        for (var i = 1; i <= 100; i++) tracker.Record(i);
        Assert.Equal(100, tracker.Count);
        Assert.True(tracker.P50 >= 40 && tracker.P50 <= 60);
        Assert.True(tracker.P95 >= 90);
        Assert.True(tracker.P99 >= 95);
    }

    [Fact]
    public void HeatmapGeneratorAccumulates()
    {
        var events = new[]
        {
            new HeatmapEvent(0, 0, 1.0),
            new HeatmapEvent(0, 0, 2.0),
            new HeatmapEvent(1, 1, 3.0),
        };
        var cells = HeatmapGenerator.Generate(events, 3, 3);
        Assert.Equal(9, cells.Count);
        Assert.Equal(3.0, cells.First(c => c.Row == 0 && c.Col == 0).Value);
    }

    // === Workflow Tests ===

    [Fact]
    public void WorkflowAllowedTransitions()
    {
        var from_queued = Workflow.AllowedTransitions("queued");
        Assert.Contains("allocated", from_queued);
        Assert.Contains("cancelled", from_queued);
        Assert.Empty(Workflow.AllowedTransitions("arrived"));
    }

    [Fact]
    public void WorkflowShortestPath()
    {
        var path = Workflow.ShortestPath("queued", "arrived");
        Assert.NotNull(path);
        Assert.Equal("queued", path![0]);
        Assert.Equal("arrived", path[^1]);
        Assert.True(path.Count >= 3);
    }

    [Fact]
    public void WorkflowEngineLifecycle()
    {
        var engine = new WorkflowEngine();
        engine.Register("ship-1");
        Assert.Equal("queued", engine.GetState("ship-1"));
        Assert.Equal(1, engine.ActiveCount);
        var r1 = engine.Transition("ship-1", "allocated", 100);
        Assert.True(r1.Success);
        Assert.Equal("queued", r1.From);
        var r2 = engine.Transition("ship-1", "departed", 200);
        Assert.True(r2.Success);
        var r3 = engine.Transition("ship-1", "arrived", 300);
        Assert.True(r3.Success);
        Assert.True(engine.IsTerminal("ship-1"));
        Assert.Equal(0, engine.ActiveCount);
        Assert.Equal(3, engine.History.Count);
        Assert.Equal(3, engine.AuditLog.Count);
    }

    [Fact]
    public void WorkflowEngineRejectsInvalidTransition()
    {
        var engine = new WorkflowEngine();
        engine.Register("ship-2");
        var r = engine.Transition("ship-2", "arrived", 100);
        Assert.False(r.Success);
        Assert.Contains("cannot transition", r.Error);
    }

    // === Contracts Tests ===

    [Fact]
    public void ServiceRegistryDefinitions()
    {
        var all = ServiceRegistry.All();
        Assert.Equal(8, all.Count);
        Assert.Contains(all, d => d.Id == "gateway");
    }

    [Fact]
    public void ServiceRegistryGetServiceUrl()
    {
        var url = ServiceRegistry.GetServiceUrl("gateway");
        Assert.Contains("8150", url!);
        Assert.Contains("/health", url);
        Assert.Null(ServiceRegistry.GetServiceUrl("nonexistent"));
    }

    [Fact]
    public void ServiceRegistryValidateContract()
    {
        var defs = ServiceRegistry.All();
        Assert.Null(ServiceRegistry.ValidateContract(defs));
    }

    [Fact]
    public void ServiceRegistryTopologicalOrder()
    {
        var defs = ServiceRegistry.All();
        var order = ServiceRegistry.TopologicalOrder(defs);
        Assert.NotNull(order);
        Assert.Equal(8, order!.Count);
        Assert.Equal("gateway", order[0]);
    }
}
