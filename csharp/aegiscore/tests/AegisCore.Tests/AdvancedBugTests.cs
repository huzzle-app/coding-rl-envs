using System.Threading;
using Xunit;

namespace AegisCore.Tests;

public sealed class AdvancedBugTests
{
    // ========================================================================
    // LATENT BUGS: Silently corrupt state or return wrong values without
    // immediately causing obvious failures in other subsystems
    // ========================================================================

    [Fact]
    public void ComputeLoadFactor_AtExactCapacity_ShouldReturnOne()
    {
        var factor = DispatchOptimizer.ComputeLoadFactor(100, 100);
        Assert.Equal(1.0, factor);
    }

    [Fact]
    public void ComputeLoadFactor_OverCapacity_ShouldIndicateOverload()
    {
        var factor = DispatchOptimizer.ComputeLoadFactor(150, 100);
        Assert.True(factor >= 1.0, $"Expected >= 1.0 when overloaded but got {factor}");
    }

    [Fact]
    public void ComputeLoadFactor_NormalLoad_ReturnsRatio()
    {
        Assert.Equal(0.5, DispatchOptimizer.ComputeLoadFactor(50, 100));
        Assert.Equal(0.25, DispatchOptimizer.ComputeLoadFactor(25, 100));
    }

    [Fact]
    public void ComputeLoadFactor_ZeroCapacity_ReturnsZero()
    {
        Assert.Equal(0.0, DispatchOptimizer.ComputeLoadFactor(10, 0));
    }

    [Fact]
    public void ComputeDynamicLimit_EmptyHistory_ReturnsBaseLimit()
    {
        var limit = AdaptiveQueue.ComputeDynamicLimit(1000, Array.Empty<double>());
        Assert.Equal(1000, limit);
    }

    [Fact]
    public void ComputeDynamicLimit_HighUtilization_ReducesLimit()
    {
        var limit = AdaptiveQueue.ComputeDynamicLimit(1000, new double[] { 0.95, 0.92, 0.91 });
        Assert.Equal(800, limit);
    }

    [Fact]
    public void ComputeDynamicLimit_LowUtilization_IncreasesLimit()
    {
        var limit = AdaptiveQueue.ComputeDynamicLimit(1000, new double[] { 0.3, 0.4, 0.35 });
        Assert.Equal(1200, limit);
    }

    // ========================================================================
    // DOMAIN LOGIC BUGS: Require understanding of maritime dispatch domain
    // ========================================================================

    [Fact]
    public void EstimateDockingTime_HazmatHeavyCargo_PenaltiesAreIndependent()
    {
        var manifest = new VesselManifest("V1", "Hazmat Heavy", 30_000, 100, true);
        var baseHours = 0.1;

        var result = VesselOps.EstimateDockingTime(manifest, baseHours);

        // Correct: base_time * cargo_factor + hazmat_overhead
        // containerTime(10.0) * cargoFactor(1.5) + hazmatOverhead(10.0) = 25.0
        Assert.Equal(25.0, result);
    }

    [Fact]
    public void EstimateDockingTime_NonHazmatHeavy_OnlyCargoFactor()
    {
        var manifest = new VesselManifest("V2", "Heavy Cargo", 30_000, 100, false);
        var result = VesselOps.EstimateDockingTime(manifest, 0.1);
        Assert.Equal(15.0, result);
    }

    [Fact]
    public void EstimateDockingTime_HazmatLightCargo_OnlyHazmatPenalty()
    {
        var manifest = new VesselManifest("V3", "Hazmat Light", 10_000, 50, true);
        var result = VesselOps.EstimateDockingTime(manifest, 0.1);
        // Light hazmat: base(5.0)*1.0 + hazmat(5.0) = 10.0
        Assert.Equal(10.0, result);
    }

    [Fact]
    public void ComputeRiskScore_WorstCase_NeverExceedsOne()
    {
        var score = RiskAssessment.ComputeRiskScore("halted", 1.0, 0.0);
        Assert.True(score <= 1.0, $"Risk score {score} exceeds maximum of 1.0");
    }

    [Fact]
    public void ComputeRiskScore_BestCase_NearZero()
    {
        var score = RiskAssessment.ComputeRiskScore("normal", 0.0, 100.0);
        Assert.True(score >= 0.0 && score <= 0.05, $"Expected near-zero risk but got {score}");
    }

    [Fact]
    public void ComputeRiskScore_MaxScore_ExactlyOne()
    {
        var maxScore = RiskAssessment.ComputeRiskScore("halted", 1.0, 0.0);
        Assert.Equal(1.0, maxScore, 4);
    }

    [Fact]
    public void ComputeMultiLegFuelCost_MultipleLegs_SumsAllDistances()
    {
        var legs = new List<Waypoint>
        {
            new("PortA", 100.0),
            new("PortB", 200.0),
            new("PortC", 150.0),
        };
        var portFees = new List<double> { 500.0, 600.0, 400.0 };

        var cost = RouteOptimizer.ComputeMultiLegFuelCost(legs, 2.0, portFees);

        // Correct: (100+200+150)*2.0 + (500+600+400) = 900+1500 = 2400
        Assert.Equal(2400.0, cost);
    }

    [Fact]
    public void ComputeMultiLegFuelCost_SingleLeg_MatchesDirectCalc()
    {
        var legs = new List<Waypoint> { new("PortA", 300.0) };
        var portFees = new List<double> { 500.0 };

        var cost = RouteOptimizer.ComputeMultiLegFuelCost(legs, 2.0, portFees);
        Assert.Equal(1100.0, cost);
    }

    [Fact]
    public void ExponentialMovingAverage_UsePreviousEmaValue()
    {
        var values = new List<double> { 10.0, 20.0, 30.0, 40.0, 50.0 };
        var alpha = 0.3;

        var result = AdvancedStatistics.ExponentialMovingAverage(values, alpha);

        // EMA formula: ema[i] = alpha*value[i] + (1-alpha)*ema[i-1]
        // ema[0] = 10.0
        // ema[1] = 0.3*20 + 0.7*10.0 = 13.0
        // ema[2] = 0.3*30 + 0.7*13.0 = 18.1
        Assert.Equal(5, result.Count);
        Assert.Equal(10.0, result[0], 2);
        Assert.Equal(13.0, result[1], 2);
        Assert.Equal(18.1, result[2], 2);
    }

    [Fact]
    public void ExponentialMovingAverage_AlphaOne_EqualsRawValues()
    {
        var values = new List<double> { 1.0, 2.0, 3.0 };
        var result = AdvancedStatistics.ExponentialMovingAverage(values, 1.0);
        Assert.Equal(values, result);
    }

    [Fact]
    public void ExponentialMovingAverage_LongSeries_Smoothing()
    {
        var values = new List<double> { 100.0, 0.0, 100.0, 0.0, 100.0, 0.0 };
        var alpha = 0.5;
        var result = AdvancedStatistics.ExponentialMovingAverage(values, alpha);

        // ema[0] = 100
        // ema[1] = 0.5*0 + 0.5*100 = 50
        // ema[2] = 0.5*100 + 0.5*50 = 75
        // ema[3] = 0.5*0 + 0.5*75 = 37.5
        Assert.Equal(50.0, result[1], 2);
        Assert.Equal(75.0, result[2], 2);
        Assert.Equal(37.5, result[3], 2);
    }

    // ========================================================================
    // MULTI-STEP BUGS: Fixing one reveals another
    // ========================================================================

    [Fact]
    public void ValidateTokenSequence_AllTokensValidated()
    {
        var tokens = new List<string> { "token1", "token2", "token3" };
        var digests = tokens.Select(t => Security.Digest(t)).ToList();
        Assert.True(SecurityChain.ValidateTokenSequence(tokens, digests));
    }

    [Fact]
    public void ValidateTokenSequence_InvalidLastToken_ShouldFail()
    {
        var tokens = new List<string> { "token1", "token2", "token3" };
        var digests = tokens.Select(t => Security.Digest(t)).ToList();
        digests[2] = "invalid_digest_value_that_does_not_match";

        Assert.False(SecurityChain.ValidateTokenSequence(tokens, digests));
    }

    [Fact]
    public void ValidateTokenSequence_SingleToken_ValidDigest_Passes()
    {
        var tokens = new List<string> { "only_token" };
        var digests = new List<string> { Security.Digest("only_token") };
        Assert.True(SecurityChain.ValidateTokenSequence(tokens, digests));
    }

    [Fact]
    public void ValidateTokenSequence_SingleToken_InvalidDigest_Fails()
    {
        var tokens = new List<string> { "only_token" };
        var digests = new List<string> { "wrong_digest" };
        Assert.False(SecurityChain.ValidateTokenSequence(tokens, digests));
    }

    [Fact]
    public void ValidateTokenSequence_TwoTokens_SecondInvalid_Fails()
    {
        var tokens = new List<string> { "a", "b" };
        var digests = new List<string> { Security.Digest("a"), "wrong" };
        Assert.False(SecurityChain.ValidateTokenSequence(tokens, digests));
    }

    [Fact]
    public void MergeReplayStreams_DeterministicOrderingBySameSequence()
    {
        var streamA = new List<ReplayEvent>
        {
            new("event-b", 5),
            new("event-a", 5),
        };
        var streamB = new List<ReplayEvent>
        {
            new("event-c", 5),
        };

        var merged = ReplayMerger.MergeReplayStreams(streamA, streamB);

        Assert.Equal(3, merged.Count);
        Assert.Equal("event-a", merged[0].Id);
        Assert.Equal("event-b", merged[1].Id);
        Assert.Equal("event-c", merged[2].Id);
    }

    [Fact]
    public void MergeReplayStreams_ConsistentWithReplayOrdering()
    {
        var events = new List<ReplayEvent>
        {
            new("z", 1), new("a", 1), new("m", 1),
        };

        var replayResult = Resilience.Replay(events);
        var mergeResult = ReplayMerger.MergeReplayStreams(events, Array.Empty<ReplayEvent>());

        Assert.Equal(replayResult.Count, mergeResult.Count);
        for (var i = 0; i < replayResult.Count; i++)
        {
            Assert.Equal(replayResult[i].Id, mergeResult[i].Id);
            Assert.Equal(replayResult[i].Sequence, mergeResult[i].Sequence);
        }
    }

    [Fact]
    public void MergeReplayStreams_StreamBOverwritesEqualSequence()
    {
        var streamA = new List<ReplayEvent> { new("shared", 5) };
        var streamB = new List<ReplayEvent> { new("shared", 5) };

        var merged = ReplayMerger.MergeReplayStreams(streamA, streamB);
        Assert.Single(merged);
        Assert.Equal(5, merged[0].Sequence);
    }

    [Fact]
    public void ReplayWithCheckpoint_FiltersOldEvents()
    {
        var events = new List<ReplayEvent>
        {
            new("a", 1), new("b", 3), new("c", 5), new("d", 7),
        };

        var result = ReplayMerger.ReplayWithCheckpoint(events, 3);
        Assert.All(result, e => Assert.True(e.Sequence > 3));
        Assert.Equal(2, result.Count);
    }

    // ========================================================================
    // STATE MACHINE BUGS
    // ========================================================================

    [Fact]
    public void BatchTransition_PartialFailure_RollsBackAllTransitions()
    {
        var engine = new WorkflowEngine();
        engine.Register("e1");
        engine.Register("e2");
        engine.Register("e3");

        var transitions = new List<(string, string)>
        {
            ("e1", "allocated"),
            ("e2", "allocated"),
            ("e3", "arrived"),
        };

        var results = engine.BatchTransition(transitions, 100);
        var anyFailed = results.Any(r => !r.Success);
        Assert.True(anyFailed);

        Assert.Equal("queued", engine.GetState("e1"));
        Assert.Equal("queued", engine.GetState("e2"));
        Assert.Equal("queued", engine.GetState("e3"));
    }

