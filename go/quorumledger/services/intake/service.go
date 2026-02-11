package intake

import "quorumledger/internal/queue"

const Name = "intake"
const Role = "command intake"

func ShouldReject(depth, maxDepth int) bool {
	return queue.ShouldShed(depth, maxDepth, false)
}

func QueueStatus(depth, maxDepth int) string {
	return queue.QueueHealth(depth, maxDepth)
}

func WaitEstimate(position, avgMs int) int {
	return queue.EstimateWaitTime(position, avgMs)
}
