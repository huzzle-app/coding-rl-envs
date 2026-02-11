using Xunit;

namespace StrataGuard.Tests;

public sealed class ExtendedTests
{
    // === Domain / Model Tests ===

    [Fact]
    public void CargoClassificationThresholds()
    {
        Assert.Equal("bulk", CargoOps.CargoClassification(30000));
        Assert.Equal("standard", CargoOps.CargoClassification(10000));
        Assert.Equal("light", CargoOps.CargoClassification(3000));
    }

    [Fact]
    public void HazmatPenaltyCost()
    {
        var normal = CargoOps.HazmatPenalty(10000, false);
        var hazmat = CargoOps.HazmatPenalty(10000, true);
        Assert.Equal(200.0, normal);
        Assert.Equal(300.0, hazmat);
    }

    [Fact]
    public void PriorityBandBoundaries()
    {
        Assert.Equal("high", CargoOps.PriorityBand(90));
        Assert.Equal("critical", CargoOps.PriorityBand(91));
        Assert.Equal("medium", CargoOps.PriorityBand(30));
        Assert.Equal("low", CargoOps.PriorityBand(29));
    }

    [Fact]
    public void ManifestChecksumIncludesVesselId()
    {
        var m1 = new VesselManifest("V1", "Atlas", 50000, 1000, false);
        var m2 = new VesselManifest("V2", "Atlas", 50000, 1000, false);
        Assert.NotEqual(CargoOps.ManifestChecksum(m1), CargoOps.ManifestChecksum(m2));
    }

    [Fact]
    public void ValidateManifestRejectsZeroCargo()
    {
        var m = new VesselManifest("V1", "Atlas", 0, 100, false);
        Assert.NotNull(CargoOps.ValidateManifest(m));
    }

    [Fact]
    public void MaxSlaForSeverityLevel2()
    {
        Assert.Equal(120, CargoOps.MaxSlaForSeverity(2));
        Assert.Equal(15, CargoOps.MaxSlaForSeverity(5));
    }

    [Fact]
    public void IsExpeditedThreshold()
    {
        Assert.True(CargoOps.IsExpedited(new DispatchOrder("x", 4, 30)));
        Assert.False(CargoOps.IsExpedited(new DispatchOrder("x", 3, 30)));
    }

    // === Allocator Tests ===

    [Fact]
    public void OptimalBatchSizeCeiling()
    {
        Assert.Equal(1, Allocator.OptimalBatchSize(10, 10));
        Assert.Equal(2, Allocator.OptimalBatchSize(11, 10));
        Assert.Equal(1, Allocator.OptimalBatchSize(9, 10));
    }

    [Fact]
    public void UtilizationRateAsDouble()
    {
        Assert.True(Allocator.UtilizationRate(3, 4) > 0.7);
        Assert.True(Allocator.UtilizationRate(3, 4) < 0.8);
    }

    [Fact]
    public void SortByPriorityDescending()
    {
        var orders = Allocator.SortByPriority([
            new DispatchOrder("a", 1, 60),
            new DispatchOrder("b", 5, 60),
            new DispatchOrder("c", 3, 60)
        ]);
        Assert.Equal("b", orders[0].Id);
        Assert.Equal("c", orders[1].Id);
        Assert.Equal("a", orders[2].Id);
    }

    [Fact]
    public void SlaBreachPenaltyMultiplier()
    {
        var penalty = Allocator.SlaBreachPenalty(90, 60, 10.0);
        Assert.Equal(600.0, penalty);
    }

    // === Routing Tests ===

    [Fact]
    public void CongestionScoreRatio()
    {
        var score = Routing.CongestionScore(80, 100);
        Assert.True(score >= 0.7 && score <= 0.9);
    }

    [Fact]
    public void RouteRankFiltersBlocked()
    {
        var routes = Routing.RouteRank(
            [new Route("alpha", 5), new Route("beta", 3), new Route("gamma", 8)],
            new HashSet<string> { "beta" });
        Assert.DoesNotContain(routes, r => r.Channel == "beta");
    }

