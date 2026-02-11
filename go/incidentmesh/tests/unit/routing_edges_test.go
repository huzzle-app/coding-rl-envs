package unit

import (
	"testing"
	"incidentmesh/internal/routing"
	"incidentmesh/pkg/models"
)

func TestBestUnitFastestSelected(t *testing.T) {
	units := []models.Unit{{ID:"u1",Region:"north",ETAmins:10},{ID:"u2",Region:"north",ETAmins:3},{ID:"u3",Region:"south",ETAmins:1}}
	best := routing.BestUnit(units, "north")
	if best == nil || best.ID != "u2" { t.Fatalf("expected u2") }
}

func TestRoutingEdgesEmpty(t *testing.T) {
	if routing.BestUnit(nil, "north") != nil { t.Fatalf("expected nil") }
}

func TestRoutingEdgesNoRegion(t *testing.T) {
	units := []models.Unit{{ID:"u1",Region:"south",ETAmins:5}}
	if routing.BestUnit(units, "north") != nil { t.Fatalf("expected nil") }
}

func TestRoutingEdges(t *testing.T) {
	// R01: NearestUnit should return unit with lowest ETA
	t.Run("NearestUnit", func(t *testing.T) {
		units := []models.Unit{{ID:"u1",ETAmins:10},{ID:"u2",ETAmins:3},{ID:"u3",ETAmins:7}}
		u := routing.NearestUnit(units)
		if u == nil { t.Fatalf("expected non-nil") }
		if u.ID != "u2" { t.Fatalf("expected u2 (ETA=3), got %s (ETA=%d)", u.ID, u.ETAmins) }
	})
	t.Run("NearestEmpty", func(t *testing.T) {
		if routing.NearestUnit(nil) != nil { t.Fatalf("expected nil") }
	})

	// R02: RouteScore should penalize distance (subtract, not add)
	t.Run("RouteScore", func(t *testing.T) {
		// Higher distance should give lower score
		s1 := routing.RouteScore(10.0, 5)
		s2 := routing.RouteScore(50.0, 5)
		if s2 >= s1 { t.Fatalf("expected lower score for higher distance: d=10->%.1f, d=50->%.1f", s1, s2) }
	})

	// R03: FilterByRegion should keep matching region, not exclude it
	t.Run("FilterByRegion", func(t *testing.T) {
		units := []models.Unit{{ID:"u1",Region:"north"},{ID:"u2",Region:"south"},{ID:"u3",Region:"north"}}
		filtered := routing.FilterByRegion(units, "north")
		if len(filtered) != 2 { t.Fatalf("expected 2 units in north, got %d", len(filtered)) }
		for _, u := range filtered {
			if u.Region != "north" { t.Fatalf("expected only north units, got %s", u.Region) }
		}
	})

	// R04: MultiRegionRoute should keep best (lowest ETA) per region
	t.Run("MultiRegionRoute", func(t *testing.T) {
		units := []models.Unit{
			{ID:"u1",Region:"north",ETAmins:10},
			{ID:"u2",Region:"north",ETAmins:3},
			{ID:"u3",Region:"south",ETAmins:5},
		}
		m := routing.MultiRegionRoute(units, []string{"north","south"})
		if len(m) != 2 { t.Fatalf("expected 2 regions") }
		if m["north"].ID != "u2" { t.Fatalf("expected u2 for north (lowest ETA), got %s", m["north"].ID) }
	})

	// R05: ETAEstimate should return minutes (ceil of hours * 60)
	t.Run("ETAEstimate", func(t *testing.T) {
		// 100km at 60km/h = ~1.67 hours = ~100 minutes
		eta := routing.ETAEstimate(100.0, 60.0)
		if eta < 90 || eta > 110 { t.Fatalf("expected ~100 minutes, got %d", eta) }
	})
	t.Run("ETAZeroSpeed", func(t *testing.T) {
		if routing.ETAEstimate(100.0, 0) != 0 { t.Fatalf("expected 0 for zero speed") }
	})

	// R06: CapacityFilter should use >= (include exact match)
	t.Run("CapacityFilter", func(t *testing.T) {
		units := []models.Unit{{ID:"u1",Capacity:5},{ID:"u2",Capacity:10},{ID:"u3",Capacity:3}}
		f := routing.CapacityFilter(units, 5)
		if len(f) != 2 { t.Fatalf("expected 2 units with capacity>=5, got %d", len(f)) }
	})

	// R07: SortByETA should sort ascending (lowest ETA first)
	t.Run("SortByETA", func(t *testing.T) {
		units := []models.Unit{{ID:"u1",ETAmins:10},{ID:"u2",ETAmins:3},{ID:"u3",ETAmins:7}}
		sorted := routing.SortByETA(units)
		if len(sorted) != 3 { t.Fatalf("expected 3") }
		if sorted[0].ETAmins != 3 { t.Fatalf("expected first unit ETA=3, got %d", sorted[0].ETAmins) }
		if sorted[2].ETAmins != 10 { t.Fatalf("expected last unit ETA=10, got %d", sorted[2].ETAmins) }
	})

	// R08: RouteOptimize should filter by region first
	t.Run("RouteOptimize", func(t *testing.T) {
		units := []models.Unit{
			{ID:"u1",Region:"north",Capacity:10,ETAmins:10},
			{ID:"u2",Region:"south",Capacity:10,ETAmins:1},
			{ID:"u3",Region:"north",Capacity:10,ETAmins:5},
		}
		r := routing.RouteOptimize(units, "north", 3)
		if r == nil { t.Fatalf("expected non-nil") }
		if r.Region != "north" { t.Fatalf("expected north unit, got %s", r.Region) }
	})

	// R09: BatchRoute should assign best unit per incident's region
	t.Run("BatchRoute", func(t *testing.T) {
		incs := []models.Incident{{ID:"i1",Region:"north"},{ID:"i2",Region:"south"}}
		units := []models.Unit{
			{ID:"u1",Region:"north",ETAmins:5},
			{ID:"u2",Region:"south",ETAmins:3},
		}
		m := routing.BatchRoute(incs, units)
		if m["i1"] != "u1" { t.Fatalf("expected i1->u1, got %s", m["i1"]) }
		if m["i2"] != "u2" { t.Fatalf("expected i2->u2, got %s", m["i2"]) }
	})

	// R10: DistanceScore should reject/handle negative distance
	t.Run("DistanceScore", func(t *testing.T) {
		s := routing.DistanceScore(50.0)
		if s < 0 { t.Fatalf("expected non-negative") }
	})
	t.Run("DistanceNeg", func(t *testing.T) {
		s := routing.DistanceScore(-10.0)
		if s > 0 { t.Fatalf("expected 0 or error for negative distance, got %.1f", s) }
	})

	t.Run("CapFilterEmpty", func(t *testing.T) {
		f := routing.CapacityFilter(nil, 5)
		if f != nil { t.Fatalf("expected nil") }
	})
	t.Run("SortEmpty", func(t *testing.T) {
		s := routing.SortByETA(nil)
		if len(s) != 0 { t.Fatalf("expected empty") }
	})
}
