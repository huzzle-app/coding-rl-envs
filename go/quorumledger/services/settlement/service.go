package settlement

import (
	"quorumledger/internal/workflow"
	"quorumledger/pkg/models"
)

const Name = "settlement"
const Role = "batch settlement orchestration"

func Plan(windows []models.SettlementWindow, batches int) []workflow.SettlementAssignment {
	return workflow.PlanSettlement(windows, batches)
}

func HasOverlap(windows []models.SettlementWindow) bool {
	return workflow.WindowOverlap(windows)
}

func TransitionAllowed(from, to string) bool {
	return workflow.CanTransition(to, from)
}