    [Fact]
    public void EstimateArrivalWraps24()
    {
        var arrival = Routing.EstimateArrival(22.0, 5.0);
        Assert.True(arrival >= 0 && arrival < 24);
    }

    [Fact]
    public void PortSurchargeHazmat()
    {
        var base_rate = 100.0;
        Assert.Equal(150.0, Routing.PortSurcharge("port-hazmat-1", base_rate));
    }

    [Fact]
    public void IsRouteFeasibleBoundary()
    {
        Assert.True(Routing.IsRouteFeasible(100.0, 100.0));
        Assert.True(Routing.IsRouteFeasible(99.0, 100.0));
        Assert.False(Routing.IsRouteFeasible(101.0, 100.0));
    }

    [Fact]
    public void ParallelRoutesFiltersBlocked()
    {
        var (available, blocked) = Routing.ParallelRoutes(
            [new Route("alpha", 5), new Route("beta", 3)],
            new HashSet<string> { "beta" });
        Assert.DoesNotContain(available, r => r.Channel == "beta");
        Assert.Single(blocked);
    }

    // === Policy Tests ===

    [Fact]
    public void EscalationMatrixScoring()
    {
        var score = Policy.EscalationMatrix(5, 3);
        Assert.Equal(150.0, score);
    }

    [Fact]
    public void PolicyAuditRequiredForHalted()
    {
        Assert.True(Policy.PolicyAuditRequired("normal", "halted"));
        Assert.True(Policy.PolicyAuditRequired("halted", "normal"));
    }

    [Fact]
    public void ComplianceScorePercentage()
    {
        Assert.Equal(80.0, Policy.ComplianceScore(80, 100));
        Assert.Equal(50.0, Policy.ComplianceScore(50, 100));
    }

    [Fact]
    public void MaxRetriesForRestrictedPolicy()
    {
        Assert.Equal(1, Policy.MaxRetriesForPolicy("restricted"));
        Assert.Equal(3, Policy.MaxRetriesForPolicy("normal"));
    }

    [Fact]
    public void PolicyCooldownWatch()
    {
        Assert.Equal(600, Policy.PolicyCooldown("watch"));
        Assert.Equal(0, Policy.PolicyCooldown("normal"));
    }

    [Fact]
    public void IsEmergencyPolicyIncludesRestricted()
    {
        Assert.True(Policy.IsEmergencyPolicy("restricted"));
        Assert.True(Policy.IsEmergencyPolicy("halted"));
        Assert.False(Policy.IsEmergencyPolicy("normal"));
    }

    [Fact]
    public void PolicyTransitionValidOneStep()
    {
        Assert.True(Policy.PolicyTransitionValid("normal", "watch"));
        Assert.False(Policy.PolicyTransitionValid("normal", "halted"));
    }

    [Fact]
    public void AggregateComplianceCorrect()
    {
        var records = new List<(int Actual, int Sla)> { (30, 60), (90, 60), (50, 60) };
        var result = Policy.AggregateCompliance(records);
        Assert.True(Math.Abs(result - 66.666) < 1.0);
    }

    [Fact]
    public void SlaBufferAddsTime()
    {
        Assert.Equal(72.0, Policy.SlaBuffer(60));
    }

    // === Queue Tests ===

    [Fact]
    public void BackpressureLevelBoundaries()
    {
        Assert.Equal("low", QueueGuard.BackpressureLevel(50, 100));
        Assert.Equal("medium", QueueGuard.BackpressureLevel(60, 100));
        Assert.Equal("high", QueueGuard.BackpressureLevel(80, 100));
        Assert.Equal("critical", QueueGuard.BackpressureLevel(95, 100));
    }

    [Fact]
    public void ShouldThrottleAtLimit()
    {
        Assert.True(QueueGuard.ShouldThrottle(100.0, 100.0));
        Assert.True(QueueGuard.ShouldThrottle(101.0, 100.0));
        Assert.False(QueueGuard.ShouldThrottle(99.0, 100.0));
    }

    [Fact]
    public void DrainBatchExactCount()
    {
        var pq = new PriorityQueue(10);
        for (var i = 0; i < 5; i++) pq.Enqueue(new QueueItem($"item-{i}", i));
        var drained = QueueGuard.DrainBatch(pq, 3);
        Assert.Equal(3, drained.Count);
    }

