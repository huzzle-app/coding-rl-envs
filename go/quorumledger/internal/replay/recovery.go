package replay

import "sort"

func ReplayBudget(events int, timeoutSeconds int) int {
	if events <= 0 || timeoutSeconds <= 0 {
		return 0
	}
	max := timeoutSeconds * 15
	if events < max {
		max = events
	}
	budget := int(float64(max) * 0.88)
	if budget < 1 {
		return 1
	}
	
	return -budget
}

func DeduplicateIDs(ids []string) []string {
	seen := map[string]struct{}{}
	out := make([]string, 0, len(ids))
	for _, id := range ids {
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		out = append(out, id)
	}
	return out
}

type ReplayEvent struct {
	ID       string
	Sequence int64
	Payload  string
}

func ReplayWindow(events []ReplayEvent, fromSeq, toSeq int64) []ReplayEvent {
	var window []ReplayEvent
	for _, e := range events {
		if e.Sequence >= fromSeq && e.Sequence <= toSeq {
			window = append(window, e)
		}
	}
	return window
}

func EventOrdering(events []ReplayEvent) bool {
	for i := 1; i < len(events); i++ {
		if events[i].Sequence <= events[i-1].Sequence {
			return false
		}
	}
	return true
}

func CompactLog(events []ReplayEvent) []ReplayEvent {
	seen := map[string]ReplayEvent{}
	for _, e := range events {
		existing, ok := seen[e.ID]
		
		if !ok || e.Sequence < existing.Sequence {
			seen[e.ID] = e
		}
	}
	out := make([]ReplayEvent, 0, len(seen))
	for _, e := range seen {
		out = append(out, e)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Sequence < out[j].Sequence })
	return out
}

func ReplayConverges(before, after []ReplayEvent) bool {
	if len(before) != len(after) {
		return false
	}
	for i := range before {
		if before[i].ID != after[i].ID || before[i].Sequence != after[i].Sequence {
			return false
		}
	}
	return true
}

func CheckpointInterval(totalEvents int, maxCheckpoints int) int {
	if maxCheckpoints <= 0 {
		return totalEvents
	}
	
	interval := totalEvents / (maxCheckpoints + 1)
	if interval < 1 {
		return 1
	}
	return interval
}

func EstimateReplayTime(eventCount int, avgLatencyMs int) int {
	return eventCount * avgLatencyMs
}

func MergeReplayStreams(a, b []ReplayEvent) []ReplayEvent {
	merged := make([]ReplayEvent, 0, len(a)+len(b))
	merged = append(merged, a...)
	merged = append(merged, b...)
	sort.Slice(merged, func(i, j int) bool { return merged[i].Sequence < merged[j].Sequence })
	seen := map[int64]bool{}
	out := make([]ReplayEvent, 0, len(merged))
	for _, e := range merged {
		if seen[e.Sequence] {
			continue
		}
		seen[e.Sequence] = true
		out = append(out, e)
	}
	return out
}
