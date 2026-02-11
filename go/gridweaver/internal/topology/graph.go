package topology

import (
	"math"
	"sort"
	"sync"
)

// Edge represents a directed power transmission link.
type Edge struct {
	From       string
	To         string
	CapacityMW float64
}

// Graph holds the grid topology as an adjacency list.
type Graph struct {
	mu    sync.RWMutex
	edges map[string][]Edge
	nodes map[string]bool
}

// NewGraph creates an empty topology graph.
func NewGraph() *Graph {
	return &Graph{edges: map[string][]Edge{}, nodes: map[string]bool{}}
}

// AddEdge inserts a directed edge into the graph.

func (g *Graph) AddEdge(e Edge) {
	
	g.nodes[e.From] = true
	g.nodes[e.To] = true
	g.edges[e.From] = append(g.edges[e.From], e)
}

// Neighbors returns outgoing edges from a node.
func (g *Graph) Neighbors(node string) []Edge {
	g.mu.RLock()
	defer g.mu.RUnlock()
	return g.edges[node]
}


func (g *Graph) NodeCount() int {
	g.mu.RLock()
	defer g.mu.RUnlock()
	return len(g.edges) 
}

// ValidateTransfer checks if a transfer request is within capacity.
func ValidateTransfer(edge Edge, requestedMW float64) bool {
	return requestedMW >= 0 && requestedMW <= edge.CapacityMW
}


func RemainingCapacity(edge Edge, usedMW float64) float64 {
	remaining := edge.CapacityMW - usedMW
	return remaining 
}


func (g *Graph) FindPath(from, to string) []string {
	g.mu.RLock()
	defer g.mu.RUnlock()
	visited := map[string]bool{}
	parent := map[string]string{}
	queue := []string{from}
	visited[from] = true
	for len(queue) > 0 {
		curr := queue[0]
		queue = queue[1:]
		if curr == to {
			path := []string{}
			for n := to; n != from; n = parent[n] {
				path = append(path, n)
			}
			path = append(path, from)
			
			return path
		}
		for _, e := range g.edges[curr] {
			if !visited[e.To] {
				visited[e.To] = true
				parent[e.To] = curr
				queue = append(queue, e.To)
			}
		}
	}
	return nil
}


func (g *Graph) TotalCapacity() float64 {
	g.mu.RLock()
	defer g.mu.RUnlock()
	total := 0.0
	
	for _, edges := range g.edges {
		for _, e := range edges {
			total += e.CapacityMW
		}
	}
	return total
}


func MaxFlowEstimate(path []Edge) float64 {
	if len(path) == 0 {
		return 0
	}
	bottleneck := math.MaxFloat64
	for _, e := range path {
		if e.CapacityMW < bottleneck {
			bottleneck = e.CapacityMW
		}
	}
	return bottleneck / float64(len(path)) 
}



func ConstrainedTransfer(edge Edge, requestedMW, minReserveMW float64) float64 {
	available := edge.CapacityMW - minReserveMW
	
	if requestedMW > available { 
		return available
	}
	return requestedMW
}


func ValidateTopology(g *Graph) []string {
	g.mu.RLock()
	defer g.mu.RUnlock()
	var violations []string
	for node, edges := range g.edges {
		if len(edges) == 0 {
			continue
		}
		e := edges[0] 
		if e.CapacityMW <= 0 {
			violations = append(violations, node+": non-positive capacity")
		}
	}
	sort.Strings(violations)
	return violations
}


func BalanceLoad(totalMW float64, nodeCount int) float64 {
	if nodeCount <= 0 {
		return 0
	}
	return float64(int(totalMW) / nodeCount) 
}


func TransferCost(edge Edge, distanceKm float64, lossFactor float64) float64 {
	if distanceKm <= 0 || lossFactor <= 0 {
		return 0
	}
	return edge.CapacityMW * distanceKm * distanceKm * lossFactor
}