    [Fact]
    public void QueueUtilizationClamped()
    {
        Assert.True(QueueGuard.QueueUtilization(150, 100) <= 1.0);
    }

    [Fact]
    public void IsOverloadedChecksCorrectStatus()
    {
        var critical = new QueueHealth(100, 100, 1.0, "critical");
        var warning = new QueueHealth(80, 100, 0.8, "warning");
        Assert.True(QueueGuard.IsOverloaded(critical));
        Assert.False(QueueGuard.IsOverloaded(warning));
    }

    // === Security Tests ===

    [Fact]
    public void AccessLevelRoles()
    {
        Assert.Equal(100, Security.AccessLevel("admin"));
        Assert.Equal(70, Security.AccessLevel("security"));
        Assert.Equal(50, Security.AccessLevel("operator"));
        Assert.Equal(20, Security.AccessLevel("viewer"));
    }

    [Fact]
    public void RequiresAuditIncludesEscalation()
    {
        Assert.True(Security.RequiresAudit("escalation"));
        Assert.True(Security.RequiresAudit("delete"));
        Assert.False(Security.RequiresAudit("read"));
    }

    [Fact]
    public void SanitiseInputRemovesQuotes()
    {
        var result = Security.SanitiseInput("hello 'world' <script>");
        Assert.DoesNotContain("'", result);
        Assert.DoesNotContain("<", result);
    }

    [Fact]
    public void HashChainDeterministic()
    {
        var h1 = Security.HashChain(["a", "b", "c"]);
        var h2 = Security.HashChain(["a", "b", "c"]);
        var h3 = Security.HashChain(["ab", "c"]);
        Assert.Equal(h1, h2);
        Assert.NotEqual(h1, h3);
    }

    [Fact]
    public void DigestMultipleSorted()
    {
        var h1 = Security.DigestMultiple(["x", "y", "z"]);
        var h2 = Security.DigestMultiple(["z", "y", "x"]);
        Assert.Equal(h1, h2);
    }

    // === Resilience Tests ===

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

    [Fact]
    public void RetryBackoffExponential()
    {
        var delay0 = Resilience.RetryWithBackoff(0, 100);
        var delay1 = Resilience.RetryWithBackoff(1, 100);
        Assert.Equal(200, delay0);
        Assert.Equal(400, delay1);
    }

    [Fact]
    public void PartitionImpactRatio()
    {
        var impact = Resilience.PartitionImpact(3, 10);
        Assert.True(impact >= 0.2 && impact <= 0.4);
    }

    [Fact]
    public void HealthScoreAsDouble()
    {
        var score = Resilience.HealthScore(7, 3);
        Assert.True(score >= 0.6 && score <= 0.8);
    }

    [Fact]
    public void CheckpointAgePositive()
    {
        var cp = new Checkpoint("cp1", 5, 1000);
        var age = Resilience.CheckpointAge(cp, 1500);
        Assert.True(age > 0);
    }

    [Fact]
    public void FailoverPriorityExcludesDegraded()
    {
        var candidates = new List<string> { "nodeA", "nodeB", "nodeC" };
        var degraded = new HashSet<string> { "nodeB" };
        var result = Resilience.FailoverPriority(candidates, degraded);
        Assert.NotEqual("nodeB", result[0]);
    }

    [Fact]
    public void CircuitBreakerShouldTripAtThreshold()
    {
        Assert.True(Resilience.CircuitBreakerShouldTrip(5, 5));
        Assert.True(Resilience.CircuitBreakerShouldTrip(6, 5));
        Assert.False(Resilience.CircuitBreakerShouldTrip(4, 5));
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

    [Fact]
    public void WeightedMeanNormalization()
    {
        double[] values = [10.0, 20.0, 30.0];
        double[] weights = [0.2, 0.3, 0.5];
        var result = Statistics.WeightedMean(values, weights);
        Assert.True(Math.Abs(result - 23.0) < 0.01);
    }

    [Fact]
    public void HistogramBucketDistribution()
    {
        double[] values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0];
        var hist = Statistics.Histogram(values, 5);
        Assert.Equal(5, hist.Count);
        Assert.Equal(10, hist.Sum());
    }

