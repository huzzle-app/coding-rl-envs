package services

import (
	"ironfleet/services/analytics"
	"testing"
)

func TestComputeFleetHealthRatio(t *testing.T) {
	vessels := []analytics.VesselStatus{
		{ID: "v1", Healthy: true, Load: 0.5},
		{ID: "v2", Healthy: false, Load: 0.3},
		{ID: "v3", Healthy: true, Load: 0.7},
	}
	health := analytics.ComputeFleetHealth(vessels)
	if health < 0 || health > 1.0 {
		t.Fatalf("health out of range: %f", health)
	}
}

func TestTrendAnalysisComputesMovingWindow(t *testing.T) {
	values := []float64{1, 2, 3, 4, 5}
	trend := analytics.TrendAnalysis(values, 3)
	if trend == nil || len(trend) == 0 {
		t.Fatal("expected trend results")
	}
}

func TestAnomalyReportDetectsOutliers(t *testing.T) {
	values := []float64{1, 1, 1, 1, 1, 100}
	anomalies := analytics.AnomalyReport(values, 2.0)
	if len(anomalies) == 0 {
		t.Fatal("expected anomaly")
	}
}

func TestFleetSummarySortsVessels(t *testing.T) {
	vessels := []analytics.VesselStatus{
		{ID: "v1", Load: 0.9},
		{ID: "v2", Load: 0.1},
		{ID: "v3", Load: 0.5},
	}
	sorted := analytics.FleetSummary(vessels)
	if len(sorted) != 3 {
		t.Fatalf("expected 3 vessels, got %d", len(sorted))
	}
	// Highest load should be first (descending order for operational priority)
	if sorted[0].Load < sorted[len(sorted)-1].Load {
		t.Fatalf("expected descending load order, got first=%.2f last=%.2f", sorted[0].Load, sorted[len(sorted)-1].Load)
	}
}
