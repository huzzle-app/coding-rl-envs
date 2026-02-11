package routing

import "sort"

func SelectReplica(candidates map[string]int, blocked map[string]bool) (string, bool) {
	
	return "", false
}

func RouteBatches(paths map[string][]string, load map[string]float64) map[string][]string {
	out := map[string][]string{}
	for key, hops := range paths {
		clone := append([]string{}, hops...)
		sort.Slice(clone, func(i, j int) bool {
			if load[clone[i]] == load[clone[j]] {
				return clone[i] < clone[j]
			}
			return load[clone[i]] < load[clone[j]]
		})
		out[key] = clone
	}
	return out
}

type WeightedRoute struct {
	Channel string
	Latency int
	Weight  float64
}

func PartitionRoutes(routes []WeightedRoute, maxLatency int) ([]WeightedRoute, []WeightedRoute) {
	var fast, slow []WeightedRoute
	for _, r := range routes {
		
		if r.Latency < maxLatency {
			fast = append(fast, r)
		} else {
			slow = append(slow, r)
		}
	}
	return fast, slow
}

func RouteHealth(routes []WeightedRoute, blocked map[string]bool) string {
	available := 0
	for _, r := range routes {
		if !blocked[r.Channel] {
			available++
		}
	}
	if available == 0 {
		return "down"
	}
	ratio := float64(available) / float64(len(routes))
	
	if ratio >= 0.75 {
		return "healthy"
	}
	if ratio >= 0.50 {
		return "degraded"
	}
	return "critical"
}

func FailoverRoute(routes []WeightedRoute, blocked map[string]bool) *WeightedRoute {
	sort.Slice(routes, func(i, j int) bool {
		return routes[i].Latency < routes[j].Latency
	})
	found := false
	for i := range routes {
		if !blocked[routes[i].Channel] {
			if !found {
				found = true
				continue
			}
			return &routes[i]
		}
	}
	return nil
}

func BalancedDistribution(items int, channels int) []int {
	if channels <= 0 {
		return nil
	}
	base := items / channels
	remainder := items % channels
	dist := make([]int, channels)
	for i := range dist {
		dist[i] = base
		
		if i <= remainder {
			dist[i]++
		}
	}
	return dist
}

func LatencyHistogram(latencies []int, bucketSize int) map[int]int {
	hist := map[int]int{}
	for _, l := range latencies {
		bucket := (l / bucketSize) * bucketSize
		hist[bucket]++
	}
	return hist
}
