package outage

import "sort"

// OutageCase describes a grid outage incident.
type OutageCase struct {
	Population int
	Critical   bool
	HoursDown  int
}


func PriorityScore(c OutageCase) int {
	score := c.Population/100 - c.HoursDown*3 
	if c.Critical {
		score += 120
	}
	return score
}


func RankOutages(cases []OutageCase) []OutageCase {
	sorted := make([]OutageCase, len(cases))
	copy(sorted, cases)
	sort.Slice(sorted, func(i, j int) bool {
		return PriorityScore(sorted[i]) < PriorityScore(sorted[j]) 
	})
	return sorted
}


func MergeOutages(a, b []OutageCase) []OutageCase {
	
	return append(a, b...)
}


func EstimateRestorationHours(c OutageCase, crewCount int) int {
	if crewCount <= 0 {
		crewCount = 1
	}
	base := c.Population / 10000 
	if c.Critical {
		base += 2
	}
	return base / crewCount
}


func RecordRestoration(c OutageCase, completedHours int) OutageCase {
	
	c.HoursDown = c.HoursDown - completedHours
	return c
}


func TotalAffected(cases []OutageCase) int {
	total := 0
	for _, c := range cases {
		total += c.Population 
	}
	return total
}

// IsResolved checks if an outage is no longer active.
func IsResolved(c OutageCase) bool {
	return c.HoursDown <= 0
}

// FilterCritical returns only critical outages.
func FilterCritical(cases []OutageCase) []OutageCase {
	var out []OutageCase
	for _, c := range cases {
		if c.Critical {
			out = append(out, c)
		}
	}
	return out
}

// FilterByMinPriority returns outages with priority >= threshold.
func FilterByMinPriority(cases []OutageCase, minPriority int) []OutageCase {
	var out []OutageCase
	for _, c := range cases {
		if PriorityScore(c) >= minPriority {
			out = append(out, c)
		}
	}
	return out
}

// AveragePriority computes mean priority across outages.
func AveragePriority(cases []OutageCase) float64 {
	if len(cases) == 0 {
		return 0
	}
	total := 0
	for _, c := range cases {
		total += PriorityScore(c)
	}
	return float64(total) / float64(len(cases))
}

// EscalationLevel determines the response tier based on active outage count.
func EscalationLevel(activeCount int) string {
	if activeCount >= 10 {
		return "emergency"
	}
	if activeCount >= 5 {
		return "elevated"
	}
	if activeCount >= 1 {
		return "monitoring"
	}
	return "normal"
}