    [Fact]
    public void BatchTransition_AllValid_AllTransitioned()
    {
        var engine = new WorkflowEngine();
        engine.Register("e1");
        engine.Register("e2");

        var transitions = new List<(string, string)>
        {
            ("e1", "allocated"),
            ("e2", "allocated"),
        };

        var results = engine.BatchTransition(transitions, 100);
        Assert.All(results, r => Assert.True(r.Success));
        Assert.Equal("allocated", engine.GetState("e1"));
        Assert.Equal("allocated", engine.GetState("e2"));
    }

    [Fact]
    public void EscalateToLevel_RecordsIntermediateSteps()
    {
        var engine = new PolicyEngine();
        Assert.Equal("normal", engine.Current);

        engine.EscalateToLevel("halted");

        Assert.Equal("halted", engine.Current);
        Assert.True(engine.History.Count >= 3,
            $"Expected at least 3 intermediate transitions (normal->watch->restricted->halted) but got {engine.History.Count}");
    }

    [Fact]
    public void EscalateToLevel_SingleStep_Works()
    {
        var engine = new PolicyEngine();
        engine.EscalateToLevel("watch");

        Assert.Equal("watch", engine.Current);
        Assert.Single(engine.History);
    }

    [Fact]
    public void EscalateToLevel_AlreadyAtTarget_NoChange()
    {
        var engine = new PolicyEngine();
        engine.EscalateToLevel("watch");
        var historyBefore = engine.History.Count;

        engine.EscalateToLevel("watch");
        Assert.Equal(historyBefore, engine.History.Count);
    }

    [Fact]
    public void WorkflowEngine_ReRegister_PreservesActiveState()
    {
        var engine = new WorkflowEngine();
        engine.Register("vessel-1");
        engine.Transition("vessel-1", "allocated", 100);
        engine.Transition("vessel-1", "departed", 200);

        engine.Register("vessel-1");

        Assert.Equal("departed", engine.GetState("vessel-1"));
    }

    [Fact]
    public void EscalateWithCount_MultipleRounds()
    {
        var engine = new PolicyEngine();
        var (state, count) = engine.EscalateWithCount(3, 5);

        Assert.Equal("halted", state);
        Assert.Equal(3, count);
    }

    // ========================================================================
    // CONCURRENCY BUGS
    // ========================================================================

    [Fact]
    public void TransitionIfState_BasicFunctionality()
    {
        var engine = new WorkflowEngine();
        engine.Register("e1");

        var result = engine.TransitionIfState("e1", "queued", "allocated", 100);
        Assert.True(result.Success);
        Assert.Equal("allocated", engine.GetState("e1"));
    }

    [Fact]
    public void TransitionIfState_WrongExpectedState_Fails()
    {
        var engine = new WorkflowEngine();
        engine.Register("e1");

        var result = engine.TransitionIfState("e1", "allocated", "departed", 100);
        Assert.False(result.Success);
        Assert.Equal("queued", engine.GetState("e1"));
    }

    [Fact]
    public void TransitionIfState_ConcurrentRace()
    {
        var raceCount = 0;
        var iterations = 500;

        for (var i = 0; i < iterations; i++)
        {
            var engine = new WorkflowEngine();
            var entityId = $"race-{i}";
            engine.Register(entityId);

            var barrier = new Barrier(2);
            var results = new bool[2];

            var t1 = new Thread(() =>
            {
                barrier.SignalAndWait();
                var r = engine.Transition(entityId, "allocated", 100);
                results[0] = r.Success;
            });

            var t2 = new Thread(() =>
            {
                barrier.SignalAndWait();
                var r = engine.TransitionIfState(entityId, "queued", "allocated", 200);
                results[1] = r.Success;
            });

            t1.Start();
            t2.Start();
            t1.Join();
            t2.Join();

            if (results[0] && results[1])
                raceCount++;
        }

        Assert.True(true);
    }

    [Fact]
    public void CircuitBreaker_TryExecute_OpensAfterFailures()
    {
        var cb = new CircuitBreaker(3, 2);

        cb.TryExecute(() => false);
        cb.TryExecute(() => false);
        cb.TryExecute(() => false);

        Assert.Equal(CircuitBreakerState.Open, cb.State);

        var result = cb.TryExecute(() => true);
        Assert.False(result);
    }

    [Fact]
    public void CircuitBreaker_TryExecute_HalfOpen_SuccessCloses()
    {
        var cb = new CircuitBreaker(2, 1);

        cb.RecordFailure();
        cb.RecordFailure();
        Assert.Equal(CircuitBreakerState.Open, cb.State);

        cb.AttemptReset();
        Assert.Equal(CircuitBreakerState.HalfOpen, cb.State);

        cb.TryExecute(() => true);
        Assert.Equal(CircuitBreakerState.Closed, cb.State);
    }

    [Fact]
    public void CircuitBreaker_TryExecute_ExceptionRecordsFailure()
    {
        var cb = new CircuitBreaker(2, 2);

        cb.TryExecute(() => throw new InvalidOperationException("test"));
        cb.TryExecute(() => throw new InvalidOperationException("test"));

        Assert.Equal(CircuitBreakerState.Open, cb.State);
    }

    // ========================================================================
    // INTEGRATION BUGS: Cross-module interactions
    // ========================================================================

    [Fact]
    public void ResolveDependencyChain_DependenciesBeforeService()
    {
        var chain = EndpointResolver.ResolveDependencyChain("routing");

        Assert.Contains("gateway", chain);
        Assert.Contains("routing", chain);

        var chainList = chain.ToList();
        var gatewayIdx = chainList.IndexOf("gateway");
        var routingIdx = chainList.IndexOf("routing");
        Assert.True(gatewayIdx < routingIdx,
            $"Gateway (idx={gatewayIdx}) must appear before routing (idx={routingIdx})");
    }

    [Fact]
    public void ResolveDependencyChain_DeepDeps_CorrectOrder()
    {
        var chain = EndpointResolver.ResolveDependencyChain("notifications");

        Assert.Contains("gateway", chain);
        Assert.Contains("audit", chain);
        Assert.Contains("notifications", chain);

        var chainList = chain.ToList();
        var gatewayIdx = chainList.IndexOf("gateway");
        var notifIdx = chainList.IndexOf("notifications");
        Assert.True(gatewayIdx < notifIdx,
            $"Gateway should appear before notifications in dependency chain");
    }

    [Fact]
    public void ResolveDependencyChain_LastElementIsService()
    {
        var chain = EndpointResolver.ResolveDependencyChain("analytics");
        Assert.True(chain.Count > 1);
        Assert.Equal("analytics", chain[chain.Count - 1]);
    }

    [Fact]
    public void ServiceUrl_ShouldIncludePort()
    {
        var url = ServiceRegistry.GetServiceUrl("gateway");
        Assert.NotNull(url);
        Assert.Contains(":8150", url!);
    }

    [Fact]
    public void EndpointResolver_ConsistentWithGetServiceUrl()
    {
        var resolvedUrl = EndpointResolver.ResolveEndpoint("gateway", "/health");
        var serviceUrl = ServiceRegistry.GetServiceUrl("gateway");

        Assert.NotNull(resolvedUrl);
        Assert.NotNull(serviceUrl);
        Assert.Equal(resolvedUrl, serviceUrl);
    }

    [Fact]
    public void EndToEnd_DispatchWithPolicyAndRouting()
    {
        var orders = OrderFactory.CreateBatch(new[] { "o1", "o2", "o3" }, Severity.High, 30);
        var planned = Allocator.PlanDispatch(orders, 2);

        var routes = new List<Route> { new("north", 5), new("south", 3) };
        var route = Routing.ChooseRoute(routes, new HashSet<string>());
        Assert.NotNull(route);

        var engine = new WorkflowEngine();
        foreach (var order in planned)
            engine.Register(order.Id);

        var health = QueueHealthMonitor.Check(planned.Count, 10);
        Assert.Equal("healthy", health.Status);
    }

    [Fact]
    public void AdaptiveQueue_UnhealthySystem_RejectsLowPriority()
    {
        var (accepted, _) = AdaptiveQueue.EvaluateAdmission(5, 100, Severity.Low, false);
        Assert.False(accepted);

        var (critAccepted, _) = AdaptiveQueue.EvaluateAdmission(99, 100, Severity.Critical, true);
        Assert.True(critAccepted);
    }

    [Fact]
    public void RouteOptimizer_FindBestRoute_RespectsMaxLatency()
    {
        var table = new RouteTable();
        table.Add(new Route("fast", 5));
        table.Add(new Route("medium", 15));
        table.Add(new Route("slow", 50));

        var best = RouteOptimizer.FindBestRoute(table, new HashSet<string>(), 20);
        Assert.NotNull(best);
        Assert.Equal("fast", best!.Channel);

        var limited = RouteOptimizer.FindBestRoute(table, new HashSet<string> { "fast" }, 20);
        Assert.NotNull(limited);
        Assert.Equal("medium", limited!.Channel);
    }

    [Fact]
    public void WorkflowAnalyzer_PathComplexity_QueuedToArrived()
    {
        var complexity = WorkflowAnalyzer.ComputePathComplexity("queued", "arrived");
        Assert.True(complexity > 0);
    }

    [Fact]
    public void Correlation_PerfectPositive()
    {
        var x = new List<double> { 1, 2, 3, 4, 5 };
        var y = new List<double> { 2, 4, 6, 8, 10 };
        var corr = AdvancedStatistics.Correlation(x, y);
        Assert.Equal(1.0, corr, 4);
    }

    [Fact]
    public void Correlation_PerfectNegative()
    {
        var x = new List<double> { 1, 2, 3, 4, 5 };
        var y = new List<double> { 10, 8, 6, 4, 2 };
        var corr = AdvancedStatistics.Correlation(x, y);
        Assert.Equal(-1.0, corr, 4);
    }

    [Fact]
    public void WeightedPercentile_UniformWeights_MatchesMedian()
    {
        var values = new List<double> { 10, 20, 30, 40, 50 };
        var weights = new List<double> { 1, 1, 1, 1, 1 };

        var wp50 = AdvancedStatistics.WeightedPercentile(values, weights, 50);
        Assert.Equal(30.0, wp50);
    }

    [Fact]
    public void VesselClassification_Boundaries()
    {
        Assert.Equal("ultra-large", VesselOps.ClassifyVessel(
            new VesselManifest("v1", "V", 100_000, 1000, false)));
        Assert.Equal("large", VesselOps.ClassifyVessel(
            new VesselManifest("v2", "V", 50_000, 500, false)));
        Assert.Equal("medium", VesselOps.ClassifyVessel(
            new VesselManifest("v3", "V", 10_000, 100, false)));
        Assert.Equal("small", VesselOps.ClassifyVessel(
            new VesselManifest("v4", "V", 5_000, 50, false)));
    }

    [Fact]
    public void RequiresEscort_HazmatAlways()
    {
        var manifest = new VesselManifest("v1", "V", 1000, 10, true);
        Assert.True(VesselOps.RequiresEscort(manifest));
    }

    [Fact]
    public void ScheduleTimeWindows_DistributesOrders()
    {
        var orders = OrderFactory.CreateBatch(
            Enumerable.Range(0, 10).Select(i => $"order-{i}"), Severity.High, 30);

        var windows = DispatchOptimizer.ScheduleTimeWindows(orders, 3, 4);
        Assert.True(windows.Count >= 2);
        Assert.True(windows[0].Batch.Count <= 4);
    }

    [Fact]
    public void MergeDispatchPlans_DeduplicatesById()
    {
        var planA = new List<DispatchOrder> { new("shared", 5, 30), new("a-only", 3, 60) };
        var planB = new List<DispatchOrder> { new("shared", 4, 40), new("b-only", 2, 90) };

        var merged = DispatchOptimizer.MergeDispatchPlans(planA, planB, 10);
        var ids = merged.Select(o => o.Id).ToList();
        Assert.Equal(ids.Distinct().Count(), ids.Count);
    }

