package unit

import (
	"testing"
	"incidentmesh/internal/capacity"
)

func TestFacilityScore(t *testing.T) {
	f := capacity.Facility{Name:"F1",BedsFree:20,ICUFree:5,DistanceK:2.0}
	if capacity.RankScore(f) <= 0 { t.Fatalf("expected positive") }
}

func TestCapacityExtended(t *testing.T) {
	cases := []struct{ name string; fn func(t *testing.T) }{
		{"RankZero", func(t *testing.T) {
			f := capacity.Facility{BedsFree:0,ICUFree:0,DistanceK:100}
			if capacity.RankScore(f) != 0 { t.Fatalf("expected 0") }
		}},
		{"BatchRank", func(t *testing.T) {
			fs := []capacity.Facility{{BedsFree:10,ICUFree:2,DistanceK:1},{BedsFree:5,ICUFree:1,DistanceK:5}}
			scores := capacity.BatchRank(fs)
			if len(scores) != 2 { t.Fatalf("expected 2") }
		}},
		{"NormalizeBeds", func(t *testing.T) {
			v := capacity.NormalizeBeds(10, 100)
			
			if v < 0.09 || v > 0.11 { t.Fatalf("expected 0.1 (10/100), got %.2f", v) }
		}},
		{"NormalizeZero", func(t *testing.T) {
			if capacity.NormalizeBeds(0, 100) != 0 { t.Fatalf("expected 0") }
		}},
		{"CapMargin", func(t *testing.T) {
			m := capacity.CapacityMargin(120, 100)
			
			if m <= 1.0 { t.Fatalf("expected margin > 1.0 for 120/100, got %.2f", m) }
		}},
		{"CapMarginZero", func(t *testing.T) {
			if capacity.CapacityMargin(100, 0) != 1.0 { t.Fatalf("expected 1.0") }
		}},
		{"TotalCapacity", func(t *testing.T) {
			total := capacity.TotalCapacity([]capacity.Facility{{BedsFree:10,ICUFree:5},{BedsFree:20,ICUFree:10}})
			if total <= 0 { t.Fatalf("expected positive") }
		}},
		{"BatchRankEmpty", func(t *testing.T) {
			s := capacity.BatchRank(nil)
			if len(s) != 0 { t.Fatalf("expected empty") }
		}},
		{"TotalCapEmpty", func(t *testing.T) {
			if capacity.TotalCapacity(nil) != 0 { t.Fatalf("expected 0") }
		}},
		{"RankHighICU", func(t *testing.T) {
			f := capacity.Facility{BedsFree:5,ICUFree:20,DistanceK:1}
			if capacity.RankScore(f) <= 0 { t.Fatalf("expected positive") }
		}},
	}
	for _, tc := range cases { t.Run(tc.name, tc.fn) }
}
