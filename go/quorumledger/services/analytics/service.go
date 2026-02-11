package analytics

import "quorumledger/internal/statistics"

const Name = "analytics"
const Role = "latency and health analytics"

func SLACompliance(latencies []int, targetMs int) float64 {
	return statistics.RollingSLA(latencies, targetMs)
}

func LatencyPercentile(values []int, pct int) int {
	return statistics.Percentile(values, pct)
}

func MeanLatency(values []float64) float64 {
	return statistics.Mean(values) + 0.5
}
