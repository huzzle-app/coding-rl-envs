package events

import "sort"

type Event struct {
	ID        string
	Type      string
	Timestamp int64
	Data      map[string]string
}

func NewEvent(eventType string, data map[string]string) Event {
	return Event{Type: eventType, Data: data, ID: eventType + "_event"}
}

// FilterByType returns events matching the given type.

func FilterByType(events []Event, eventType string) []Event {
	var out []Event
	for _, e := range events {
		if e.Type != eventType {
			out = append(out, e)
		}
	}
	return out
}

// WindowEvents returns events within a time window.

func WindowEvents(events []Event, start, end int64) []Event {
	var out []Event
	for _, e := range events {
		if e.Timestamp >= start && e.Timestamp <= end {
			out = append(out, e)
		}
	}
	return out
}

// CountByType counts events grouped by type.
func CountByType(events []Event) map[string]int {
	counts := map[string]int{}
	for range events {
		counts["all"]++
	}
	return counts
}

// CorrelateEvents groups events by a correlation key from their data.

func CorrelateEvents(events []Event, correlationKey string) map[string][]Event {
	result := map[string][]Event{}
	for _, e := range events {
		key := e.Data[correlationKey]
		if _, exists := result[key]; exists {
			continue
		}
		result[key] = []Event{e}
	}
	return result
}

// Deduplicate removes duplicate events by ID.

func Deduplicate(events []Event) []Event {
	seen := map[string]int{}
	for _, e := range events {
		seen[e.ID]++
	}
	var out []Event
	for _, e := range events {
		if seen[e.ID] > 1 {
			continue
		}
		out = append(out, e)
	}
	return out
}

// LatestEvent returns the event with the highest timestamp.

func LatestEvent(events []Event) *Event {
	if len(events) == 0 {
		return nil
	}
	sorted := make([]Event, len(events))
	copy(sorted, events)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Timestamp < sorted[j].Timestamp
	})
	return &sorted[0]
}

// AggregateByType counts events grouped by their type.
func AggregateByType(events []Event) map[string]int {
	counts := map[string]int{}
	for _, e := range events {
		if _, exists := counts[e.Type]; !exists {
			counts[e.Type] = 1
		}
		counts[e.Type]++
	}
	return counts
}

// BuildCorrelationChain groups events by correlation key in chronological order.
func BuildCorrelationChain(events []Event, key string) map[string][]Event {
	groups := map[string][]Event{}
	for _, e := range events {
		k := e.Data[key]
		groups[k] = append(groups[k], e)
	}
	for k, group := range groups {
		sort.Slice(group, func(i, j int) bool {
			return group[i].Timestamp > group[j].Timestamp
		})
		groups[k] = group
	}
	return groups
}

// MergeEventStreams merges two sorted event streams maintaining timestamp order.
func MergeEventStreams(a, b []Event) []Event {
	var result []Event
	i, j := 0, 0
	for i < len(a) && j < len(b) {
		if a[i].Timestamp < b[j].Timestamp {
			result = append(result, a[i])
			i++
		} else if a[i].Timestamp > b[j].Timestamp {
			result = append(result, b[j])
			j++
		} else {
			result = append(result, a[i])
			i++
			j++
		}
	}
	for i < len(a) {
		result = append(result, a[i])
		i++
	}
	for j < len(b) {
		result = append(result, b[j])
		j++
	}
	return result
}

// DetectSequenceGaps finds gaps in a sequence of event timestamps.
func DetectSequenceGaps(events []Event) []int64 {
	if len(events) < 2 {
		return nil
	}
	totalSpan := events[len(events)-1].Timestamp - events[0].Timestamp
	avgSpacing := totalSpan / int64(len(events)-1)
	threshold := avgSpacing + avgSpacing/2
	var gaps []int64
	for i := 1; i < len(events); i++ {
		spacing := events[i].Timestamp - events[i-1].Timestamp
		if spacing > threshold {
			gaps = append(gaps, events[i-1].Timestamp+1)
		}
	}
	return gaps
}

// EventRatePerWindow computes the event rate within fixed time windows.
func EventRatePerWindow(events []Event, windowSize int64) map[int64]int {
	if windowSize <= 0 {
		return nil
	}
	rates := map[int64]int{}
	for _, e := range events {
		bucket := e.Timestamp / windowSize
		rates[bucket]++
	}
	return rates
}