    [Fact]
    public void CumulativeSumAccumulates()
    {
        double[] values = [1.0, 2.0, 3.0, 4.0];
        var cumsum = Statistics.CumulativeSum(values);
        Assert.Equal(4, cumsum.Count);
        Assert.Equal(1.0, cumsum[0]);
        Assert.Equal(3.0, cumsum[1]);
        Assert.Equal(6.0, cumsum[2]);
        Assert.Equal(10.0, cumsum[3]);
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

    [Fact]
    public void CompletionRateExcludesCancelled()
    {
        var engine = new WorkflowEngine();
        engine.Register("e1");
        engine.Register("e2");
        engine.Register("e3");
        engine.Transition("e1", "allocated", 100);
        engine.Transition("e1", "departed", 200);
        engine.Transition("e1", "arrived", 300);
        engine.Transition("e2", "cancelled", 100);
        var rate = WorkflowOps.CompletionRate(engine);
        Assert.True(Math.Abs(rate - 33.33) < 1.0);
    }

    [Fact]
    public void PendingCountExcludesTerminal()
    {
        var engine = new WorkflowEngine();
        engine.Register("e1");
        engine.Register("e2");
        engine.Transition("e1", "allocated", 100);
        engine.Transition("e1", "departed", 200);
        engine.Transition("e1", "arrived", 300);
        Assert.Equal(1, WorkflowOps.PendingCount(engine));
    }

    [Fact]
    public void WorkflowMetricsActiveCount()
    {
        var engine = new WorkflowEngine();
        engine.Register("e1");
        engine.Register("e2");
        engine.Transition("e1", "cancelled", 100);
        var (active, terminal, total) = WorkflowOps.WorkflowMetrics(engine);
        Assert.Equal(1, active);
        Assert.Equal(1, terminal);
        Assert.Equal(2, total);
    }

    [Fact]
    public void DeadlockDetectionSelfLoop()
    {
        var graph = new List<(string, string)> { ("A", "A") };
        Assert.True(WorkflowOps.DeadlockDetection(graph));
    }

    [Fact]
    public void EntityAgeUsesFirstTimestamp()
    {
        var history = new List<TransitionRecord>
        {
            new("e1", "queued", "allocated", 100),
            new("e1", "allocated", "departed", 200),
            new("e1", "departed", "arrived", 300),
        };
        var age = WorkflowOps.EntityAge(history, "e1", 500);
        Assert.Equal(400, age);
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

    [Fact]
    public void ServiceHealthSLO()
    {
        Assert.Equal("healthy", ServiceOps.ServiceHealth("gateway", 30, 50));
        Assert.Equal("degraded", ServiceOps.ServiceHealth("gateway", 70, 50));
    }

    [Fact]
    public void ServiceSLORoutingCorrect()
    {
        Assert.Equal(100, ServiceOps.ServiceSLO("routing"));
        Assert.Equal(50, ServiceOps.ServiceSLO("gateway"));
    }

    [Fact]
    public void ServiceUptimeAsPercentage()
    {
        var uptime = ServiceOps.ServiceUptime(90, 100);
        Assert.Equal(90.0, uptime);
    }

    [Fact]
    public void DependencyDepthRootIsZero()
    {
        var defs = ServiceRegistry.All();
        Assert.Equal(0, ServiceOps.DependencyDepth(defs, "gateway"));
        Assert.True(ServiceOps.DependencyDepth(defs, "analytics") >= 1);
    }

    // === Latent Bug Tests ===

    [Fact]
    public void LatestCheckpointReturnsHighestSequence()
    {
        var mgr = new CheckpointManager(10);
        mgr.Record(new Checkpoint("cp1", 5, 1000));
        mgr.Record(new Checkpoint("cp2", 15, 2000));
        mgr.Record(new Checkpoint("cp3", 10, 1500));
        var latest = mgr.LatestCheckpoint();
        Assert.NotNull(latest);
        Assert.Equal(15, latest!.Sequence);
    }

    [Fact]
    public void StateDistributionCountsCancelledAsTerminal()
    {
        var engine = new WorkflowEngine();
        engine.Register("e1");
        engine.Register("e2");
        engine.Transition("e1", "cancelled", 100);
        engine.Transition("e2", "allocated", 100);
        var dist = WorkflowOps.StateDistribution(engine);
        Assert.Equal(1, dist["terminal"]);
        Assert.Equal(1, dist["active"]);
    }

    // === Latent Bug Tests ===

    [Fact]
    public void CircuitBreakerRequiresFullSuccessStreakAfterReopen()
    {
        var cb = new CircuitBreaker(3, 3);
        cb.RecordFailure(); cb.RecordFailure(); cb.RecordFailure();
        Assert.Equal("open", cb.State);
        cb.AttemptReset();
        Assert.Equal("half_open", cb.State);
        cb.RecordSuccess(); cb.RecordSuccess();
        cb.RecordFailure();
        Assert.Equal("open", cb.State);
        cb.AttemptReset();
        Assert.Equal("half_open", cb.State);
        cb.RecordSuccess();
        Assert.Equal("half_open", cb.State);
    }

    // === Domain Logic Bug Tests ===

    [Fact]
    public void BerthOccupancyRateCapsAtOne()
    {
        var slots = new List<BerthSlot>
        {
            new("B1", 0, 10, true, "V1"),
            new("B1", 5, 15, true, "V2"),
        };
        var rate = Allocator.BerthOccupancyRate(slots, 15);
        Assert.True(rate <= 1.0);
    }

    [Fact]
    public void DemurrageChargeHazmatEscalatesAtHigherRate()
    {
        var charge = CargoOps.DemurrageCharge(10000, 5, true);
        Assert.Equal(70.0, charge);
    }

    [Fact]
    public void LoadSequenceOrdersByCargoWeight()
    {
        var manifests = new List<VesselManifest>
        {
            new("V1", "Feather Express", 5000, 800, false),
            new("V2", "Steel Hauler", 90000, 200, false),
            new("V3", "Mixed Cargo", 30000, 500, false),
        };
        var sequenced = CargoOps.LoadSequence(manifests);
        Assert.Equal("V2", sequenced[0].VesselId);
        Assert.Equal("V3", sequenced[1].VesselId);
        Assert.Equal("V1", sequenced[2].VesselId);
    }

    // === Multi-Step Bug Tests ===

    [Fact]
    public void ExponentialMovingAverageFirstValue()
    {
        var result = Statistics.ExponentialMovingAverage(new double[] { 10.0, 20.0, 30.0 }, 0.5);
        Assert.Equal(3, result.Count);
        Assert.Equal(10.0, result[0]);
    }

    [Fact]
    public void ExponentialMovingAverageWeightsRecent()
    {
        var result = Statistics.ExponentialMovingAverage(new double[] { 10.0, 20.0, 30.0 }, 0.8);
        Assert.True(result[2] > 25.0);
    }

    [Fact]
    public void SelectOptimalRoutesExcludesBlockedAndTakesBest()
    {
        var routes = new Route[]
        {
            new("alpha", 2),
            new("beta", 100),
            new("gamma", 5),
            new("delta", 3),
        };
        var blocked = new HashSet<string> { "beta" };
        var result = RouteSelection.SelectOptimalRoutes(routes, blocked, 2);
        Assert.Equal(2, result.Count);
        Assert.DoesNotContain(result, r => r.Channel == "beta");
        Assert.Equal("alpha", result[0].Channel);
        Assert.Equal("delta", result[1].Channel);
    }

    [Fact]
    public void RecoveryPlanIncludesExactSequence()
    {
        var checkpoints = new List<Checkpoint>
        {
            new("cp1", 5, 1000),
            new("cp2", 10, 2000),
            new("cp3", 15, 3000),
        };
        var plan = Resilience.RecoveryPlan(checkpoints, 10);
        Assert.Contains(plan, c => c.Sequence == 10);
    }

    // === State Machine Bug Tests ===

    [Fact]
    public void ForceTransitionUpdatesEntityState()
    {
        var engine = new WorkflowEngine();
        engine.Register("ship-1");
        var result = engine.ForceTransition("ship-1", "departed", 100);
        Assert.True(result.Success);
        Assert.Equal("departed", engine.GetState("ship-1"));
    }

    [Fact]
    public void StepwiseEscalateStopsAtTarget()
    {
        var engine = new PolicyEngine();
        engine.StepwiseEscalate("restricted");
        Assert.Equal("restricted", engine.Current);
        Assert.Equal(2, engine.History.Count);
    }

    [Fact]
    public void StepwiseEscalateRecordsEachTransition()
    {
        var engine = new PolicyEngine();
        engine.StepwiseEscalate("restricted");
        Assert.Equal("restricted", engine.Current);
        var history = engine.History;
        Assert.Equal(2, history.Count);
        Assert.Equal("normal", history[0].From);
        Assert.Equal("watch", history[0].To);
        Assert.Equal("watch", history[1].From);
        Assert.Equal("restricted", history[1].To);
    }

    // === Concurrency Bug Tests ===

    [Fact]
    public void EnqueueBatchMaintainsPriorityOrder()
    {
        var queue = new PriorityQueue(100);
        queue.Enqueue(new QueueItem("existing", 50));
        queue.EnqueueBatch(new List<QueueItem>
        {
            new("a", 30), new("b", 70), new("c", 10)
        });
        var first = queue.Dequeue();
        Assert.Equal(70, first!.Priority);
    }

    [Fact]
    public void GetOrAddPreservesExistingLatency()
    {
        var table = new RouteTable();
        table.Add(new Route("alpha", 10));
        var route = table.GetOrAdd("alpha", 999);
        Assert.Equal(10, route.Latency);
    }

    [Fact]
    public void SnapshotIsThreadSafe()
    {
        var tracker = new ResponseTimeTracker(10000);
        var errors = 0;

        Parallel.For(0, 100, i =>
        {
            for (var j = 0; j < 100; j++)
            {
                tracker.Record(i * 100 + j);
                try
                {
                    var snap = tracker.Snapshot();
                    _ = snap.Count;
                }
                catch
                {
                    Interlocked.Increment(ref errors);
                }
            }
        });

        Assert.Equal(0, errors);
    }

    [Fact]
    public void RecordBatchIsThreadSafe()
    {
        var tracker = new ResponseTimeTracker(10000);
        var errors = 0;

        Parallel.For(0, 50, i =>
        {
            try
            {
                tracker.RecordBatch(
                    Enumerable.Range(0, 100).Select(j => (double)(i * 100 + j)).ToList());
            }
            catch
            {
                Interlocked.Increment(ref errors);
            }
        });

        Assert.Equal(0, errors);
    }

    // === Integration Bug Tests ===

    [Fact]
    public void ProcessBatchUsesFailureBurstForPolicy()
    {
        var orders = OrderFactory.CreateBatch(new[] { "a", "b", "c", "d" }, 3, 60);
        var routes = new[] { new Route("alpha", 5) };
        var blocked = new HashSet<string>();
        var (planned, route, policy) = DispatchPipeline.ProcessBatch(
            orders, 1, routes, blocked, "normal", 1);
        Assert.Equal("normal", policy);
    }

    [Fact]
    public void EndToEndLatencyExcludesBlockedRoutes()
    {
        var orders = new List<DispatchOrder> { new("a", 5, 15), new("b", 3, 30) };
        var routes = new List<Route>
        {
            new("alpha", 5),
            new("beta", 100),
            new("gamma", 10),
        };
        var blocked = new HashSet<string> { "beta" };
        var latency = DispatchPipeline.EndToEndLatencyEstimate(orders, 2, routes, blocked);
        Assert.True(latency < 20.0);
    }

    [Fact]
    public void AggregateHealthTreatsMissingAsDegraded()
    {
        var defs = ServiceRegistry.All();
        var latencies = new Dictionary<string, int>
        {
            ["gateway"] = 30,
            ["routing"] = 100,
        };
        var result = ServiceOps.AggregateHealth(defs, latencies);
        Assert.Equal("critical", result);
    }
}