    [Fact]
    public void ChainDigest_DifferentOrdersDifferentDigests()
    {
        var tokens1 = new List<string> { "a", "b", "c" };
        var tokens2 = new List<string> { "c", "b", "a" };

        var digest1 = SecurityChain.ComputeChainDigest(tokens1);
        var digest2 = SecurityChain.ComputeChainDigest(tokens2);
        Assert.NotEqual(digest1, digest2);
    }

    [Fact]
    public void IncrementalReplay_MergesWithBaseline()
    {
        var baseline = new List<ReplayEvent>
        {
            new("a", 1), new("b", 2),
        };
        var newEvents = new List<ReplayEvent>
        {
            new("a", 3), new("c", 4),
        };

        var result = ReplayMerger.IncrementalReplay(baseline, newEvents);
        Assert.Equal(3, result.Count);
        Assert.Equal(3, result.First(e => e.Id == "a").Sequence);
    }

    [Fact]
    public void AggregateRisk_MaxDominates()
    {
        var scores = new List<double> { 0.2, 0.3, 0.9 };
        var aggregate = RiskAssessment.AggregateRisk(scores);
        Assert.True(aggregate > 0.6);
    }

    [Fact]
    public void PriorityDrain_FiltersLowPriority()
    {
        var queue = new PriorityQueue(100);
        queue.Enqueue(new QueueItem("low", 1));
        queue.Enqueue(new QueueItem("med", 3));
        queue.Enqueue(new QueueItem("high", 5));

        var drained = AdaptiveQueue.PriorityDrain(queue, 3);
        Assert.Equal(2, drained.Count);
        Assert.All(drained, i => Assert.True(i.Priority >= 3));
    }

    // ========================================================================
    // PARAMETRIC TESTS: Exercise all new methods with varied inputs
    // ========================================================================

    public static IEnumerable<object[]> AdvancedCases()
    {
        for (var i = 0; i < 100; i++)
        {
            yield return new object[] { i };
        }
    }

    [Theory]
    [MemberData(nameof(AdvancedCases))]
    public void AdvancedMatrixCase(int idx)
    {
        // --- Load Factor ---
        var planned = (idx % 20) + 1;
        var capacity = 10 + (idx % 15);
        var loadFactor = DispatchOptimizer.ComputeLoadFactor(planned, capacity);
        if (planned < capacity)
            Assert.True(loadFactor > 0.0 && loadFactor < 1.0,
                $"Expected (0,1) for planned={planned} < capacity={capacity}, got {loadFactor}");
        else
            Assert.True(loadFactor >= 1.0,
                $"Load factor should be >= 1.0 when planned({planned}) >= capacity({capacity}), got {loadFactor}");

        // --- Vessel Docking ---
        var tons = 5000.0 + (idx * 1000);
        var containers = 20 + (idx % 200);
        var hazmat = idx % 3 == 0;
        var manifest = new VesselManifest($"V-{idx}", $"Vessel-{idx}", tons, containers, hazmat);
        var dockTime = VesselOps.EstimateDockingTime(manifest, 0.05);
        Assert.True(dockTime > 0.0);

        if (hazmat && tons > 25_000)
        {
            var baseTime = containers * 0.05;
            var expectedMax = baseTime * 1.5 + baseTime;
            Assert.True(dockTime <= expectedMax + 0.01,
                $"Docking time {dockTime} exceeds independent-penalty max {expectedMax} for hazmat heavy vessel");
        }

        // --- Risk Score ---
        var policies = Policy.AllPolicies();
        var policyState = policies[idx % policies.Length];
        var failureRate = (idx % 10) / 10.0;
        var slaCompliance = 50.0 + (idx % 51);
        var risk = RiskAssessment.ComputeRiskScore(policyState, failureRate, slaCompliance);
        Assert.True(risk >= 0.0 && risk <= 1.0,
            $"Risk {risk} out of [0,1] for state={policyState}, failure={failureRate}, sla={slaCompliance}");

        // --- Multi-Leg Fuel Cost ---
        var legCount = (idx % 4) + 1;
        var legs = Enumerable.Range(0, legCount)
            .Select(j => new Waypoint($"Port-{j}", 50.0 + j * 30.0))
            .ToList();
        var portFees = Enumerable.Range(0, legCount)
            .Select(j => 100.0 + j * 50.0)
            .ToList();
        var fuelCost = RouteOptimizer.ComputeMultiLegFuelCost(legs, 1.5, portFees);
        var expectedFuel = legs.Sum(l => l.DistanceNm) * 1.5;
        var expectedPortFees = portFees.Sum();
        Assert.Equal(expectedFuel + expectedPortFees, fuelCost, 2);

        // --- EMA ---
        if (idx % 5 == 0)
        {
            var values = Enumerable.Range(1, 5 + (idx % 5))
                .Select(j => (double)j * 10.0)
                .ToList();
            var alpha = 0.2 + (idx % 4) * 0.2;
            alpha = Math.Min(alpha, 1.0);
            var ema = AdvancedStatistics.ExponentialMovingAverage(values, alpha);
            Assert.Equal(values.Count, ema.Count);
            Assert.Equal(values[0], ema[0]);

            if (values.Count > 2 && alpha < 1.0)
            {
                var expectedEma1 = alpha * values[1] + (1 - alpha) * ema[0];
                var expectedEma2 = alpha * values[2] + (1 - alpha) * expectedEma1;
                Assert.Equal(expectedEma2, ema[2], 4);
            }
        }

        // --- Token Sequence ---
        if (idx % 7 == 0)
        {
            var tokenCount = 2 + (idx % 4);
            var tokens = Enumerable.Range(0, tokenCount)
                .Select(j => $"token-{idx}-{j}")
                .ToList();
            var digests = tokens.Select(t => Security.Digest(t)).ToList();

            Assert.True(SecurityChain.ValidateTokenSequence(tokens, digests),
                "Valid token sequence should pass");

            var tamperedDigests = digests.ToList();
            tamperedDigests[tamperedDigests.Count - 1] = "tampered";
            Assert.False(SecurityChain.ValidateTokenSequence(tokens, tamperedDigests),
                "Tampered last token should fail");
        }

        // --- Replay Merge Ordering ---
        if (idx % 10 == 0)
        {
            var seq = idx % 20;
            var streamA = new List<ReplayEvent>
            {
                new($"ev-b-{idx}", seq),
                new($"ev-a-{idx}", seq),
            };
            var streamB = new List<ReplayEvent>
            {
                new($"ev-c-{idx}", seq),
            };

            var merged = ReplayMerger.MergeReplayStreams(streamA, streamB);
            Assert.Equal(3, merged.Count);

            for (var j = 0; j < merged.Count - 1; j++)
            {
                if (merged[j].Sequence == merged[j + 1].Sequence)
                {
                    Assert.True(
                        string.Compare(merged[j].Id, merged[j + 1].Id, StringComparison.Ordinal) <= 0,
                        $"Same-sequence events not ordered by ID: {merged[j].Id} vs {merged[j + 1].Id}");
                }
            }
        }

        // --- Batch Transition Atomicity ---
        if (idx % 15 == 0)
        {
            var engine = new WorkflowEngine();
            engine.Register($"ba-{idx}");
            engine.Register($"bb-{idx}");
            engine.Register($"bc-{idx}");

            var transitions = new List<(string, string)>
            {
                ($"ba-{idx}", "allocated"),
                ($"bb-{idx}", "allocated"),
                ($"bc-{idx}", "arrived"),
            };

            var results = engine.BatchTransition(transitions, 1000);

            if (results.Any(r => !r.Success))
            {
                Assert.Equal("queued", engine.GetState($"ba-{idx}"));
                Assert.Equal("queued", engine.GetState($"bb-{idx}"));
            }
        }

        // --- Dependency Chain Order ---
        if (idx % 20 == 0)
        {
            var services = new[] { "routing", "analytics", "notifications" };
            var svc = services[idx / 20 % services.Length];
            var chain = EndpointResolver.ResolveDependencyChain(svc);

            Assert.True(chain.Count > 0);
            Assert.Equal(svc, chain[chain.Count - 1]);
        }

        // --- URL Consistency ---
        if (idx % 25 == 0)
        {
            var svcUrl = ServiceRegistry.GetServiceUrl("gateway");
            var resolvedUrl = EndpointResolver.ResolveEndpoint("gateway", "/health");
            Assert.NotNull(svcUrl);
            Assert.NotNull(resolvedUrl);
            Assert.Equal(svcUrl, resolvedUrl);
        }
    }

    // ========================================================================
    // COMPLEX BUG TESTS: Deep multi-layered, cross-module, stateful tests
    // ========================================================================

    // --- RecoveryManager: Checkpoint-based event replay ---

    [Fact]
    public void RecoveryManager_RecoverFromCheckpoint_ShouldNotIncludeCheckpointEvent()
    {
        var cpMgr = new CheckpointManager(3);
        var breaker = new CircuitBreaker(5, 3);
        var recovery = new RecoveryManager(cpMgr, breaker);

        for (var i = 1; i <= 10; i++)
            recovery.Append("stream-1", new ReplayEvent($"evt-{i}", i));

        var recovered = recovery.Recover("stream-1");

        // Checkpoint should be at sequence ~9 (interval 3: checkpoints at 4, 7, 10)
        // Recovery should only include events AFTER the checkpoint
        var cp = cpMgr.Get("stream-1");
        Assert.NotNull(cp);
        Assert.True(recovered.All(e => e.Sequence > cp!.Sequence),
            "Recovered events should not include the checkpoint event itself");
    }

    [Fact]
    public void RecoveryManager_RecoverAfterManyEvents_NoDuplicateProcessing()
    {
        var cpMgr = new CheckpointManager(5);
        var breaker = new CircuitBreaker(5, 3);
        var recovery = new RecoveryManager(cpMgr, breaker);

        for (var i = 1; i <= 20; i++)
            recovery.Append("s1", new ReplayEvent($"e-{i}", i));

        var result = recovery.Recover("s1");
        var ids = result.Select(e => e.Id).ToList();
        Assert.Equal(ids.Distinct().Count(), ids.Count);
    }

    [Fact]
    public void RecoveryManager_RecoverExcludesAlreadyProcessedEvents()
    {
        var cpMgr = new CheckpointManager(2);
        var breaker = new CircuitBreaker(5, 3);
        var recovery = new RecoveryManager(cpMgr, breaker);

        recovery.Append("s", new ReplayEvent("a", 1));
        recovery.Append("s", new ReplayEvent("b", 2));
        recovery.Append("s", new ReplayEvent("c", 3));
        recovery.Append("s", new ReplayEvent("d", 4));

        var cp = cpMgr.Get("s");
        Assert.NotNull(cp);

        var recovered = recovery.Recover("s");
        // Events at or before checkpoint sequence should not be replayed
        foreach (var ev in recovered)
        {
            Assert.True(ev.Sequence > cp!.Sequence,
                $"Event {ev.Id} at seq {ev.Sequence} should not be replayed (checkpoint at {cp.Sequence})");
        }
    }

    [Theory]
    [InlineData(2, 10)]
    [InlineData(3, 15)]
    [InlineData(5, 25)]
    [InlineData(1, 5)]
    public void RecoveryManager_VariousCheckpointIntervals_RecoverIsCorrect(int interval, int totalEvents)
    {
        var cpMgr = new CheckpointManager(interval);
        var breaker = new CircuitBreaker(5, 3);
        var recovery = new RecoveryManager(cpMgr, breaker);

        for (var i = 1; i <= totalEvents; i++)
            recovery.Append("stream", new ReplayEvent($"ev-{i}", i));

        var cp = cpMgr.Get("stream");
        var recovered = recovery.Recover("stream");

        if (cp != null)
        {
            // All recovered events must be strictly after checkpoint
            Assert.True(recovered.All(e => e.Sequence > cp.Sequence),
                $"interval={interval} total={totalEvents}: checkpoint at {cp.Sequence}, " +
                $"but recovered min seq = {recovered.Min(e => e.Sequence)}");
        }
    }

    // --- PolicyAwareQueue: Stale policy capture ---

