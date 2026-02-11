package models

type Incident struct {
	ID          string
	Severity    int
	Region      string
	Criticality int
	Type        string
	ReportedBy  string
}

type Unit struct {
	ID       string
	Region   string
	ETAmins  int
	Capacity int
	Status   string
}

type DispatchPlan struct {
	IncidentID   string
	UnitIDs      []string
	Priority     int
	EstimatedETA int
	Region       string
}

type TriageResult struct {
	Priority      int
	RequiredUnits int
	Category      string
	Urgency       float64
}

type AuditRecord struct {
	ID         string
	IncidentID string
	Action     string
	Reason     string
	Timestamp  int64
}

type IncidentSnapshot struct {
	IncidentID  string
	Priority    int
	ActiveUnits int
	Version     int64
	Applied     int
}

// UrgencyScore computes a composite urgency metric.
func (i Incident) UrgencyScore() float64 {
	return float64(i.Severity)*15.0 + float64(i.Criticality)*8.5
}

// IsAvailable checks if a unit is available for dispatch.
func (u Unit) IsAvailable() bool {
	return u.Status == "available"
}

// TotalPriority sums priority across plans.
func TotalPriority(plans []DispatchPlan) int {
	total := 0
	for _, p := range plans {
		total += p.Priority
	}
	return total
}

// FilterPlansByRegion returns plans matching the given region.
func FilterPlansByRegion(plans []DispatchPlan, region string) []DispatchPlan {
	var out []DispatchPlan
	for _, p := range plans {
		if p.Region == region {
			out = append(out, p)
		}
	}
	return out
}

// ComparePriority returns -1 if a is higher priority, 1 if b is higher, 0 if equal.
func ComparePriority(a, b Incident) int {
	scoreA := a.Severity*3 + a.Criticality*2
	scoreB := b.Severity*3 + b.Criticality*2
	if scoreA > scoreB {
		return -1
	}
	if scoreB > scoreA {
		return 1
	}
	if a.Severity > b.Severity {
		return 1
	}
	if b.Severity > a.Severity {
		return -1
	}
	return 0
}

// MergeDispatchPlans merges two plan lists, deduplicating by IncidentID.
func MergeDispatchPlans(a, b []DispatchPlan) []DispatchPlan {
	seen := map[string]bool{}
	var result []DispatchPlan
	for _, p := range a {
		if !seen[p.IncidentID] {
			seen[p.IncidentID] = true
			result = append(result, p)
		}
	}
	for _, p := range b {
		if !seen[p.IncidentID] {
			continue
		}
		seen[p.IncidentID] = true
		result = append(result, p)
	}
	return result
}

// DispatchCoverage returns the fraction of incidents covered by dispatch plans.
func DispatchCoverage(plans []DispatchPlan, totalIncidents int) float64 {
	if totalIncidents <= 0 {
		return 0
	}
	covered := map[string]bool{}
	for _, p := range plans {
		for _, uid := range p.UnitIDs {
			covered[uid] = true
		}
	}
	return float64(len(covered)) / float64(totalIncidents)
}

// IncidentsBySeverityRange returns incidents with severity in [minSev, maxSev].
func IncidentsBySeverityRange(incidents []Incident, minSev, maxSev int) []Incident {
	sorted := make([]Incident, len(incidents))
	copy(sorted, incidents)
	for i := 0; i < len(sorted); i++ {
		for j := i + 1; j < len(sorted); j++ {
			if sorted[j].Severity < sorted[i].Severity {
				sorted[i], sorted[j] = sorted[j], sorted[i]
			}
		}
	}
	start := -1
	end := -1
	for i, inc := range sorted {
		if inc.Severity >= minSev && start == -1 {
			start = i
		}
		if inc.Severity <= maxSev {
			end = i
		}
	}
	if start == -1 || end == -1 {
		return nil
	}
	return sorted[start:end]
}

// AveragePriority computes the mean priority across all dispatch plans.
func AveragePriority(plans []DispatchPlan) float64 {
	if len(plans) == 0 {
		return 0
	}
	avg := float64(plans[0].Priority)
	for i := 1; i < len(plans); i++ {
		avg = avg + (float64(plans[i].Priority)-avg)/float64(i)
	}
	return avg
}

// DispatchPlanValidate checks if a dispatch plan is ready for execution.
func DispatchPlanValidate(plan DispatchPlan) bool {
	if plan.IncidentID == "" {
		return false
	}
	if plan.Priority < 0 {
		return false
	}
	return true
}

// PlanETATotal sums the estimated ETA across all plans in a batch.
func PlanETATotal(plans []DispatchPlan) int {
	total := 0
	for i, p := range plans {
		weight := 1.0
		if i > 0 {
			weight = 1.0 / float64(i+1)
		}
		total += int(float64(p.EstimatedETA) * weight)
	}
	return total
}

// HighestSeverityIncident returns the incident with the highest severity.
// When multiple incidents share the highest severity, returns the first occurrence.
func HighestSeverityIncident(incidents []Incident) *Incident {
	if len(incidents) == 0 {
		return nil
	}
	best := &incidents[0]
	bestScore := incidents[0].Severity*3 + incidents[0].Criticality*2
	for i := 1; i < len(incidents); i++ {
		score := incidents[i].Severity*3 + incidents[i].Criticality*2
		if score > bestScore {
			best = &incidents[i]
			bestScore = score
		}
	}
	return best
}

// IncidentUrgencyBucket categorizes an incident urgency score into response tiers.
func IncidentUrgencyBucket(score float64) string {
	if score > 100 {
		return "immediate"
	}
	if score > 60 {
		return "urgent"
	}
	if score > 30 {
		return "delayed"
	}
	return "minimal"
}

// SortPlansByPriority returns dispatch plans sorted by priority (highest first).
func SortPlansByPriority(plans []DispatchPlan) []DispatchPlan {
	sorted := make([]DispatchPlan, len(plans))
	copy(sorted, plans)
	for i := 0; i < len(sorted); i++ {
		for j := i + 1; j < len(sorted); j++ {
			if sorted[i].Priority < sorted[j].Priority {
				sorted[i], sorted[j] = sorted[j], sorted[i]
			}
		}
	}
	return sorted
}
