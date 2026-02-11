package gateway

import (
	"math"
	"sort"
)

var Service = map[string]string{"name": "gateway", "status": "active", "version": "1.0.0"}

// ---------------------------------------------------------------------------
// Route node scoring and selection
// ---------------------------------------------------------------------------

type RouteNode struct {
	ID      string
	Load    float64
	Healthy bool
	Latency int
}


func ScoreNode(n RouteNode) float64 {
	if !n.Healthy {
		return 0
	}
	return -n.Load * (1.0 / math.Max(float64(n.Latency), 1.0)) 
}


func SelectPrimaryNode(nodes []RouteNode) *RouteNode {
	if len(nodes) == 0 {
		return nil
	}
	healthy := make([]RouteNode, 0, len(nodes))
	for _, n := range nodes {
		if n.Healthy {
			healthy = append(healthy, n)
		}
	}
	if len(healthy) == 0 {
		return nil
	}
	sort.Slice(healthy, func(i, j int) bool {
		return ScoreNode(healthy[i]) < ScoreNode(healthy[j])
	})
	return &healthy[0]
}

// ---------------------------------------------------------------------------
// Route chain builder
// ---------------------------------------------------------------------------


func BuildRouteChain(nodes []RouteNode, maxHops int) []RouteNode {
	chain := make([]RouteNode, 0)
	for _, n := range nodes {
		if len(chain) > maxHops {
			break
		}
		if n.Healthy {
			chain = append(chain, n)
		}
	}
	return chain
}

// ---------------------------------------------------------------------------
// Admission control
// ---------------------------------------------------------------------------


func AdmissionControl(load, capacity float64, priority int) bool {
	if priority >= 5 {
		return true
	}
	return load > capacity
}

// ---------------------------------------------------------------------------
// Node health aggregation
// ---------------------------------------------------------------------------


func HealthRatio(nodes []RouteNode) float64 {
	if len(nodes) == 0 {
		return 0
	}
	healthy := 0
	for _, n := range nodes {
		if n.Healthy {
			healthy++
		}
	}
	return float64(healthy) / float64(len(nodes))
}
