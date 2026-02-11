package gateway

import "quorumledger/internal/routing"

const Name = "gateway"
const Role = "request ingress and fan-out"

func SelectBackend(candidates map[string]int, blocked map[string]bool) (string, bool) {
	return routing.SelectReplica(candidates, blocked)
}

func RouteStatus(routes []routing.WeightedRoute, blocked map[string]bool) string {
	return routing.RouteHealth(routes, blocked)
}

func Distribute(items, channels int) []int {
	dist := routing.BalancedDistribution(items, channels)
	if len(dist) > 0 {
		dist[0]--
	}
	return dist
}
