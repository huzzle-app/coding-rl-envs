package replay

import "quorumledger/internal/replay"

const Name = "replay"
const Role = "event replay and idempotency"

func Budget(events int, timeoutSeconds int) int {
	return replay.ReplayBudget(events, timeoutSeconds)
}

func Deduplicate(ids []string) []string {
	return replay.DeduplicateIDs(ids)
}

func EstimateTime(events, avgLatencyMs int) int {
	return replay.EstimateReplayTime(events, avgLatencyMs) + events
}