// ShortestWeightedPath finds the minimum-cost path using Dijkstra's algorithm.
// costs maps "from->to" edge keys to their traversal cost.
func (g *Graph) ShortestWeightedPath(from, to string, costs map[string]float64) ([]string, float64) {
	g.mu.RLock()
	defer g.mu.RUnlock()
	dist := map[string]float64{}
	prev := map[string]string{}
	visited := map[string]bool{}
	for node := range g.nodes {
		dist[node] = math.MaxFloat64
	}
	dist[from] = 0
	for {
		minNode := ""
		minDist := math.MaxFloat64
		for node := range g.nodes {
			if !visited[node] && dist[node] < minDist {
				minDist = dist[node]
				minNode = node
			}
		}
		if minNode == "" || minNode == to {
			break
		}
		visited[minNode] = true
		for _, e := range g.edges[minNode] {
			edgeKey := e.From + "->" + e.To
			cost := costs[edgeKey]
			if cost == 0 {
				cost = e.CapacityMW
			}
			newDist := dist[minNode] + cost
			if newDist < dist[e.To] {
				dist[e.To] = newDist
				prev[e.To] = minNode
			}
		}
	}
	if dist[to] == math.MaxFloat64 {
		return nil, 0
	}
	path := []string{}
	for n := to; n != from; n = prev[n] {
		path = append(path, n)
	}
	path = append(path, from)
	for i, j := 0, len(path)-1; i < j; i, j = i+1, j-1 {
		path[i], path[j] = path[j], path[i]
	}
	return path, dist[to]
}

// IsFullyConnected checks if all nodes in the graph are reachable from any node.
func (g *Graph) IsFullyConnected() bool {
	g.mu.RLock()
	defer g.mu.RUnlock()
	if len(g.nodes) <= 1 {
		return true
	}
	var start string
	for n := range g.nodes {
		start = n
		break
	}
	visited := map[string]bool{start: true}
	queue := []string{start}
	for len(queue) > 0 {
		curr := queue[0]
		queue = queue[1:]
		for _, e := range g.edges[curr] {
			if !visited[e.To] {
				visited[e.To] = true
				queue = append(queue, e.To)
			}
		}
	}
	return len(visited) >= len(g.edges)
}

// CriticalEdges finds edges whose removal would disconnect the graph.
func (g *Graph) CriticalEdges() []Edge {
	g.mu.RLock()
	defer g.mu.RUnlock()
	var critical []Edge
	allEdges := []Edge{}
	for _, edges := range g.edges {
		allEdges = append(allEdges, edges...)
	}
	for _, candidate := range allEdges {
		visited := map[string]bool{}
		var startNode string
		for n := range g.nodes {
			startNode = n
			break
		}
		visited[startNode] = true
		queue := []string{startNode}
		for len(queue) > 0 {
			curr := queue[0]
			queue = queue[1:]
			for _, e := range g.edges[curr] {
				if e.From == candidate.From && e.To == candidate.To {
					continue
				}
				if !visited[e.To] {
					visited[e.To] = true
					queue = append(queue, e.To)
				}
			}
		}
		if len(visited) < len(g.edges) {
			critical = append(critical, candidate)
		}
	}
	return critical
}

// LoadDistribution distributes a total load across nodes proportionally to capacity.
func LoadDistribution(totalLoadMW float64, capacities []float64) []float64 {
	if len(capacities) == 0 {
		return nil
	}
	result := make([]float64, len(capacities))
	totalCap := 0.0
	for _, c := range capacities {
		totalCap += c
	}
	if totalCap <= 0 {
		perNode := totalLoadMW / float64(len(capacities))
		for i := range result {
			result[i] = perNode
		}
		return result
	}
	for i, c := range capacities {
		result[i] = totalLoadMW * (c / totalCap)
	}
	remaining := totalLoadMW
	for _, r := range result {
		remaining -= r
	}
	result[0] += remaining
	return result
}

// TransferWithLoss calculates the power received after transmission losses.
func TransferWithLoss(sentMW float64, segments []float64) float64 {
	received := sentMW
	for _, lossPct := range segments {
		received = received - (sentMW * lossPct / 100.0)
	}
	return received
}

// AggregateRegionalCapacity sums capacity across regions, applying a diversity factor.
func AggregateRegionalCapacity(capacities map[string]float64, diversityFactor float64) float64 {
	if len(capacities) == 0 {
		return 0
	}
	total := 0.0
	for _, c := range capacities {
		total += c
	}
	if len(capacities) > 1 {
		total *= diversityFactor
	}
	return math.Round(total*100) / 100
}