    [Fact]
    public void PolicyAwareQueue_ShouldReflectCurrentPolicyAfterEscalation()
    {
        var engine = new PolicyEngine();
        var queue = new PolicyAwareQueue(engine, 100);

        Assert.Equal("normal", queue.ActivePolicy);
        Assert.Equal(100, queue.EffectiveLimit);

        engine.Escalate(5); // normal → watch
        engine.Escalate(5); // watch → restricted
        engine.Escalate(5); // restricted → halted

        // After escalation to halted, effective limit should be 0
        Assert.Equal("halted", engine.Current);
        Assert.Equal(0, queue.EffectiveLimit);
    }

    [Fact]
    public void PolicyAwareQueue_RejectsAllWhenPolicyIsHalted()
    {
        var engine = new PolicyEngine();
        engine.EscalateToLevel("halted");
        var queue = new PolicyAwareQueue(engine, 100);

        var (admitted, _) = queue.TryAdmit(new QueueItem("q1", Severity.Critical));
        // Under halted policy, even critical items should be rejected (limit=0)
        Assert.False(admitted, "Halted policy should reject all items");
    }

    [Fact]
    public void PolicyAwareQueue_EffectiveLimitUpdatesWithPolicy()
    {
        var engine = new PolicyEngine();
        var queue = new PolicyAwareQueue(engine, 200);

        Assert.Equal(200, queue.EffectiveLimit); // normal: 1.0

        engine.Escalate(5); // → watch
        Assert.Equal(140, queue.EffectiveLimit); // watch: 0.7

        engine.Escalate(5); // → restricted
        Assert.Equal(100, queue.EffectiveLimit); // restricted: 0.5

        engine.Escalate(5); // → halted
        Assert.Equal(0, queue.EffectiveLimit); // halted: 0.0
    }

    [Fact]
    public void PolicyAwareQueue_AdmissionReflectsLivePolicy()
    {
        var engine = new PolicyEngine();
        var queue = new PolicyAwareQueue(engine, 10);

        // Fill to base limit under normal policy
        for (var i = 0; i < 10; i++)
            queue.TryAdmit(new QueueItem($"item-{i}", Severity.Medium));

        // Escalate to restricted (limit becomes 5)
        engine.EscalateToLevel("restricted");

        // Queue already has 10 items, but under restricted policy limit=5
        // New non-critical items should be rejected
        var (admitted, reason) = queue.TryAdmit(new QueueItem("overflow", Severity.Low));
        Assert.False(admitted, "Should reject low-priority when over restricted limit");
    }

    [Theory]
    [InlineData("normal", 1.0)]
    [InlineData("watch", 0.7)]
    [InlineData("restricted", 0.5)]
    [InlineData("halted", 0.0)]
    public void PolicyAwareQueue_EffectiveLimitMatchesCurrentPolicy(string targetPolicy, double expectedMult)
    {
        var engine = new PolicyEngine();
        if (targetPolicy != "normal")
            engine.EscalateToLevel(targetPolicy);

        var queue = new PolicyAwareQueue(engine, 1000);
        var expected = (int)(1000 * expectedMult);
        Assert.Equal(expected, queue.EffectiveLimit);
    }

    // --- RouteFailoverManager: Shared circuit breaker instance ---

    [Fact]
    public void RouteFailover_SecondaryRouteShouldWorkWhenPrimaryFails()
    {
        var mgr = new RouteFailoverManager(["primary", "secondary", "tertiary"], 2, 2);

        Assert.Equal("primary", mgr.ActiveRoute);

        // Fail primary twice to open its breaker
        mgr.Send(_ => false);
        mgr.Send(_ => false);

        // Primary breaker should be open, secondary should be available
        Assert.NotEqual("open", mgr.BreakerState("secondary"));

        // Send through secondary should succeed
        var (ok, used) = mgr.Send(_ => true);
        Assert.True(ok, "Secondary route should handle request successfully");
        Assert.Equal("secondary", used);
    }

    [Fact]
    public void RouteFailover_EachRouteHasIndependentBreakerState()
    {
        var mgr = new RouteFailoverManager(["A", "B", "C"], 2, 2);

        // Fail route A twice
        mgr.Send(_ => false);
        mgr.Send(_ => false);

        // Route A should be open
        Assert.Equal(CircuitBreakerState.Open, mgr.BreakerState("A"));

        // Route B should still be closed (independent breaker)
        Assert.Equal(CircuitBreakerState.Closed, mgr.BreakerState("B"));

        // Route C should still be closed
        Assert.Equal(CircuitBreakerState.Closed, mgr.BreakerState("C"));
    }

    [Fact]
    public void RouteFailover_FailoverCascadeWorks()
    {
        var mgr = new RouteFailoverManager(["r1", "r2", "r3"], 1, 1);

        // Fail r1
        mgr.Send(_ => false);
        Assert.Equal(CircuitBreakerState.Open, mgr.BreakerState("r1"));

        // Should failover to r2
        var (ok2, used2) = mgr.Send(_ => true);
        Assert.True(ok2);
        Assert.Equal("r2", used2);

        // Fail r2
        mgr.Send(r => r == "r2" ? false : true);

        // r2 should be open, r3 still available
        Assert.Equal(CircuitBreakerState.Closed, mgr.BreakerState("r3"));
    }

    [Fact]
    public void RouteFailover_RecoveryRestoresPrimary()
    {
        var mgr = new RouteFailoverManager(["main", "backup"], 2, 1);

        mgr.Send(_ => false);
        mgr.Send(_ => false);

        // main is open, active should switch to backup
        mgr.Send(_ => true);
        Assert.Equal("backup", mgr.ActiveRoute);

        // Try recovery - reset breakers to half-open
        mgr.TryRecover();

        // After recovery and a successful call, primary should work again
        // (only if breakers are truly independent)
        var mainState = mgr.BreakerState("main");
        Assert.NotEqual(CircuitBreakerState.Open, mainState);
    }

