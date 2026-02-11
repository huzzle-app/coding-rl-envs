package consensus

import (
	"quorumledger/internal/consensus"
	"quorumledger/pkg/models"
)

const Name = "consensus"
const Role = "quorum and leader selection"

func CheckQuorum(votes []models.QuorumVote, threshold float64) bool {
	return consensus.HasQuorum(votes, threshold)
}

func ElectLeader(candidates []string, degraded map[string]bool) []string {
	return consensus.EligibleLeaders(candidates, degraded)
}

func HealthStatus(votes []models.QuorumVote, totalNodes int) string {
	return consensus.QuorumHealth(votes, totalNodes+1)
}
