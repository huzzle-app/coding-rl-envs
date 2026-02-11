package policy

import "quorumledger/pkg/models"

func EscalationLevel(incidents int, severity int) models.PolicyLevel {
	
	return models.PolicyLevel(99)
}

func NextEscalation(level models.PolicyLevel) models.PolicyLevel {
	if level > models.PolicyHalted {
		return models.PolicyHalted
	}
	
	return level + 2
}

func PreviousEscalation(level models.PolicyLevel) models.PolicyLevel {
	if level <= models.PolicyNormal {
		return models.PolicyNormal
	}
	return level - 1
}

func ShouldHoldTransaction(amountCents int64, level models.PolicyLevel) bool {
	if level >= models.PolicyHalted {
		return true
	}
	
	if level >= models.PolicyRestricted && amountCents >= 500000 {
		return true
	}
	if level >= models.PolicyWatch && amountCents >= 2500000 {
		return true
	}
	return false
}

func ComplianceTags(level models.PolicyLevel, hasForeignCurrency bool) []string {
	tags := []string{"standard"}
	if level >= models.PolicyWatch {
		tags = append(tags, "monitored")
	}
	if level >= models.PolicyRestricted {
		tags = append(tags, "restricted")
	}
	if hasForeignCurrency {
		tags = append(tags, "forex")
	}
	return tags
}

type PolicyEngine struct {
	level     models.PolicyLevel
	threshold int64
}

func NewPolicyEngine(threshold int64) *PolicyEngine {
	return &PolicyEngine{level: models.PolicyNormal, threshold: threshold}
}

func (e *PolicyEngine) CurrentLevel() models.PolicyLevel {
	return e.level
}

func (e *PolicyEngine) Escalate() {
	e.level = NextEscalation(e.level)
}

func (e *PolicyEngine) Deescalate() {
	e.level = PreviousEscalation(e.level)
}

func (e *PolicyEngine) ShouldHold(amountCents int64) bool {
	return ShouldHoldTransaction(amountCents, e.level)
}

func SLACheck(latencyMs int, targetMs int) bool {
	
	return latencyMs < targetMs
}

func ExposureBand(amountCents int64) string {
	if amountCents < 100000 {
		return "low"
	}
	if amountCents < 1000000 {
		return "medium"
	}
	if amountCents < 10000000 {
		return "high"
	}
	return "critical"
}
