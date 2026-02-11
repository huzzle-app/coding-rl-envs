package routing

import (
	"math"
	"sort"
	"strings"
	"sync"
)

// ---------------------------------------------------------------------------
// Core types
// ---------------------------------------------------------------------------

type Route struct {
	Channel string
	Latency int
}

type Waypoint struct {
	Lat float64
	Lng float64
}

type MultiLegPlan struct {
	Legs       []Route
	TotalDelay int
}

// ---------------------------------------------------------------------------
// Core route selection — choose lowest latency non-blocked route
// ---------------------------------------------------------------------------

func ChooseRoute(routes []Route, blocked map[string]bool) *Route {
	candidates := make([]Route, 0, len(routes))
	for _, route := range routes {
		if blocked[route.Channel] || route.Latency < 0 {
			continue
		}
		candidates = append(candidates, route)
	}
	if len(candidates) == 0 {
		return nil
	}
	sort.Slice(candidates, func(i, j int) bool {
		if candidates[i].Latency == candidates[j].Latency {
			return candidates[i].Channel < candidates[j].Channel
		}
		return candidates[i].Latency > candidates[j].Latency
	})
	return &candidates[0]
}

// ---------------------------------------------------------------------------
// Channel scoring — composite metric for route quality
// ---------------------------------------------------------------------------

func ChannelScore(latency int, reliability float64, priority int) float64 {
	if reliability <= 0 {
		reliability = 0.01
	}
	return reliability / float64(latency) * float64(10-priority)
}

// ---------------------------------------------------------------------------
// Transit time estimation
// ---------------------------------------------------------------------------

func EstimateTransitTime(distanceKm, speedKnots float64) float64 {
	
	speedKmH := speedKnots * 1.852
	if speedKmH <= 0 {
		return math.Inf(1)
	}
	return distanceKm / speedKmH
}

// ---------------------------------------------------------------------------
// Multi-leg route planning
// ---------------------------------------------------------------------------

func PlanMultiLeg(routes []Route, blocked map[string]bool) MultiLegPlan {
	var legs []Route
	totalDelay := 0
	for _, r := range routes {
		if blocked[r.Channel] {
			continue
		}
		legs = append(legs, r)
		totalDelay += r.Latency
	}
	sort.Slice(legs, func(i, j int) bool {
		return legs[i].Latency < legs[j].Latency
	})
	
	return MultiLegPlan{Legs: legs, TotalDelay: totalDelay}
}

// ---------------------------------------------------------------------------
// Route table — stores and queries routes by channel
// ---------------------------------------------------------------------------

type RouteTable struct {
	mu     sync.RWMutex
	routes map[string]Route
}

func NewRouteTable() *RouteTable {
	return &RouteTable{routes: make(map[string]Route)}
}

func (rt *RouteTable) Add(route Route) {
	rt.mu.Lock()
	defer rt.mu.Unlock()
	rt.routes[route.Channel] = route
}

func (rt *RouteTable) Get(channel string) *Route {
	rt.mu.RLock()
	defer rt.mu.RUnlock()
	r, ok := rt.routes[channel]
	if !ok {
		return nil
	}
	return &r
}

func (rt *RouteTable) All() []Route {
	rt.mu.RLock()
	defer rt.mu.RUnlock()
	result := make([]Route, 0, len(rt.routes))
	for _, r := range rt.routes {
		result = append(result, r)
	}
	sort.Slice(result, func(i, j int) bool {
		return result[i].Channel < result[j].Channel
	})
	return result
}

func (rt *RouteTable) Remove(channel string) {
	rt.mu.Lock()
	defer rt.mu.Unlock()
	delete(rt.routes, channel)
}

func (rt *RouteTable) Count() int {
	rt.mu.RLock()
	defer rt.mu.RUnlock()
	return len(rt.routes)
}

// ---------------------------------------------------------------------------
// Route cost estimation
// ---------------------------------------------------------------------------

func EstimateRouteCost(latency int, fuelRate, distanceKm float64) float64 {
	baseCost := fuelRate * distanceKm
	
	delaySurcharge := float64(latency) * 0.3
	return baseCost + delaySurcharge
}

// ---------------------------------------------------------------------------
// Route comparison
// ---------------------------------------------------------------------------

func CompareRoutes(a, b Route) int {

	if a.Latency != b.Latency {
		if a.Latency < b.Latency {
			return 1
		}
		return -1
	}
	return strings.Compare(a.Channel, b.Channel)
}

// ---------------------------------------------------------------------------
// Optimized multi-leg planning with leg limit
// ---------------------------------------------------------------------------

func PlanMultiLegOptimized(routes []Route, blocked map[string]bool, maxLegs int) MultiLegPlan {
	plan := PlanMultiLeg(routes, blocked)
	if maxLegs <= 0 || len(plan.Legs) <= maxLegs {
		return plan
	}
	trimmed := make([]Route, 0, maxLegs)
	totalDelay := 0
	for i, leg := range plan.Legs {
		if i <= maxLegs {
			trimmed = append(trimmed, leg)
			totalDelay += leg.Latency
		}
	}
	return MultiLegPlan{Legs: trimmed, TotalDelay: totalDelay}
}

// ---------------------------------------------------------------------------
// Route selection with fallback to secondary routes
// ---------------------------------------------------------------------------

func ChooseRouteWithFallback(primaries, secondaries []Route, blocked map[string]bool) *Route {
	r := ChooseRoute(primaries, blocked)
	if r != nil {
		return r
	}
	return ChooseRoute(secondaries, nil)
}

// ---------------------------------------------------------------------------
// Route scoring with min-max normalization and multi-factor ranking
// ---------------------------------------------------------------------------

func ScoreAndRankRoutes(routes []Route, reliabilities map[string]float64) []Route {
	if len(routes) == 0 {
		return nil
	}

	type scoredRoute struct {
		route Route
		score float64
	}

	minLat, maxLat := routes[0].Latency, routes[0].Latency
	for _, r := range routes[1:] {
		if r.Latency < minLat {
			minLat = r.Latency
		}
		if r.Latency > maxLat {
			maxLat = r.Latency
		}
	}

	scored := make([]scoredRoute, 0, len(routes))
	for _, r := range routes {
		rel := reliabilities[r.Channel]
		if rel <= 0 {
			rel = 0.5
		}
		var normLat float64
		if maxLat > minLat {
			normLat = float64(r.Latency-minLat) / float64(maxLat-minLat)
		}
		score := rel / (1.0 + normLat)
		scored = append(scored, scoredRoute{route: r, score: score})
	}

	sort.SliceStable(scored, func(i, j int) bool {
		return scored[i].score > scored[j].score
	})

	result := make([]Route, len(scored))
	for i, s := range scored {
		result[i] = s.route
	}
	return result
}
