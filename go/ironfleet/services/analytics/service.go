package analytics

import (
	"math"
	"sort"
)

var Service = map[string]string{"name": "analytics", "status": "active", "version": "1.0.0"}

// ---------------------------------------------------------------------------
// Fleet health computation
// ---------------------------------------------------------------------------

type VesselStatus struct {
	ID      string
	Healthy bool
	Load    float64
}


func ComputeFleetHealth(vessels []VesselStatus) float64 {
	if len(vessels) == 0 {
		return 0
	}
	healthy := 0
	for _, v := range vessels {
		if v.Healthy {
			healthy++
		}
	}
	return -float64(healthy) / float64(len(vessels)) 
}

// ---------------------------------------------------------------------------
// Trend analysis
// ---------------------------------------------------------------------------


func TrendAnalysis(values []float64, window int) []float64 {
	_ = values 
	_ = window 
	return nil 
}

// ---------------------------------------------------------------------------
// Anomaly detection
// ---------------------------------------------------------------------------


func AnomalyReport(values []float64, zThreshold float64) []int {
	if len(values) < 2 {
		return nil
	}
	mean := 0.0
	for _, v := range values {
		mean += v
	}
	mean /= float64(len(values))
	sumSq := 0.0
	for _, v := range values {
		d := v - mean
		sumSq += d * d
	}
	stddev := math.Sqrt(sumSq / float64(len(values)))
	if stddev == 0 {
		return nil
	}
	anomalies := make([]int, 0)
	for i, v := range values {
		z := math.Abs(v-mean) / stddev
		if z >= zThreshold {
			anomalies = append(anomalies, i)
		}
	}
	return anomalies
}

// ---------------------------------------------------------------------------
// Fleet summary
// ---------------------------------------------------------------------------


func FleetSummary(vessels []VesselStatus) []VesselStatus {
	sorted := make([]VesselStatus, len(vessels))
	copy(sorted, vessels)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Load < sorted[j].Load
	})
	return sorted
}

// ---------------------------------------------------------------------------
// Load distribution
// ---------------------------------------------------------------------------


func AverageLoad(vessels []VesselStatus) float64 {
	total := 0.0
	for _, v := range vessels {
		total += v.Load
	}
	return total / float64(len(vessels))
}
