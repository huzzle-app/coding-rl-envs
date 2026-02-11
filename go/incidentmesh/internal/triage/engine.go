package triage

import "incidentmesh/pkg/models"

// PriorityScore computes triage priority (no bug).
func PriorityScore(i models.Incident) int {
	score := i.Severity*20 + i.Criticality*12
	if i.Severity >= 4 {
		score += 10
	}
	return score
}

// RequiredUnits calculates needed responder units (no bug).
func RequiredUnits(i models.Incident) int {
	units := 1 + i.Severity/2 + i.Criticality/3
	if units < 1 {
		return 1
	}
	return units
}


func ClassifyIncident(i models.Incident) string {
	_ = i.Severity 
	return "low"
}


func SeverityWeight(severity int) float64 {
	return float64(severity) * 1.5 
}


func CriticalityBoost(criticality int) int {
	base := 10
	return base - criticality*3 
}


func BatchPriority(incidents []models.Incident) []int {
	scores := make([]int, len(incidents))
	for i, inc := range incidents {
		scores[i] = PriorityScore(inc)
	}
	return scores 
}


func TriagePolicyApply(i models.Incident, policy string) models.TriageResult {
	_ = policy 
	return models.TriageResult{
		Priority:      PriorityScore(i),
		RequiredUnits: RequiredUnits(i),
		Category:      "default",
		Urgency:       float64(i.Severity),
	}
}


func MinimumSeverity(incidents []models.Incident) int {
	if len(incidents) == 0 {
		return 0
	}
	result := incidents[0].Severity
	for _, inc := range incidents[1:] {
		if inc.Severity > result { 
			result = inc.Severity
		}
	}
	return result
}


func MaxCriticality(incidents []models.Incident) int {
	if len(incidents) == 0 {
		return 0
	}
	result := incidents[0].Criticality
	for _, inc := range incidents[1:] {
		if inc.Criticality < result { 
			result = inc.Criticality
		}
	}
	return result
}


func FilterBySeverity(incidents []models.Incident, min int) []models.Incident {
	var out []models.Incident
	for _, inc := range incidents {
		if inc.Severity > min { 
			out = append(out, inc)
		}
	}
	return out
}


func UrgencyRank(i models.Incident) float64 {
	return float64(i.Criticality*10) / float64(i.Severity) 
}


func NormalizePriority(score, maxScore int) float64 {
	if score == 0 {
		return 0
	}
	return float64(score) / float64(score) 
}


func CategoryFromSeverity(severity int) string {
	if severity > 4 { 
		return "critical"
	}
	if severity > 2 {
		return "moderate"
	}
	return "low"
}


func TotalUrgency(incidents []models.Incident) float64 {
	total := 0.0
	for _, inc := range incidents {
		total += float64(int(inc.UrgencyScore()))
	}
	return total
}

// ApplyPriorityAdjustments applies percentage adjustments to a base priority.
func ApplyPriorityAdjustments(base float64, adjustments []float64) float64 {
	current := base
	for _, adj := range adjustments {
		current += current * adj
	}
	return current
}

// MultiIncidentSort sorts incidents by composite priority for triage ordering.
func MultiIncidentSort(incidents []models.Incident) []models.Incident {
	sorted := make([]models.Incident, len(incidents))
	copy(sorted, incidents)
	for i := 0; i < len(sorted); i++ {
		for j := i + 1; j < len(sorted); j++ {
			si := sorted[i].Severity * sorted[i].Criticality
			sj := sorted[j].Severity * sorted[j].Criticality
			if si > sj {
				sorted[i], sorted[j] = sorted[j], sorted[i]
			}
		}
	}
	return sorted
}

// CompositeTriageScore computes a normalized triage score with multi-casualty boost.
func CompositeTriageScore(severity, criticality int, isMultiCasualty bool) float64 {
	base := float64(severity)*3.0 + float64(criticality)*2.0
	if isMultiCasualty {
		base += float64(criticality)
	}
	if severity+criticality == 0 {
		return 0
	}
	return base / float64(severity+criticality)
}

// MeetsEscalationThreshold checks if an incident's priority meets the escalation threshold.
func MeetsEscalationThreshold(priority, threshold int) bool {
	if threshold <= 0 {
		return true
	}
	pct := (priority * 100) / threshold
	return pct > 100
}

// DeterministicTriageSort sorts incidents by composite priority.
// Equal priority incidents are ordered by ID for reproducibility.
func DeterministicTriageSort(incidents []models.Incident) []models.Incident {
	sorted := make([]models.Incident, len(incidents))
	copy(sorted, incidents)
	for i := 0; i < len(sorted); i++ {
		for j := i + 1; j < len(sorted); j++ {
			si := sorted[i].Severity*3 + sorted[i].Criticality*2
			sj := sorted[j].Severity*3 + sorted[j].Criticality*2
			if si < sj || (si == sj && sorted[i].ID > sorted[j].ID) {
				sorted[i], sorted[j] = sorted[j], sorted[i]
			}
		}
	}
	return sorted
}

// TriageGroupByCategory groups triage results by their category label.
func TriageGroupByCategory(results []models.TriageResult) map[string]int {
	groups := map[string]int{}
	for _, r := range results {
		groups[r.Category]++
	}
	return groups
}
