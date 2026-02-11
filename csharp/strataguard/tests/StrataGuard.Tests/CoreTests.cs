using Xunit;

namespace StrataGuard.Tests;

public sealed class CoreTests
{
    [Fact]
    public void PlanDispatchRespectsCapacity()
    {
        var outOrders = Allocator.PlanDispatch(
        [
            new DispatchOrder("a", 1, 60),
            new DispatchOrder("b", 4, 70),
            new DispatchOrder("c", 4, 30)
        ], 2);

        Assert.Collection(outOrders,
            o => Assert.Equal("c", o.Id),
            o => Assert.Equal("b", o.Id));
    }

    [Fact]
    public void ChooseRouteIgnoresBlocked()
    {
        var route = Routing.ChooseRoute([new Route("alpha", 8), new Route("beta", 3)], new HashSet<string> { "beta" });
        Assert.NotNull(route);
        Assert.Equal("alpha", route!.Channel);
    }

    [Fact]
    public void NextPolicyEscalates()
    {
        Assert.Equal("restricted", Policy.NextPolicy("watch", 3));
    }

    [Fact]
    public void VerifySignatureDigest()
    {
        var payload = "manifest:v1";
        var digest = Security.Digest(payload);
        Assert.True(Security.VerifySignature(payload, digest, digest));
        Assert.False(Security.VerifySignature(payload, digest[..^1], digest));
    }

    [Fact]
    public void ReplayLatestSequenceWins()
    {
        var replayed = Resilience.Replay([new ReplayEvent("x", 1), new ReplayEvent("x", 2), new ReplayEvent("y", 1)]);
        Assert.Equal(2, replayed.Count);
        Assert.Equal(2, replayed.Last().Sequence);
    }

    [Fact]
    public void QueueGuardUsesHardLimit()
    {
        Assert.False(QueueGuard.ShouldShed(9, 10, false));
        Assert.True(QueueGuard.ShouldShed(11, 10, false));
        Assert.True(QueueGuard.ShouldShed(8, 10, true));
    }

    [Fact]
    public void StatisticsPercentileSparse()
    {
        Assert.Equal(4, Statistics.Percentile([4, 1, 9, 7], 50));
        Assert.Equal(0, Statistics.Percentile([], 90));
    }

    [Fact]
    public void WorkflowGraphEnforced()
    {
        Assert.True(Workflow.CanTransition("queued", "allocated"));
        Assert.False(Workflow.CanTransition("queued", "arrived"));
    }

    [Fact]
    public void DispatchOrderUrgencyScore()
    {
        Assert.Equal(120, new DispatchOrder("d", 3, 30).UrgencyScore());
    }

    [Fact]
    public void FlowIntegration()
    {
        var orders = Allocator.PlanDispatch([new DispatchOrder("z", 5, 20)], 1);
        var route = Routing.ChooseRoute([new Route("north", 4)], new HashSet<string>());
        Assert.Single(orders);
        Assert.NotNull(route);
        Assert.True(Workflow.CanTransition("queued", "allocated"));
    }

    [Fact]
    public void ReplayConvergence()
    {
        var a = Resilience.Replay([new ReplayEvent("k", 1), new ReplayEvent("k", 2)]);
        var b = Resilience.Replay([new ReplayEvent("k", 2), new ReplayEvent("k", 1)]);
        Assert.Equal(a, b);
    }

    [Fact]
    public void ContractsRequiredFields()
    {
        Assert.Equal(8150, Contracts.ServicePorts["gateway"]);
        Assert.True(Contracts.ServicePorts["routing"] > 0);
    }
}
