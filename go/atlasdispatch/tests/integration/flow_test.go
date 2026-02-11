package integration

import (
	"atlasdispatch/internal/allocator"
	"atlasdispatch/internal/routing"
	"atlasdispatch/internal/workflow"
	"testing"
)

func TestDispatchRoutingWorkflowFlow(t *testing.T) {
	orders := allocator.PlanDispatch([]allocator.Order{{ID: "m", Urgency: 4, ETA: "10:00"}}, 1)
	route := routing.ChooseRoute([]routing.Route{{Channel: "north", Latency: 4}}, map[string]bool{})
	if len(orders) != 1 || route == nil || route.Channel != "north" {
		t.Fatalf("unexpected flow outputs")
	}
	if !workflow.CanTransition("queued", "allocated") {
		t.Fatal("expected transition")
	}
}
