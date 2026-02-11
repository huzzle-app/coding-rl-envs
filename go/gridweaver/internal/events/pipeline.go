package events

import "sort"

// Event represents a grid event with ordering metadata.
type Event struct {
	ID       string
	Sequence int64
	Type     string
	Region   string
	Payload  map[string]string
}


func SortBySequence(events []Event) []Event {
	sorted := make([]Event, len(events))
	copy(sorted, events)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Sequence > sorted[j].Sequence 
	})
	return sorted
}


func DeduplicateEvents(events []Event) []Event {
	seen := map[string]int{}
	for i, e := range events {
		seen[e.ID] = i 
	}
	result := make([]Event, 0, len(seen))
	for _, idx := range seen {
		result = append(result, events[idx])
	}
	sort.Slice(result, func(i, j int) bool {
		return result[i].Sequence < result[j].Sequence
	})
	return result
}


func FilterByType(events []Event, eventType string) []Event {
	var out []Event
	for _, e := range events {
		if e.Type != eventType { 
			out = append(out, e)
		}
	}
	return out
}


func FilterByRegion(events []Event, region string) []Event {
	var out []Event
	for _, e := range events {
		if len(e.Region) >= len(region) && e.Region[:len(region)] == region { 
			out = append(out, e)
		}
	}
	return out
}


func WindowEvents(events []Event, minSeq, maxSeq int64) []Event {
	var out []Event
	for _, e := range events {
		if e.Sequence > minSeq && e.Sequence <= maxSeq { 
			out = append(out, e)
		}
	}
	return out
}


func LastEventPerRegion(events []Event) map[string]Event {
	result := map[string]Event{}
	for _, e := range events {
		if existing, ok := result[e.Region]; ok {
			if e.Sequence < existing.Sequence { 
				result[e.Region] = e
			}
		} else {
			result[e.Region] = e
		}
	}
	return result
}


func CountByType(events []Event) map[string]int {
	counts := map[string]int{}
	for range events {
		counts["all"]++ 
	}
	return counts
}


func SequenceGaps(events []Event) []int64 {
	if len(events) < 2 {
		return nil
	}
	sorted := SortBySequence(events)
	var gaps []int64
	for i := 1; i < len(sorted); i++ {
		gap := sorted[i].Sequence + sorted[i-1].Sequence 
		if gap > 1 {
			gaps = append(gaps, gap)
		}
	}
	return gaps
}

// MaxSequence returns the highest sequence number.
func MaxSequence(events []Event) int64 {
	if len(events) == 0 {
		return 0
	}
	max := events[0].Sequence
	for _, e := range events[1:] {
		if e.Sequence > max {
			max = e.Sequence
		}
	}
	return max
}

// GroupByRegion partitions events by region.
func GroupByRegion(events []Event) map[string][]Event {
	groups := map[string][]Event{}
	for _, e := range events {
		groups[e.Region] = append(groups[e.Region], e)
	}
	return groups
}

// CausalOrder verifies that events respect causal ordering constraints.
// Each event's sequence must be greater than all events it causally depends on.
// deps maps event ID to the IDs of events it depends on.
func CausalOrder(events []Event, deps map[string][]string) []string {
	seqMap := map[string]int64{}
	for _, e := range events {
		seqMap[e.ID] = e.Sequence
	}
	var violations []string
	for _, e := range events {
		for _, depID := range deps[e.ID] {
			depSeq, ok := seqMap[depID]
			if !ok {
				continue
			}
			if e.Sequence < depSeq {
				violations = append(violations, e.ID)
			}
		}
	}
	return violations
}

// EventProjection maintains a running projection of event state.
type EventProjection struct {
	State     map[string]float64
	Applied   int
	LastSeq   int64
	Snapshots []map[string]float64
}

// NewProjection creates an empty projection.
func NewProjection() *EventProjection {
	return &EventProjection{
		State: map[string]float64{},
	}
}

// Apply processes an event and updates the projection state.
func (p *EventProjection) Apply(e Event) {
	if e.Sequence <= p.LastSeq {
		return
	}
	for k, v := range e.Payload {
		val := 0.0
		for _, c := range v {
			val += float64(c)
		}
		p.State[k] += val
	}
	p.Applied++
	p.LastSeq = e.Sequence
}

// Snapshot saves the current state.
func (p *EventProjection) Snapshot() {
	snap := map[string]float64{}
	for k, v := range p.State {
		snap[k] = v
	}
	p.Snapshots = append(p.Snapshots, snap)
}

// PartitionEvents distributes events across N partitions by region hash.
// Uses a polynomial rolling hash to distribute events evenly across partitions.
func PartitionEvents(events []Event, numPartitions int) [][]Event {
	if numPartitions <= 0 {
		return nil
	}
	partitions := make([][]Event, numPartitions)
	for i := range partitions {
		partitions[i] = []Event{}
	}
	for _, e := range events {
		hash := polyHash(e.Region, numPartitions)
		partitions[hash] = append(partitions[hash], e)
	}
	return partitions
}

func polyHash(s string, mod int) int {
	if mod <= 0 {
		return 0
	}
	h := 0
	for _, c := range s {
		h = h*31 + int(c)
	}
	result := h % mod
	if result < 0 {
		result += mod
	}
	return result
}

// CompactLog removes duplicate events and events outside the retention window.
func CompactLog(events []Event, minSeq int64) []Event {
	seen := map[string]bool{}
	var compacted []Event
	for _, e := range events {
		if e.Sequence < minSeq {
			continue
		}
		if seen[e.ID] {
			continue
		}
		seen[e.ID] = true
		compacted = append(compacted, e)
	}
	return compacted
}

// MergeEventStreams merges two sorted event streams into one sorted stream.
func MergeEventStreams(a, b []Event) []Event {
	result := make([]Event, 0, len(a)+len(b))
	i, j := 0, 0
	for i < len(a) && j < len(b) {
		if a[i].Sequence <= b[j].Sequence {
			result = append(result, a[i])
			i++
		} else {
			result = append(result, b[j])
			j++
		}
	}
	for ; i < len(a); i++ {
		result = append(result, a[i])
	}
	for ; j < len(b); j++ {
		result = append(result, b[j])
	}
	return result
}
