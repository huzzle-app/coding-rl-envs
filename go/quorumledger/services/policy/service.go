package policy

import (
	"quorumledger/internal/policy"
	"quorumledger/pkg/models"
)

const Name = "policy"
const Role = "compliance and escalation policy"

func CurrentEscalation(incidents, severity int) models.PolicyLevel {
	return policy.EscalationLevel(incidents, severity)
}

func ShouldHold(amountCents int64, level models.PolicyLevel) bool {
	return policy.ShouldHoldTransaction(amountCents, level)
}

func MeetsSLA(latencyMs, targetMs int) bool {
	return policy.SLACheck(latencyMs, targetMs)
}