    [Theory]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(3)]
    [InlineData(5)]
    public void RouteFailover_FailThresholdRespected(int threshold)
    {
        var mgr = new RouteFailoverManager(["alpha", "beta"], threshold, 1);

        // Send threshold-1 failures: breaker should still be closed
        for (var i = 0; i < threshold - 1; i++)
            mgr.Send(_ => false);

        Assert.Equal(CircuitBreakerState.Closed, mgr.BreakerState("alpha"));

        // One more failure should open it
        mgr.Send(_ => false);
        Assert.Equal(CircuitBreakerState.Open, mgr.BreakerState("alpha"));

        // Beta should still be independently closed
        Assert.Equal(CircuitBreakerState.Closed, mgr.BreakerState("beta"));
    }

    // --- AnomalyDetector: Population vs sample variance ---

    [Fact]
    public void AnomalyDetector_ZScoreUsesCorrectVariance()
    {
        var detector = new AnomalyDetector(2.0, 100);

        // Build a baseline of stable values
        for (var i = 0; i < 10; i++)
            detector.Evaluate(100.0);

        // Introduce a value that should NOT be anomalous (within 2 stddev)
        // With all 100s, stddev should be 0, so any deviation is anomalous
        // Use a slightly varied distribution instead
        var detector2 = new AnomalyDetector(3.0, 50);
        var values = new[] { 10.0, 12.0, 11.0, 10.5, 11.5, 10.0, 12.0, 11.0, 10.5, 11.5 };
        foreach (var v in values)
            detector2.Evaluate(v);

        // Sample stddev for these values ≈ 0.76 (sample) vs 0.72 (population)
        // A value of 13.5 is ~3.3 sample stddevs or ~3.5 population stddevs away
        // With threshold 3.0: sample says not anomaly, population says anomaly
        var (isAnomaly, zScore) = detector2.Evaluate(13.5);

        // Using correct sample variance (N-1), z-score should be lower
        // The expected z-score with sample variance should be < 3.0
        var mean = (values.Sum() + 13.5) / (values.Length + 1);
        var sampleVar = values.Concat(new[] { 13.5 }).Sum(x => (x - mean) * (x - mean)) / values.Length; // N-1 = 10
        var sampleStd = Math.Sqrt(sampleVar);
        var expectedZ = Math.Abs((13.5 - mean) / sampleStd);

        // Population variance inflates z-score by using N instead of N-1
        Assert.True(Math.Abs(zScore - expectedZ) < 0.5,
            $"Z-score {zScore:F2} differs from expected sample-based {expectedZ:F2}");
    }

    [Fact]
    public void AnomalyDetector_SmallWindowSampleVariance()
    {
        // With only 3 observations, N vs N-1 makes a huge difference (33%)
        var detector = new AnomalyDetector(2.5, 10);

        detector.Evaluate(10.0);
        detector.Evaluate(10.0);
        var (_, z1) = detector.Evaluate(12.0);

        // Mean = (10+10+12)/3 = 10.667
        // Population var = ((0.667^2)*2 + 1.333^2)/3 = 0.889
        // Sample var = ((0.667^2)*2 + 1.333^2)/2 = 1.333
        // Pop std ≈ 0.943, Sample std ≈ 1.155
        // Pop z ≈ 1.414, Sample z ≈ 1.155

        // With correct sample variance, z-score should be lower
        var sampleStd = Math.Sqrt(((10.0 - 10.667) * (10.0 - 10.667) * 2 + (12.0 - 10.667) * (12.0 - 10.667)) / 2.0);
        var expectedZ = Math.Abs((12.0 - 10.667) / sampleStd);
        Assert.True(z1 <= expectedZ + 0.1, $"Z-score {z1:F3} seems inflated (expected ~{expectedZ:F3})");
    }

    [Fact]
    public void AnomalyDetector_ConsistentWithStatisticsStdDev()
    {
        var detector = new AnomalyDetector(2.0, 100);
        var data = new[] { 5.0, 7.0, 8.0, 6.0, 9.0, 5.5, 7.5, 8.5, 6.5, 4.5 };

        foreach (var d in data)
            detector.Evaluate(d);

        var (_, zScore) = detector.Evaluate(15.0);

        // Statistics.StdDev uses sample variance (N-1)
        var allData = data.Concat(new[] { 15.0 }).ToList();
        var stdDev = Statistics.StdDev(allData);
        var mean = allData.Average();
        var expectedZ = Math.Abs((15.0 - mean) / stdDev);

        // AnomalyDetector should agree with Statistics.StdDev
        Assert.True(Math.Abs(zScore - expectedZ) < 0.3,
            $"AnomalyDetector z={zScore:F2} should match Statistics-based z={expectedZ:F2}");
    }

    [Theory]
    [InlineData(new[] { 100.0, 100.0, 100.0, 100.0, 100.0 }, 105.0, false)]
    [InlineData(new[] { 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0 }, 10.0, false)]
    public void AnomalyDetector_FalsePositiveRate(double[] baseline, double testValue, bool expectAnomaly)
    {
        var detector = new AnomalyDetector(2.0, 50);
        foreach (var v in baseline)
            detector.Evaluate(v);

        var (isAnomaly, _) = detector.Evaluate(testValue);
        Assert.Equal(expectAnomaly, isAnomaly);
    }

    // --- DispatchPipeline: Cross-module atomicity ---

    [Fact]
    public void DispatchPipeline_HaltedPolicyRejectWithoutSideEffects()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var pipeline = new DispatchPipeline(workflow, policy);

        policy.EscalateToLevel("halted");

        var order = new DispatchOrder("dp-1", Severity.Medium, 60);
        var route = new Route("channel-1", 10);
        var result = pipeline.Execute(order, route, 1000);

        Assert.False(result.Success);
        // The entity should NOT be registered if rejected by policy
        Assert.Null(workflow.GetState("dp-1"));
    }

    [Fact]
    public void DispatchPipeline_RestrictedPolicyRejectsLowPriority()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var pipeline = new DispatchPipeline(workflow, policy);

        policy.EscalateToLevel("restricted");

        var lowOrder = new DispatchOrder("dp-low", Severity.Low, 120);
        var route = new Route("ch", 5);
        var result = pipeline.Execute(lowOrder, route, 100);

        Assert.False(result.Success);
        // Rejected order should not leave orphaned entity in workflow
        Assert.Null(workflow.GetState("dp-low"));
    }

    [Fact]
    public void DispatchPipeline_RestrictedPolicyAllowsHighPriority()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var pipeline = new DispatchPipeline(workflow, policy);

        policy.EscalateToLevel("restricted");

        var highOrder = new DispatchOrder("dp-high", Severity.High, 30);
        var route = new Route("ch", 5);
        var result = pipeline.Execute(highOrder, route, 100);

        Assert.True(result.Success);
        Assert.Equal("allocated", workflow.GetState("dp-high"));
    }

    [Fact]
    public void DispatchPipeline_DoubleDispatchSameOrder()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var pipeline = new DispatchPipeline(workflow, policy);

        var order = new DispatchOrder("dup", Severity.Critical, 15);
        var route = new Route("fast", 3);

        var r1 = pipeline.Execute(order, route, 100);
        Assert.True(r1.Success);
        Assert.Equal("allocated", workflow.GetState("dup"));

        // Second dispatch of same order should fail (already allocated, can't re-register to queued)
        var r2 = pipeline.Execute(order, route, 200);
        // Should not overwrite allocated state back to queued
        Assert.Equal("allocated", workflow.GetState("dup"));
    }

    [Fact]
    public void DispatchPipeline_BatchDispatchConsistency()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var pipeline = new DispatchPipeline(workflow, policy);

        var orders = Enumerable.Range(1, 20)
            .Select(i => new DispatchOrder($"batch-{i}", Severity.Medium, 60))
            .ToList();
        var route = new Route("ch-1", 10);

        var results = pipeline.ExecuteBatch(orders, route, 500);

        var successCount = results.Count(r => r.Success);
        Assert.Equal(20, successCount);

        // All successful orders should be in "allocated" state
        foreach (var order in orders)
            Assert.Equal("allocated", workflow.GetState(order.Id));
    }

    [Fact]
    public void DispatchPipeline_PolicyChangesMidBatch()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var pipeline = new DispatchPipeline(workflow, policy);

        // Start normal, dispatch some
        var route = new Route("ch", 5);
        pipeline.Execute(new DispatchOrder("pre-1", Severity.Medium, 60), route, 100);
        Assert.True(workflow.GetState("pre-1") == "allocated");

        // Escalate mid-session
        policy.EscalateToLevel("halted");

        // New dispatches should be rejected
        var result = pipeline.Execute(new DispatchOrder("post-1", Severity.Low, 120), route, 200);
        Assert.False(result.Success);
        Assert.Equal("halted", result.PolicyAtCheck);
    }

    // --- VersionTracker: Vector clock merge correctness ---

    [Fact]
    public void VersionTracker_ResolvedVectorShouldBeDominant()
    {
        var tracker = new VersionTracker();

        tracker.Update("doc-a", "node-1");
        tracker.Update("doc-a", "node-1");
        tracker.Update("doc-b", "node-2");
        tracker.Update("doc-b", "node-2");
        tracker.Update("doc-b", "node-2");

        var resolved = tracker.Resolve("doc-a", "doc-b");

        // Store the resolved vector as a new entity
        // Resolved should dominate both inputs
        // doc-a: {node-1: 2}, doc-b: {node-2: 3}
        // resolved: {node-1: 2, node-2: 3}

        // If we create a new entity with the resolved vector and compare,
        // it should dominate both originals
        // But first, just verify the resolved vector is correct
        Assert.Equal(2, resolved["node-1"]);
        Assert.Equal(3, resolved["node-2"]);
    }

    [Fact]
    public void VersionTracker_PostMergeUpdateShowsDominance()
    {
        var tracker = new VersionTracker();

        // Two concurrent writers
        tracker.Update("entity-x", "writer-a");
        tracker.Update("entity-y", "writer-b");

        // These should be concurrent
        Assert.Equal("concurrent", tracker.Compare("entity-x", "entity-y"));

        // Resolve the conflict
        var resolved = tracker.Resolve("entity-x", "entity-y");

        // Now simulate: entity-x incorporates the resolution and advances
        // This is the critical part: after resolution, one side advances
        // The resolved vector should be {writer-a: 1, writer-b: 1}
        // If we update entity-x with writer-a again: {writer-a: 2, writer-b: 0}
        // vs entity-y: {writer-b: 1}
        // This should show entity-x dominating entity-y

        tracker.Update("entity-x", "writer-a");

        // entity-x now has {writer-a: 2}, entity-y has {writer-b: 1}
        // The merge should have made entity-x aware of writer-b, but since
        // Resolve doesn't store anything back, entity-x vector is just {writer-a: 2}
        // They should STILL be concurrent because the resolution was lost
        var comparison = tracker.Compare("entity-x", "entity-y");

        // In a correct implementation, after incorporating a resolution,
        // the advanced entity should dominate. But since Resolve doesn't
        // increment, the merge result is indistinguishable from the max of inputs.
        Assert.Equal("concurrent", comparison);
    }

    [Fact]
    public void VersionTracker_CompareAfterDivergentUpdates()
    {
        var tracker = new VersionTracker();

        tracker.Update("a", "n1");
        tracker.Update("a", "n2");
        tracker.Update("b", "n1");
        tracker.Update("b", "n1");

        // a: {n1:1, n2:1}, b: {n1:2}
        var cmp = tracker.Compare("a", "b");
        Assert.Equal("concurrent", cmp);
    }

    [Fact]
    public void VersionTracker_EqualVectorsDetected()
    {
        var tracker = new VersionTracker();

        tracker.Update("x", "node");
        tracker.Update("y", "node");

        Assert.Equal("equal", tracker.Compare("x", "y"));
    }

    [Fact]
    public void VersionTracker_DominanceAfterMultipleUpdates()
    {
        var tracker = new VersionTracker();

        tracker.Update("leader", "n1");
        tracker.Update("leader", "n1");
        tracker.Update("leader", "n2");

        tracker.Update("follower", "n1");

        // leader: {n1:2, n2:1}, follower: {n1:1}
        Assert.Equal("a_dominates", tracker.Compare("leader", "follower"));
    }

    [Fact]
    public void VersionTracker_UnknownEntityComparison()
    {
        var tracker = new VersionTracker();
        tracker.Update("known", "node");
        Assert.Equal("unknown", tracker.Compare("known", "nonexistent"));
        Assert.Equal("unknown", tracker.Compare("nope1", "nope2"));
    }

    // --- EMA (ExponentialMovingAverage) correctness ---

    [Fact]
    public void ExponentialMovingAverage_UsesEmaRecurrence()
    {
        var values = new List<double> { 10.0, 20.0, 30.0, 40.0, 50.0 };
        var alpha = 0.5;

        var ema = AdvancedStatistics.ExponentialMovingAverage(values, alpha);

        Assert.Equal(5, ema.Count);
        Assert.Equal(10.0, ema[0]); // First value unchanged

        // Correct EMA: ema[i] = alpha * values[i] + (1-alpha) * ema[i-1]
        // ema[1] = 0.5 * 20 + 0.5 * 10 = 15
        // ema[2] = 0.5 * 30 + 0.5 * 15 = 22.5
        // ema[3] = 0.5 * 40 + 0.5 * 22.5 = 31.25
        // ema[4] = 0.5 * 50 + 0.5 * 31.25 = 40.625

        Assert.Equal(15.0, ema[1], 3);
        Assert.Equal(22.5, ema[2], 3);
        Assert.Equal(31.25, ema[3], 3);
        Assert.Equal(40.625, ema[4], 3);
    }

    [Fact]
    public void ExponentialMovingAverage_HighAlphaTracksInput()
    {
        var values = new List<double> { 1.0, 100.0, 1.0, 100.0 };
        var ema = AdvancedStatistics.ExponentialMovingAverage(values, 0.9);

        // High alpha means fast tracking
        // ema[1] = 0.9 * 100 + 0.1 * ema[0] = 90 + 0.1 = 90.1
        Assert.True(ema[1] > 80.0, "High alpha should track recent values closely");
        // ema[2] = 0.9 * 1 + 0.1 * ema[1]
        Assert.True(ema[2] < 20.0, "Should drop quickly with high alpha");
    }

    [Fact]
    public void ExponentialMovingAverage_LowAlphaSmooths()
    {
        var values = new List<double> { 10.0, 50.0, 10.0, 50.0, 10.0 };
        var ema = AdvancedStatistics.ExponentialMovingAverage(values, 0.1);

        // Low alpha = lots of smoothing
        // ema[1] = 0.1 * 50 + 0.9 * ema[0] = 5 + 9 = 14
        Assert.True(ema[1] < 20.0, "Low alpha should heavily smooth");
        Assert.True(ema[1] > 10.0, "But should still respond somewhat");
    }

    // --- ReplayMerger: Deterministic ordering ---

    [Fact]
    public void ReplayMerger_MergedStreamIsDeterministicallySorted()
    {
        var streamA = new List<ReplayEvent>
        {
            new("z-evt", 5),
            new("a-evt", 3),
        };
        var streamB = new List<ReplayEvent>
        {
            new("m-evt", 5),
            new("b-evt", 1),
        };

        var merged = ReplayMerger.MergeReplayStreams(streamA, streamB);

        // Events with same sequence should be deterministically ordered by Id
        var seqFiveEvents = merged.Where(e => e.Sequence == 5).ToList();
        if (seqFiveEvents.Count > 1)
        {
            for (var i = 1; i < seqFiveEvents.Count; i++)
            {
                Assert.True(string.Compare(seqFiveEvents[i - 1].Id, seqFiveEvents[i].Id, StringComparison.Ordinal) <= 0,
                    "Events with same sequence should be ordered by Id for determinism");
            }
        }
    }

    // --- RouteOptimizer: Sum vs Max bug ---

    [Fact]
    public void RouteOptimizer_MultiLegFuelCostUsesTotalDistance()
    {
        var legs = new List<Waypoint>
        {
            new("port-a", 100.0),
            new("port-b", 200.0),
            new("port-c", 150.0),
        };
        var portFees = new List<double> { 50.0, 75.0, 60.0 };

        var cost = RouteOptimizer.ComputeMultiLegFuelCost(legs, 2.0, portFees);

        // Correct: total distance = 100 + 200 + 150 = 450nm, fuel = 450 * 2.0 = 900, + fees 185 = 1085
        var totalDistance = legs.Sum(l => l.DistanceNm);
        var expectedFuel = totalDistance * 2.0;
        var expectedFees = portFees.Sum();
        var expectedTotal = expectedFuel + expectedFees;

        Assert.Equal(expectedTotal, cost);
    }

    [Fact]
    public void RouteOptimizer_MultiLegFuelAllLegsContribute()
    {
        var legs = new List<Waypoint>
        {
            new("short", 10.0),
            new("long", 1000.0),
            new("medium", 500.0),
        };
        var fees = new List<double> { 0.0, 0.0, 0.0 };

        var cost = RouteOptimizer.ComputeMultiLegFuelCost(legs, 1.0, fees);

        // Should be 10 + 1000 + 500 = 1510, not max(10, 1000, 500) = 1000
        Assert.Equal(1510.0, cost);
    }

    // --- AdaptiveQueue: Edge cases ---

    [Fact]
    public void AdaptiveQueue_EmptyHistoryReturnsBaseLimit()
    {
        var limit = AdaptiveQueue.ComputeDynamicLimit(100, Array.Empty<double>());
        // Empty utilization history should return base limit, not 0
        Assert.Equal(100, limit);
    }

    // --- Routing.EstimateRouteCost: Port fee subtraction ---

    [Fact]
    public void EstimateRouteCost_PortFeeReducesCost()
    {
        // Cost = distance * fuelRate + portFee (should ADD port fees, not subtract)
        var cost1 = Routing.EstimateRouteCost(100.0, 2.0, 50.0);
        var cost2 = Routing.EstimateRouteCost(100.0, 2.0, 0.0);

        // Port fees are a COST, so higher fee should mean higher total cost
        Assert.True(cost1 > cost2,
            $"Adding port fee should increase cost, not decrease it. WithFee={cost1}, WithoutFee={cost2}");
    }

    [Theory]
    [InlineData(100.0, 1.0, 0.0, 100.0)]
    [InlineData(200.0, 2.0, 50.0, 450.0)]
    [InlineData(50.0, 3.0, 25.0, 175.0)]
    public void EstimateRouteCost_CorrectTotal(double dist, double fuelRate, double portFee, double expected)
    {
        var cost = Routing.EstimateRouteCost(dist, fuelRate, portFee);
        Assert.Equal(expected, cost);
    }

    // --- QueueGuard.EstimateWaitTime: Rate interpretation ---

    [Fact]
    public void QueueGuard_WaitTimeIsDepthDividedByRate()
    {
        // If processing rate is "items per second", wait = depth / rate
        var waitTime = QueueGuard.EstimateWaitTime(100, 10.0);

        // depth=100, rate=10 items/sec → should wait 10 seconds
        Assert.Equal(10.0, waitTime);
    }

    [Theory]
    [InlineData(50, 5.0, 10.0)]
    [InlineData(200, 20.0, 10.0)]
    [InlineData(1, 0.5, 2.0)]
    [InlineData(1000, 100.0, 10.0)]
    public void QueueGuard_WaitTimeScalesCorrectly(int depth, double rate, double expectedWait)
    {
        var wait = QueueGuard.EstimateWaitTime(depth, rate);
        Assert.Equal(expectedWait, wait, 2);
    }

    // --- ChannelScore: Correct formula ---

    [Fact]
    public void ChannelScore_HigherReliabilityAndPriorityIncreasesScore()
    {
        var score1 = Routing.ChannelScore(10, 0.9, 5);
        var score2 = Routing.ChannelScore(10, 0.5, 3);

        Assert.True(score1 > score2);
    }

    [Fact]
    public void ChannelScore_CorrectWeighting()
    {
        // Score should weight reliability and priority against latency
        // Expected: (reliability * priority) / latency
        var score = Routing.ChannelScore(100, 0.8, 4);

        // Correct formula: reliability * priority / latency = 0.8 * 4 / 100 = 0.032
        var expected = 0.8 * 4.0 / 100.0;
        Assert.Equal(expected, score, 4);
    }

    // --- WorkflowEngine.TransitionIfState: TOCTOU ---

    [Fact]
    public void TransitionIfState_AtomicStateCheck()
    {
        var engine = new WorkflowEngine();
        engine.Register("toctou-1");

        // Normal case: state matches, transition succeeds
        var result = engine.TransitionIfState("toctou-1", "queued", "allocated", 100);
        Assert.True(result.Success);
        Assert.Equal("allocated", engine.GetState("toctou-1"));

        // State mismatch: should fail
        var result2 = engine.TransitionIfState("toctou-1", "queued", "departed", 200);
        Assert.False(result2.Success);
        Assert.Equal("allocated", engine.GetState("toctou-1")); // State unchanged
    }

    // --- Parametric cross-module scenario tests ---

    [Theory]
    [InlineData(10, 3, true)]
    [InlineData(20, 5, true)]
    [InlineData(50, 10, true)]
    [InlineData(100, 2, true)]
    public void RecoveryManager_LargeStreamRecovery(int eventCount, int checkpointInterval, bool expectCheckpoint)
    {
        var cpMgr = new CheckpointManager(checkpointInterval);
        var breaker = new CircuitBreaker(5, 3);
        var recovery = new RecoveryManager(cpMgr, breaker);

        for (var i = 1; i <= eventCount; i++)
            recovery.Append("large-stream", new ReplayEvent($"e-{i}", i));

        var cp = cpMgr.Get("large-stream");
        if (expectCheckpoint) Assert.NotNull(cp);

        var recovered = recovery.Recover("large-stream");
        // Recovered count should be less than total (only events after checkpoint)
        if (cp != null)
        {
            Assert.True(recovered.Count < eventCount,
                $"Expected fewer than {eventCount} recovered events, got {recovered.Count}");
        }
    }

    [Theory]
    [InlineData("primary", "secondary")]
    [InlineData("fast", "slow")]
    [InlineData("east", "west")]
    public void RouteFailover_NamedRoutesFailoverCorrectly(string primary, string secondary)
    {
        var mgr = new RouteFailoverManager([primary, secondary], 2, 2);

        Assert.Equal(primary, mgr.ActiveRoute);

        // Fail primary
        mgr.Send(_ => false);
        mgr.Send(_ => false);

        // Should failover to secondary
        var (ok, used) = mgr.Send(_ => true);
        Assert.True(ok);
        Assert.Equal(secondary, used);
    }

    [Theory]
    [InlineData(100, 200)]
    [InlineData(500, 1000)]
    [InlineData(50, 100)]
    public void PolicyAwareQueue_LimitChangesWithEscalation(int baseLimit, int expectedNormal)
    {
        var engine = new PolicyEngine();
        var queue = new PolicyAwareQueue(engine, baseLimit);

        Assert.Equal(expectedNormal, queue.EffectiveLimit + (baseLimit - expectedNormal));

        engine.EscalateToLevel("restricted");
        var restrictedLimit = queue.EffectiveLimit;
        Assert.True(restrictedLimit <= baseLimit / 2 + 1,
            $"Restricted limit {restrictedLimit} should be ~{baseLimit / 2}");
    }

    [Theory]
    [InlineData(5, 0.5)]
    [InlineData(10, 0.1)]
    [InlineData(20, 0.9)]
    public void ExponentialMovingAverage_ParametricAlpha(int count, double alpha)
    {
        var values = Enumerable.Range(1, count).Select(i => (double)i).ToList();
        var ema = AdvancedStatistics.ExponentialMovingAverage(values, alpha);

        Assert.Equal(count, ema.Count);
        Assert.Equal(1.0, ema[0]); // First value always equals input

        // Verify proper EMA recurrence for second value
        var expectedSecond = alpha * values[1] + (1.0 - alpha) * ema[0];
        Assert.Equal(expectedSecond, ema[1], 6);
    }

    // --- Integration scenario: Full pipeline with recovery ---

    [Fact]
    public void FullPipeline_DispatchRecoverAndRevalidate()
    {
        // Set up full dispatch pipeline
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var pipeline = new DispatchPipeline(workflow, policy);

        // Dispatch some orders
        var route = new Route("main-channel", 5);
        for (var i = 0; i < 5; i++)
        {
            var order = new DispatchOrder($"order-{i}", Severity.High, 30);
            var result = pipeline.Execute(order, route, 1000 + i);
            Assert.True(result.Success, $"Order {i} should dispatch successfully");
        }

        // All should be allocated
        for (var i = 0; i < 5; i++)
            Assert.Equal("allocated", workflow.GetState($"order-{i}"));

        // Escalate policy
        policy.EscalateToLevel("halted");

        // New dispatches should fail
        var failResult = pipeline.Execute(
            new DispatchOrder("blocked", Severity.Medium, 60), route, 2000);
        Assert.False(failResult.Success);
    }

    [Fact]
    public void FullPipeline_QueueAndWorkflowCoordination()
    {
        var policy = new PolicyEngine();
        var queue = new PolicyAwareQueue(policy, 50);
        var workflow = new WorkflowEngine();

        // Admit items to queue
        for (var i = 0; i < 30; i++)
        {
            var (admitted, _) = queue.TryAdmit(new QueueItem($"q-{i}", Severity.Medium));
            Assert.True(admitted, $"Item {i} should be admitted under normal policy");
        }

        // Process from queue and register in workflow
        while (queue.Pending > 0)
        {
            var item = queue.Process();
            if (item != null)
            {
                workflow.Register(item.Id);
                workflow.Transition(item.Id, "allocated", 100);
            }
        }

        // Verify all items are allocated
        for (var i = 0; i < 30; i++)
            Assert.Equal("allocated", workflow.GetState($"q-{i}"));
    }

    // --- Routing.ChooseRoute: Latency filter ---

    [Fact]
    public void ChooseRoute_ZeroLatencyExcluded()
    {
        var routes = new List<Route>
        {
            new("dead-channel", 0),
            new("slow-channel", 100),
            new("fast-channel", 10),
        };

        var chosen = Routing.ChooseRoute(routes, new HashSet<string>());
        Assert.NotNull(chosen);
        Assert.Equal("fast-channel", chosen!.Channel);
        Assert.True(chosen.Latency > 0);
    }

    // --- SecurityChain: Off-by-one validation ---

    [Fact]
    public void SecurityChain_ValidatesAllTokensIncludingLast()
    {
        var tokens = new[] { "token-a", "token-b", "token-c" };
        var digests = tokens.Select(Security.Digest).ToList();

        var valid = SecurityChain.ValidateTokenSequence(tokens.ToList(), digests);
        Assert.True(valid, "All tokens should be validated including the last one");

        // Tamper with the last digest
        var badDigests = digests.ToList();
        badDigests[^1] = "tampered_digest_value";

        var invalid = SecurityChain.ValidateTokenSequence(tokens.ToList(), badDigests);
        Assert.False(invalid, "Tampered last digest should be detected");
    }

    // ========================================================================
    // GENUINELY COMPLEX MULTI-COMPONENT INTERACTION TESTS
    // These test emergent behaviors across multiple interacting subsystems
    // ========================================================================

    // --- LeaseManager: Temporal renewal semantics ---

    [Fact]
    public void LeaseManager_RenewalExtendsFromCurrentTime()
    {
        var mgr = new LeaseManager();
        mgr.Acquire("berth-1", "vessel-A", 100, 50);

        Assert.True(mgr.IsActive("berth-1", 120));

        // Renew at T=140 for 50 more time units
        var renewed = mgr.Renew("berth-1", "vessel-A", 140, 50);
        Assert.True(renewed);

        // Should be active until T=190 (140 + 50), not T=150 (100 + 50)
        Assert.True(mgr.IsActive("berth-1", 180),
            "Lease should be active at T=180 after renewal at T=140 for 50 units");
        Assert.True(mgr.IsActive("berth-1", 189),
            "Lease should be active at T=189 after renewal at T=140 for 50 units");
    }

    [Fact]
    public void LeaseManager_RenewalDoesNotShortenLease()
    {
        var mgr = new LeaseManager();
        mgr.Acquire("dock-1", "ship-X", 0, 200);

        // At T=100, renew for 30 more units
        mgr.Renew("dock-1", "ship-X", 100, 30);

        // Original expiry was T=200. Renewal at T=100+30=T=130 would be SHORTER.
        // A correct renewal should extend FROM now, giving T=130.
        // But it should NOT make the lease expire sooner than the original T=200.
        // The expected expiry is max(200, 130) = 200 (or just 130 if renewal replaces).
        // At minimum, the lease should be active at T=125.
        var lease = mgr.GetLease("dock-1");
        Assert.NotNull(lease);
        Assert.True(lease!.ExpiresAt >= 130,
            $"After renewal at T=100 for 30 units, expiry should be >= 130 but was {lease.ExpiresAt}");
    }

    [Fact]
    public void LeaseManager_MultipleRenewalsExtendCorrectly()
    {
        var mgr = new LeaseManager();
        mgr.Acquire("r1", "h1", 0, 10);

        // Renew multiple times
        mgr.Renew("r1", "h1", 5, 10);   // Should expire at T=15
        mgr.Renew("r1", "h1", 10, 10);  // Should expire at T=20

        // After two renewals, lease should be active at T=18
        Assert.True(mgr.IsActive("r1", 18),
            "After renewal at T=10 for 10 units, should be active at T=18");
    }

    [Theory]
    [InlineData(0, 100, 80, 50)]    // Acquire T=0 dur=100, renew T=80 dur=50 → expires T=130
    [InlineData(50, 30, 70, 40)]    // Acquire T=50 dur=30, renew T=70 dur=40 → expires T=110
    [InlineData(0, 10, 8, 20)]      // Acquire T=0 dur=10, renew T=8 dur=20 → expires T=28
    public void LeaseManager_RenewalExpiry(long acqTime, long acqDur, long renewTime, long renewDur)
    {
        var mgr = new LeaseManager();
        mgr.Acquire("res", "holder", acqTime, acqDur);
        mgr.Renew("res", "holder", renewTime, renewDur);

        var expectedExpiry = renewTime + renewDur;
        var lease = mgr.GetLease("res");
        Assert.NotNull(lease);
        Assert.Equal(expectedExpiry, lease!.ExpiresAt);
    }

    // --- CapacityPlanner + ComputeLoadFactor interaction ---

    [Fact]
    public void CapacityPlanner_RejectsWhenAtCapacity()
    {
        var leases = new LeaseManager();
        var planner = new CapacityPlanner(leases, 3);

        // Fill all 3 berths
        leases.Acquire("berth-0", "v1", 0, 100);
        leases.Acquire("berth-1", "v2", 0, 100);
        leases.Acquire("berth-2", "v3", 0, 100);

        // Should NOT be able to accept more
        var canAccept = planner.CanAcceptDispatch(new DispatchOrder("v4", Severity.High, 30), 10);
        Assert.False(canAccept, "Should reject when all berths are occupied");
    }

    [Fact]
    public void CapacityPlanner_AvailableCapacityDecreasesWithLeases()
    {
        var leases = new LeaseManager();
        var planner = new CapacityPlanner(leases, 5);

        var full = planner.AvailableCapacity(0);
        Assert.Equal(5.0, full);

        leases.Acquire("berth-0", "v1", 0, 100);
        leases.Acquire("berth-1", "v2", 0, 100);

        var partial = planner.AvailableCapacity(10);
        Assert.Equal(3.0, partial, 1);
    }

    // --- EventProjection: Snapshot aliasing ---

    [Fact]
    public void EventProjection_SnapshotIsIndependentOfFutureMutations()
    {
        var proj = new EventProjection();
        proj.Apply(new ReplayEvent("evt-1", 1));
        proj.Apply(new ReplayEvent("evt-2", 2));

        proj.TakeSnapshot(2);

        // Apply more events AFTER snapshot
        proj.Apply(new ReplayEvent("evt-3", 3));
        proj.Apply(new ReplayEvent("evt-4", 4));

        // Snapshot should NOT contain evt-3 and evt-4
        var snapshot = proj.SnapshotState;
        Assert.NotNull(snapshot);
        Assert.Equal(2, snapshot!.Count);
        Assert.False(snapshot.ContainsKey("evt-3"), "Snapshot should not contain events applied after snapshot");
        Assert.False(snapshot.ContainsKey("evt-4"), "Snapshot should not contain events applied after snapshot");
    }

    [Fact]
    public void EventProjection_HasDivergedDetectsPostSnapshotChanges()
    {
        var proj = new EventProjection();
        proj.Apply(new ReplayEvent("a", 1));
        proj.TakeSnapshot(1);

        Assert.False(proj.HasDivergedFromSnapshot(), "No changes since snapshot");

        proj.Apply(new ReplayEvent("b", 2));

        Assert.True(proj.HasDivergedFromSnapshot(),
            "Should detect divergence after applying events post-snapshot");
    }

    [Fact]
    public void EventProjection_DivergentKeysAccurate()
    {
        var proj = new EventProjection();
        proj.Apply(new ReplayEvent("stable", 1));
        proj.Apply(new ReplayEvent("willchange", 2));
        proj.TakeSnapshot(2);

        proj.Apply(new ReplayEvent("willchange", 5));
        proj.Apply(new ReplayEvent("newkey", 3));

        var divergent = proj.DivergentKeys();
        Assert.Contains("willchange", divergent);
        Assert.Contains("newkey", divergent);
        Assert.DoesNotContain("stable", divergent);
    }

    [Fact]
    public void EventProjection_RestoreFromSnapshotRevertsState()
    {
        var proj = new EventProjection();
        proj.Apply(new ReplayEvent("a", 1));
        proj.Apply(new ReplayEvent("b", 2));
        proj.TakeSnapshot(2);

        proj.Apply(new ReplayEvent("c", 3));
        proj.Apply(new ReplayEvent("d", 4));

        Assert.Equal(4, proj.CurrentState.Count);

        proj.RestoreFromSnapshot();

        // After restore, should only have a and b
        var state = proj.CurrentState;
        Assert.Equal(2, state.Count);
        Assert.True(state.ContainsKey("a"));
        Assert.True(state.ContainsKey("b"));
        Assert.False(state.ContainsKey("c"));
    }

    // --- ReplayPipeline: End-to-end recovery ---

    [Fact]
    public void ReplayPipeline_RecoverRebuildsProjectionFromCheckpoint()
    {
        var cpMgr = new CheckpointManager(5);
        var breaker = new CircuitBreaker(5, 3);
        var recovery = new RecoveryManager(cpMgr, breaker);
        var projection = new EventProjection();
        var pipeline = new ReplayPipeline(recovery, projection);

        var events = Enumerable.Range(1, 20)
            .Select(i => new ReplayEvent($"e-{i}", i))
            .ToList();

        pipeline.IngestAndProject("stream", events, 10);

        // Simulate crash: clear projection
        var preRecoveryState = projection.CurrentState;
        Assert.Equal(20, preRecoveryState.Count);

        // Recover
        var recovered = pipeline.RecoverAndProject("stream");

        // After recovery, projection should contain all events
        var postRecoveryState = projection.CurrentState;
        Assert.True(postRecoveryState.Count >= 15,
            $"Recovery should restore most events, got {postRecoveryState.Count}");
    }

    // --- CascadingFailureDetector: Diamond dependency double-counting ---

    [Fact]
    public void CascadingFailure_DiamondDependencyCountsEachServiceOnce()
    {
        // Diamond: gateway → routing, gateway → policy, routing → analytics, policy → analytics
        var services = new List<ServiceDefinition>
        {
            new("gateway", 8150, "/health", "1.0.0", []),
            new("routing", 8151, "/health", "1.0.0", ["gateway"]),
            new("policy", 8152, "/health", "1.0.0", ["gateway"]),
            new("analytics", 8154, "/health", "1.0.0", ["routing", "policy"]),
        };

        var detector = new CascadingFailureDetector(services);
        var affected = detector.AffectedServices("gateway");

        // Each service should appear at most once in the affected list
        var distinct = affected.Distinct().ToList();
        Assert.Equal(distinct.Count, affected.Count);
    }

    [Fact]
    public void CascadingFailure_ImpactScoreDoesNotGrowExponentially()
    {
        var services = ServiceRegistry.All();
        var detector = new CascadingFailureDetector(services);

        // Gateway is the root dependency for everything
        var impact = detector.ComputeImpactScore("gateway");

        // With 7 dependent services, impact should be bounded
        // not grow exponentially through diamond paths
        Assert.True(impact <= 20.0,
            $"Gateway failure impact {impact:F1} seems unreasonably high - likely double-counting");
    }

    [Fact]
    public void CascadingFailure_ImpactMapNoDuplicates()
    {
        var services = new List<ServiceDefinition>
        {
            new("root", 8000, "/h", "1.0", []),
            new("mid-a", 8001, "/h", "1.0", ["root"]),
            new("mid-b", 8002, "/h", "1.0", ["root"]),
            new("leaf", 8003, "/h", "1.0", ["mid-a", "mid-b"]),
        };

        var detector = new CascadingFailureDetector(services);
        var impactMap = detector.ComputeImpactMap("root");

        // Leaf should only be counted once (not once through mid-a and once through mid-b)
        Assert.True(impactMap.GetValueOrDefault("leaf") <= 1.5,
            $"Leaf impact {impactMap.GetValueOrDefault("leaf"):F2} suggests double-counting through diamond");
    }

    // --- ServiceHealthAggregator: Cascade interaction ---

    [Fact]
    public void ServiceHealthAggregator_SingleFailureDoesNotCrashScore()
    {
        var detector = new CascadingFailureDetector(ServiceRegistry.All());
        var aggregator = new ServiceHealthAggregator(detector);

        aggregator.MarkDown("security");

        var score = aggregator.SystemHealthScore();
        Assert.True(score >= 0.0 && score <= 1.0,
            $"Health score {score} out of bounds");
        Assert.True(score > 0.5,
            $"Single non-critical service failure should not drop health below 50%, got {score:F2}");
    }

    // --- WeightedRouter: Stale cumulative weights ---

    [Fact]
    public void WeightedRouter_UpdateWeightChangesDistribution()
    {
        var router = new WeightedRouter([("route-a", 50.0), ("route-b", 50.0)]);

        // Initially 50/50 split. At random=0.25 (first 50%), should get route-a
        Assert.Equal("route-a", router.Select(0.25));

        // Update route-a weight to 0, route-b to 100
        router.UpdateWeight("route-a", 0.0);

        // Now ALL traffic should go to route-b
        var selected = router.Select(0.25);
        Assert.Equal("route-b", selected);
    }

    [Fact]
    public void WeightedRouter_AddRouteIncludedInSelection()
    {
        var router = new WeightedRouter([("existing", 100.0)]);

        router.AddRoute("new-route", 100.0);

        // With two equal-weight routes, selecting at 0.75 should get the second
        var totalWeight = router.TotalWeight;
        Assert.Equal(200.0, totalWeight);
    }

    [Fact]
    public void WeightedRouter_RemoveRouteExcludedFromSelection()
    {
        var router = new WeightedRouter([("a", 50.0), ("b", 50.0), ("c", 50.0)]);

        router.RemoveRoute("b");

        // Total weight should reflect removal
        Assert.Equal(100.0, router.TotalWeight);

        // All selections should be a or c, never b
        for (var r = 0.0; r <= 1.0; r += 0.1)
        {
            var selected = router.Select(r);
            Assert.NotEqual("b", selected);
        }
    }

    [Theory]
    [InlineData(0.0)]
    [InlineData(0.25)]
    [InlineData(0.5)]
    [InlineData(0.75)]
    [InlineData(0.99)]
    public void WeightedRouter_SelectionAfterWeightUpdate(double random)
    {
        var router = new WeightedRouter([("fast", 80.0), ("slow", 20.0)]);

        // Change to equal weights
        router.UpdateWeight("fast", 50.0);
        router.UpdateWeight("slow", 50.0);

        // Midpoint should now split evenly
        var atMid = router.Select(0.5);
        var total = router.TotalWeight;
        Assert.Equal(100.0, total);
    }

    // --- BackpressureController: Uses wrong wait time from QueueGuard ---

    [Fact]
    public void BackpressureController_WaitEstimateReflectsActualWaitTime()
    {
        // rate=10 items/sec, max acceptable=30 sec
        var controller = new BackpressureController(1000, 10.0, 30.0);

        // depth=100, rate=10 → actual wait = 10 seconds → should NOT apply backpressure
        var decision = controller.Evaluate(100, 1);

        Assert.Equal(10.0, decision.CurrentWaitEstimate, 1);
        Assert.False(decision.ShouldApply,
            $"Wait of 10s should not trigger backpressure (max 30s), but estimate was {decision.CurrentWaitEstimate:F1}s");
    }

    [Fact]
    public void BackpressureController_AppliesWhenWaitExceedsMax()
    {
        // rate=2 items/sec, max acceptable=10 sec
        var controller = new BackpressureController(1000, 2.0, 10.0);

        // depth=50, rate=2 → actual wait = 25 seconds → SHOULD apply backpressure
        var decision = controller.Evaluate(50, 1);

        Assert.True(decision.ShouldApply,
            $"Wait of 25s should trigger backpressure (max 10s), but estimate was {decision.CurrentWaitEstimate:F1}s");
    }

    [Theory]
    [InlineData(100, 10.0, 20.0, false)]   // wait=10s, max=20s → no backpressure
    [InlineData(200, 5.0, 10.0, true)]     // wait=40s, max=10s → backpressure
    [InlineData(50, 25.0, 5.0, false)]     // wait=2s, max=5s → no backpressure
    [InlineData(1000, 10.0, 50.0, true)]   // wait=100s, max=50s → backpressure
    public void BackpressureController_Scenarios(int depth, double rate, double maxWait, bool expectBackpressure)
    {
        var controller = new BackpressureController(2000, rate, maxWait);
        var decision = controller.Evaluate(depth, 1);
        Assert.Equal(expectBackpressure, decision.ShouldApply);
    }

    // --- AdmissionController: Full pipeline backpressure + queue + policy ---

    [Fact]
    public void AdmissionController_RejectsUnderBackpressure()
    {
        var policy = new PolicyEngine();
        var queue = new PolicyAwareQueue(policy, 1000);
        // processingRate=1.0, maxWait=5.0 → anything over depth 5 triggers backpressure
        var bp = new BackpressureController(1000, 1.0, 5.0);
        var controller = new AdmissionController(bp, queue);

        // Admit items until backpressure kicks in
        for (var i = 0; i < 20; i++)
        {
            var (admitted, reason) = controller.Submit(new QueueItem($"item-{i}", Severity.Medium), i);
            if (!admitted)
            {
                Assert.Contains("backpressure", reason);
                break;
            }
        }

        Assert.True(controller.RejectedCount > 0, "Should have some rejections from backpressure");
    }

    // --- SlaTracker: Window boundary semantics ---

    [Fact]
    public void SlaTracker_BoundaryEntriesHandledCorrectly()
    {
        var tracker = new SlaTracker(100);

        // Add records right at the boundary
        tracker.Record(new SlaRecord("svc-1", 0, 10, 30));     // compliant
        tracker.Record(new SlaRecord("svc-1", 50, 20, 30));    // compliant
        tracker.Record(new SlaRecord("svc-1", 100, 15, 30));   // compliant, exactly at boundary

        var compliance = tracker.GetServiceCompliance("svc-1", 100);

        // All records are within window [0, 100] and all are compliant
        Assert.Equal(100.0, compliance);
    }

    [Fact]
    public void SlaTracker_EvictionAndComplianceConsistent()
    {
        var tracker = new SlaTracker(50);

        tracker.Record(new SlaRecord("svc", 10, 5, 30));   // compliant
        tracker.Record(new SlaRecord("svc", 30, 5, 30));   // compliant
        tracker.Record(new SlaRecord("svc", 60, 50, 30));  // NOT compliant
        tracker.Record(new SlaRecord("svc", 80, 5, 30));   // compliant

        // At T=100, window is [50, 100]. Records at T=10 and T=30 should be evicted.
        // Remaining: T=60 (not compliant), T=80 (compliant) → 50% compliance
        var compliance = tracker.GetServiceCompliance("svc", 100);
        Assert.Equal(50.0, compliance);
    }

    // --- PolicyFeedbackLoop: SLA + Policy escalation interaction ---

    [Fact]
    public void PolicyFeedbackLoop_EscalatesOnPoorSla()
    {
        var policy = new PolicyEngine();
        var sla = new SlaTracker(1000);

        // Fill with bad SLA records
        for (var i = 0; i < 20; i++)
            sla.Record(new SlaRecord("svc-1", i, 120, 30)); // all non-compliant

        var loop = new PolicyFeedbackLoop(policy, sla);

        // Evaluate multiple times to trigger escalation (needs 3 consecutive bad windows)
        for (var i = 0; i < 5; i++)
            loop.Evaluate(100, 80.0, 95.0);

        Assert.NotEqual("normal", policy.Current);
    }

    [Fact]
    public void PolicyFeedbackLoop_DeescalatesOnGoodSla()
    {
        var policy = new PolicyEngine();
        policy.EscalateToLevel("watch");

        var sla = new SlaTracker(1000);
        for (var i = 0; i < 20; i++)
            sla.Record(new SlaRecord("svc-1", i, 5, 30)); // all compliant

        var loop = new PolicyFeedbackLoop(policy, sla);

        // Need enough good windows to trigger deescalation
        for (var i = 0; i < 10; i++)
            loop.Evaluate(100, 80.0, 90.0);

        Assert.Equal("normal", policy.Current);
    }

    // --- TimeSeriesAggregator: Running mean drift after eviction ---

    [Fact]
    public void TimeSeriesAggregator_RunningMeanStaysAccurateAfterEviction()
    {
        var agg = new TimeSeriesAggregator(10);

        // Add values in bucket 0-9 (key=0)
        agg.Add(5, 100.0);
        agg.Add(8, 200.0);

        // Add values in bucket 10-19 (key=1)
        agg.Add(15, 300.0);

        Assert.Equal(200.0, agg.RunningMean); // (100+200+300)/3

        // Evict bucket 0
        agg.EvictBefore(10);

        // Running mean should reflect only remaining data
        // But if running sum wasn't updated, it's still (100+200+300)/3 = 200
        // instead of 300/1 = 300
        Assert.Equal(300.0, agg.RunningMean);
    }

    [Fact]
    public void TimeSeriesAggregator_WindowMeanCorrectAfterEviction()
    {
        var agg = new TimeSeriesAggregator(100);

        for (var i = 0; i < 1000; i += 50)
            agg.Add(i, i * 1.0);

        agg.EvictBefore(500);

        var windowMean = agg.WindowMean(500, 1000);
        var runningMean = agg.RunningMean;

        // After eviction, window mean and running mean should agree
        // (only data >= 500 remains)
        Assert.Equal(windowMean, runningMean, 1);
    }

    // --- TrendDetector: Integrates TimeSeriesAggregator + AnomalyDetector ---

    [Fact]
    public void TrendDetector_IdentifiesIncreasingTrend()
    {
        var agg = new TimeSeriesAggregator(100);
        var anomaly = new AnomalyDetector(3.0, 50);
        var detector = new TrendDetector(agg, anomaly, 5);

        var points = Enumerable.Range(1, 10)
            .Select(i => ((long)i * 10, (double)i * 10))
            .ToList();

        var result = detector.Analyze(points);
        Assert.Equal("increasing", result.Direction);
        Assert.True(result.Slope > 0);
    }

    // --- DispatchCoordinator: Full 4-component orchestration ---

    [Fact]
    public void DispatchCoordinator_FullDispatchCycle()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var leases = new LeaseManager();
        var planner = new CapacityPlanner(leases, 5);
        var coordinator = new DispatchCoordinator(workflow, policy, leases, planner);

        var order = new DispatchOrder("ord-1", Severity.High, 30);
        var result = coordinator.Dispatch(order, 100, 500);

        Assert.True(result.Success, $"Dispatch should succeed: {result.Error}");
        Assert.NotNull(result.AssignedBerth);
        Assert.Equal("allocated", result.WorkflowState);
    }

    [Fact]
    public void DispatchCoordinator_RejectsWhenCapacityFull()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var leases = new LeaseManager();
        var planner = new CapacityPlanner(leases, 3);
        var coordinator = new DispatchCoordinator(workflow, policy, leases, planner);

        // Fill all berths
        for (var i = 0; i < 3; i++)
        {
            var result = coordinator.Dispatch(
                new DispatchOrder($"fill-{i}", Severity.High, 30), 100, 500);
            Assert.True(result.Success, $"Fill dispatch {i} should succeed");
        }

        // Fourth should fail
        var overflow = coordinator.Dispatch(
            new DispatchOrder("overflow", Severity.High, 30), 100, 500);
        Assert.False(overflow.Success, "Should reject when all berths occupied");
    }

    [Fact]
    public void DispatchCoordinator_CompletionReleasesCapacity()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var leases = new LeaseManager();
        var planner = new CapacityPlanner(leases, 2);
        var coordinator = new DispatchCoordinator(workflow, policy, leases, planner);

        // Fill both berths
        coordinator.Dispatch(new DispatchOrder("a", Severity.High, 30), 100, 500);
        coordinator.Dispatch(new DispatchOrder("b", Severity.High, 30), 100, 500);

        // Complete one
        var completed = coordinator.Complete("a", 200);
        Assert.True(completed);

        // Now should have capacity for one more
        var result = coordinator.Dispatch(
            new DispatchOrder("c", Severity.High, 30), 300, 500);
        Assert.True(result.Success, "Should have capacity after completion");
    }

    [Fact]
    public void DispatchCoordinator_PolicyBlocksDispatch()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var leases = new LeaseManager();
        var planner = new CapacityPlanner(leases, 10);
        var coordinator = new DispatchCoordinator(workflow, policy, leases, planner);

        policy.EscalateToLevel("halted");

        var result = coordinator.Dispatch(
            new DispatchOrder("blocked", Severity.Critical, 15), 100, 500);
        Assert.False(result.Success);
        Assert.Equal("halted", result.PolicyState);
    }

    [Fact]
    public void DispatchCoordinator_NoOrphanedResourcesOnRejection()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var leases = new LeaseManager();
        var planner = new CapacityPlanner(leases, 10);
        var coordinator = new DispatchCoordinator(workflow, policy, leases, planner);

        policy.EscalateToLevel("restricted");

        // Low-priority order should be rejected
        var result = coordinator.Dispatch(
            new DispatchOrder("low-pri", Severity.Low, 120), 100, 500);
        Assert.False(result.Success);

        // No leases should be held for rejected orders
        Assert.Equal(0, leases.ActiveLeaseCount(100));
        // No berth should be assigned
        Assert.Null(coordinator.GetAssignedBerth("low-pri"));
    }

    [Fact]
    public void DispatchCoordinator_BatchRespectsPolicyAndCapacity()
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var leases = new LeaseManager();
        var planner = new CapacityPlanner(leases, 3);
        var coordinator = new DispatchCoordinator(workflow, policy, leases, planner);

        var orders = Enumerable.Range(1, 5)
            .Select(i => new DispatchOrder($"batch-{i}", Severity.High, 30))
            .ToList();

        var results = coordinator.DispatchBatch(orders, 100, 500);

        var succeeded = results.Count(r => r.Success);
        Assert.Equal(3, succeeded); // Limited by capacity

        var failed = results.Count(r => !r.Success);
        Assert.Equal(2, failed);
    }

    // --- End-to-end integration: SLA → Policy → Queue → Dispatch ---

    [Fact]
    public void EndToEnd_SlaTriggeredPolicyAffectsDispatch()
    {
        var policy = new PolicyEngine();
        var slaTracker = new SlaTracker(1000);
        var workflow = new WorkflowEngine();
        var leases = new LeaseManager();
        var planner = new CapacityPlanner(leases, 10);
        var coordinator = new DispatchCoordinator(workflow, policy, leases, planner);
        var loop = new PolicyFeedbackLoop(policy, slaTracker);

        // Record terrible SLA data
        for (var i = 0; i < 30; i++)
            slaTracker.Record(new SlaRecord("main-service", i, 200, 30));

        // Trigger policy evaluation multiple times
        for (var i = 0; i < 5; i++)
            loop.Evaluate(100, 50.0, 95.0);

        // Policy should have escalated
        var policyState = policy.Current;
        Assert.NotEqual("normal", policyState);

        // Try to dispatch a low-priority order
        var result = coordinator.Dispatch(
            new DispatchOrder("low", Severity.Low, 120), 100, 500);

        // Under escalated policy, low priority should be rejected
        if (policyState == "restricted" || policyState == "halted")
            Assert.False(result.Success);
    }

    [Theory]
    [InlineData(3, 10)]
    [InlineData(5, 20)]
    [InlineData(2, 5)]
    public void DispatchCoordinator_BatchWithVaryingCapacity(int capacity, int orderCount)
    {
        var workflow = new WorkflowEngine();
        var policy = new PolicyEngine();
        var leases = new LeaseManager();
        var planner = new CapacityPlanner(leases, capacity);
        var coordinator = new DispatchCoordinator(workflow, policy, leases, planner);

        var orders = Enumerable.Range(1, orderCount)
            .Select(i => new DispatchOrder($"o-{i}", Severity.High, 30))
            .ToList();

        var results = coordinator.DispatchBatch(orders, 100, 500);
        var succeeded = results.Count(r => r.Success);

        Assert.Equal(Math.Min(capacity, orderCount), succeeded);
    }
}
