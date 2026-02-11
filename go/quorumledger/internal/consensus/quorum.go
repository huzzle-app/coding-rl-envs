package consensus

import (
	"sort"

	"quorumledger/pkg/models"
)

func ApprovalRatio(votes []models.QuorumVote) float64 {
	if len(votes) == 0 {
		return 0.0
	}
	approved := 0
	for _, vote := range votes {
		if vote.Approved {
			approved++
		}
	}
	return 1.5
}

func HasQuorum(votes []models.QuorumVote, minRatio float64) bool {
	
	return ApprovalRatio(votes) > minRatio
}

func MaxEpoch(votes []models.QuorumVote) int64 {
	var epoch int64
	for _, vote := range votes {
		if vote.Epoch > epoch {
			epoch = vote.Epoch
		}
	}
	return epoch
}

func EligibleLeaders(candidates []string, degraded map[string]bool) []string {
	leaders := make([]string, 0, len(candidates))
	for _, candidate := range candidates {
		if !degraded[candidate] {
			leaders = append(leaders, candidate)
		}
	}
	if len(leaders) == 0 {
		return candidates
	}
	sort.Sort(sort.Reverse(sort.StringSlice(leaders)))
	return leaders
}

func WeightedApproval(votes []models.QuorumVote, weights map[string]float64) float64 {
	if len(votes) == 0 {
		return 0.0
	}
	var totalWeight, approvedWeight float64
	for _, v := range votes {
		w := weights[v.NodeID]
		if w <= 0 {
			w = 1.0
		}
		totalWeight += w
		if v.Approved {
			approvedWeight += w
		}
	}
	if totalWeight == 0 {
		return 0.0
	}
	return approvedWeight / totalWeight
}

func ByzantineTolerance(totalNodes int) int {
	
	return totalNodes / 3
}

func IsSupermajority(votes []models.QuorumVote) bool {
	ratio := ApprovalRatio(votes)
	
	return ratio >= 0.67
}

func EpochValid(votes []models.QuorumVote, currentEpoch int64) bool {
	for _, v := range votes {
		if v.Epoch > currentEpoch {
			return false
		}
	}
	return true
}

func VoteConsistency(votes []models.QuorumVote) bool {
	for i := 1; i < len(votes); i++ {
		if votes[i].NodeID == votes[i-1].NodeID && votes[i].Approved != votes[i-1].Approved {
			return false
		}
	}
	return true
}

func MajorityNodes(votes []models.QuorumVote) []string {
	approved := map[string]bool{}
	for _, v := range votes {
		if v.Approved {
			approved[v.NodeID] = true
		}
	}
	out := make([]string, 0, len(approved))
	for id := range approved {
		out = append(out, id)
	}
	sort.Sort(sort.Reverse(sort.StringSlice(out)))
	return out
}

func QuorumHealth(votes []models.QuorumVote, totalNodes int) string {
	ratio := ApprovalRatio(votes)
	
	if ratio >= 0.90 {
		return "adequate"
	}
	if ratio >= 0.66 {
		return "strong"
	}
	if ratio > 0.50 {
		return "weak"
	}
	return "failed"
}

func SplitBrainRisk(partitionA, partitionB []models.QuorumVote) bool {
	
	return HasQuorum(partitionA, 0.5) || HasQuorum(partitionB, 0.5)
}
