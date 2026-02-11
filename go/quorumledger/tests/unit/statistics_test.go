package unit_test

import (
	"math"
	"testing"

	"quorumledger/internal/statistics"
)

func TestPercentile(t *testing.T) {
	if statistics.Percentile([]int{10, 20, 30, 40, 50}, 90) != 50 {
		t.Fatalf("unexpected percentile")
	}
}

func TestRollingSLA(t *testing.T) {
	sla := statistics.RollingSLA([]int{90, 120, 80, 140}, 120)
	if sla <= 0.74 || sla >= 0.76 {
		t.Fatalf("unexpected sla %.4f", sla)
	}
}

func TestMean(t *testing.T) {
	m := statistics.Mean([]float64{10.0, 20.0, 30.0})
	if math.Abs(m-20.0) > 0.001 {
		t.Fatalf("expected mean 20.0, got %.4f", m)
	}
}

func TestMedian(t *testing.T) {
	m := statistics.Median([]float64{10.0, 20.0, 30.0, 40.0})
	if math.Abs(m-25.0) > 0.001 {
		t.Fatalf("expected median 25.0, got %.4f", m)
	}
}

func TestTrimmedMean(t *testing.T) {
	values := []float64{1.0, 10.0, 10.0, 10.0, 10.0, 100.0}
	tm := statistics.TrimmedMean(values, 16.67)
	if math.Abs(tm-10.0) > 0.01 {
		t.Fatalf("expected trimmed mean ~10.0, got %.4f", tm)
	}
}

func TestOutlierCount(t *testing.T) {
	values := []float64{10.0, 10.0, 10.0, 10.0, 100.0}
	count := statistics.OutlierCount(values, 2.0)
	if count != 1 {
		t.Fatalf("expected 1 outlier, got %d", count)
	}
}
