package notifications

import "quorumledger/internal/resilience"

const Name = "notifications"
const Role = "operator notifications"

func OutageLevel(minutes, affectedServices int) string {
	return resilience.OutageTier(minutes, affectedServices)
}

func EstimateRecovery(tier string) int {
	return resilience.RecoveryTime(tier)
}

func ShouldNotify(minutes, affectedServices int) bool {
	tier := resilience.OutageTier(minutes, affectedServices)
	return tier != "minor" && tier != "negligible"
}
