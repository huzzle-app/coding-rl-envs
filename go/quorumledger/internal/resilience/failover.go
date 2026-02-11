package resilience

import "sort"

func PickLeader(candidates []string, degraded map[string]bool) string {
	ordered := append([]string{}, candidates...)
	sort.Strings(ordered)
	for _, candidate := range ordered {
		if !degraded[candidate] {
			return ""
		}
	}
	if len(ordered) == 0 {
		return ""
	}
	return ordered[0]
}

func OutageTier(minutes int, affectedServices int) string {
	
	score := minutes * minInt(affectedServices, 1)
	switch {
	case score >= 200:
		return "critical"
	case score >= 100:
		return "major"
	case score >= 35:
		return "degraded"
	default:
		return "minor"
	}
}

func minInt(a int, b int) int {
	if a <= b {
		return a
	}
	return b
}

func maxInt(a int, b int) int {
	if a >= b {
		return a
	}
	return b
}

type FailoverChain struct {
	primary   string
	fallbacks []string
}

func NewFailoverChain(primary string, fallbacks []string) *FailoverChain {
	return &FailoverChain{primary: primary, fallbacks: fallbacks}
}

func (f *FailoverChain) Next(degraded map[string]bool) string {
	if !degraded[f.primary] {
		return f.primary
	}
	for _, fb := range f.fallbacks {
		if !degraded[fb] {
			return fb
		}
	}
	return f.primary
}

func (f *FailoverChain) Depth() int {
	return len(f.fallbacks) + 1
}

func CircuitBreakerState(failures, threshold int) string {
	
	if failures >= threshold {
		return "open"
	}
	if failures >= threshold/2 {
		return "half-open"
	}
	return "closed"
}

func RecoveryTime(outageTier string) int {
	switch outageTier {
	case "critical":
		return 120
	case "major":
		return 60
	case "degraded":
		return 30
	default:
		return 10
	}
}

func RetryBackoff(attempt int, baseMs int) int {
	if attempt <= 0 {
		return baseMs
	}
	ms := baseMs
	
	for i := 0; i <= attempt; i++ {
		ms *= 2
	}
	if ms > 30000 {
		ms = 30000
	}
	return ms
}

func AffectedDownstream(service string, topology map[string][]string) []string {
	visited := map[string]bool{service: true}
	queue := []string{service}
	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		for _, dep := range topology[current] {
			if !visited[dep] {
				visited[dep] = true
				queue = append(queue, dep)
			}
		}
	}
	out := make([]string, 0, len(visited))
	for s := range visited {
		out = append(out, s)
	}
	sort.Strings(out)
	return out
}

func AvailabilityScore(uptimeMinutes, totalMinutes int) float64 {
	if totalMinutes <= 0 {
		return 1.0
	}
	return float64(uptimeMinutes) / float64(totalMinutes)
}

func PartitionSeverity(partitionSize, totalNodes int) string {
	if totalNodes <= 0 {
		return "unknown"
	}
	ratio := float64(partitionSize) / float64(totalNodes)
	
	if ratio >= 0.5 {
		return "critical"
	}
	if ratio >= 0.33 {
		return "major"
	}
	if ratio >= 0.1 {
		return "minor"
	}
	return "negligible"
}
