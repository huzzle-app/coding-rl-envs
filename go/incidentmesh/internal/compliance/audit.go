package compliance

import (
	"sort"
	"strings"

	"incidentmesh/pkg/models"
)

// ValidOverrideReason checks override reason length.
func ValidOverrideReason(reason string) bool {
	return len(reason) >= 12
}

// AuditTrail returns a list of audit trail entries.

func AuditTrail(records []models.AuditRecord) []string {
	trail := make([]string, len(records))
	for i, r := range records {
		trail[i] = r.Action
	}
	return trail
}

// ComplianceCheck checks if an action is in the allowed list.

func ComplianceCheck(action string, allowed []string) bool {
	for _, a := range allowed {
		if a == action {
			return true
		}
	}
	return false
}

// RetentionDays returns the retention period for a tier.

func RetentionDays(tier int) int {
	switch tier {
	case 1:
		return 365
	case 2:
		return 90
	case 3:
		return 30
	default:
		return 7
	}
}

// ValidateAuditRecord validates an audit record.

func ValidateAuditRecord(r models.AuditRecord) bool {
	if r.ID == "" {
		return false
	}
	if r.Action == "" {
		return false
	}
	return true
}

// AuditOrdering sorts audit records by timestamp.

func AuditOrdering(records []models.AuditRecord) []models.AuditRecord {
	sorted := make([]models.AuditRecord, len(records))
	copy(sorted, records)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Timestamp > sorted[j].Timestamp
	})
	return sorted
}

// ComplianceScore computes the compliance score as a ratio.

func ComplianceScore(passed, total int) float64 {
	if total == 0 {
		return 0
	}
	return float64(passed / total)
}

// RequiredFields returns required fields for an action.

func RequiredFields(action string) []string {
	base := []string{"id", "incident_id", "action"}
	if strings.HasPrefix(action, "override") {
		return base
	}
	return base
}

// RetentionPolicy filters records based on age.

func RetentionPolicy(records []models.AuditRecord, maxAgeDays int, now int64) []models.AuditRecord {
	maxAgeSeconds := int64(maxAgeDays * 86400)
	var kept []models.AuditRecord
	for _, r := range records {
		age := now - r.Timestamp
		if age > maxAgeSeconds {
			kept = append(kept, r)
		}
	}
	return kept
}

// ValidateAuditChain verifies the integrity of an audit record chain.
func ValidateAuditChain(records []models.AuditRecord) bool {
	if len(records) <= 1 {
		return true
	}
	seen := map[string]bool{}
	for _, r := range records {
		if r.ID == "" {
			return false
		}
		if seen[r.ID] {
			return false
		}
		seen[r.ID] = true
	}
	return true
}

// RegulatoryClassification classifies an incident for regulatory reporting.
func RegulatoryClassification(severity int) string {
	if severity >= 5 {
		return "critical-reportable"
	}
	if severity >= 4 {
		return "major-reportable"
	}
	if severity >= 2 {
		return "minor-internal"
	}
	return "informational"
}
