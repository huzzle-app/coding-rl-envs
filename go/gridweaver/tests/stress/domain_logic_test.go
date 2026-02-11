package stress

import (
	"math"
	"testing"

	"gridweaver/internal/dispatch"
	"gridweaver/internal/estimator"
	"gridweaver/internal/resilience"
	"gridweaver/pkg/models"
)

func TestDomainLogicBugs(t *testing.T) {

	t.Run("OptimalGenerationMix_RespectsMinGenConstraint", func(t *testing.T) {
		// The key insight: if you only need 50 MW from a generator with MinGen=100,
		// you still must produce 100 MW (minimum generation constraint).
		// This means selecting a cheap generator with high MinGen can actually
		// INCREASE total cost vs skipping it for a slightly more expensive one.
		generators := []struct {
			ID        string
			CapMW     float64
			CostPerMW float64
			MinGenMW  float64
		}{
			{"solar", 200, 10.0, 0},   // cheap, no minimum
			{"gas", 500, 50.0, 200},    // expensive, high minimum
			{"coal", 300, 30.0, 50},    // mid-cost, low minimum
		}
		// Need 250 MW. Optimal: solar (200) + coal (50) = 200*10 + 50*30 = 3500
		// Buggy with MinGen: solar(200) + gas forces 200 MW = 200*10 + 200*50 = 12000
		ids, cost := dispatch.OptimalGenerationMix(generators, 250)
		if len(ids) < 2 {
			t.Fatalf("expected at least 2 generators, got %d", len(ids))
		}
		// Total generation should not exceed demand by more than MinGen of any committed unit
		totalGen := 0.0
		for _, id := range ids {
			for _, g := range generators {
				if g.ID == id {
					totalGen += g.CapMW
				}
			}
		}
		if cost > 5000 {
			t.Fatalf("cost should be ~3500 (solar+coal), got %.0f - MinGen constraint likely forcing expensive gas unit", cost)
		}
	})

	t.Run("OptimalGenerationMix_MinGenOvershoot", func(t *testing.T) {
		// When MinGen > remaining demand, the generator produces more than needed
		generators := []struct {
			ID        string
			CapMW     float64
			CostPerMW float64
			MinGenMW  float64
		}{
			{"base", 100, 10.0, 0},
			{"peaker", 200, 50.0, 150}, // MinGen 150 but might only need 50 more
		}
		// Need 150 MW. base(100) + peaker should produce max(50,150)=150 at 50/MW = 7500
		// Total cost = 100*10 + 150*50 = 8500
		// But if we just used base(100) + needed 50 more, peaker's minimum forces 150
		_, cost := dispatch.OptimalGenerationMix(generators, 150)
		// We've overshot by 100 MW (base 100 + peaker min 150 = 250 vs needed 150)
		// That means cost includes generation we don't need
		if cost > 2500 {
			t.Fatalf("total cost %.0f too high - MinGen constraint forcing overproduction", cost)
		}
	})

	t.Run("ContingencyReserve_LargestUnit", func(t *testing.T) {
		caps := []float64{100, 300, 200, 150}
		reserve := dispatch.ContingencyReserve(caps, 5000)
		// N-1: reserve must cover largest unit (300)
		if reserve < 300 {
			t.Fatalf("N-1 reserve should be >= largest unit (300), got %.0f", reserve)
		}
	})

	t.Run("ContingencyReserve_MinimumFloor", func(t *testing.T) {
		caps := []float64{10, 20}
		reserve := dispatch.ContingencyReserve(caps, 1000)
		// Largest unit is 20, but 5% of demand = 50, which is higher
		minReserve := 1000 * 0.05
		if reserve < minReserve {
			t.Fatalf("reserve should be >= 5%% of demand (%.0f), got %.0f", minReserve, reserve)
		}
	})

	t.Run("EconomicDispatch_LowerCostGetsMore", func(t *testing.T) {
		caps := []float64{500, 500, 500}
		costs := []float64{10, 30, 50}
		alloc := dispatch.EconomicDispatch(caps, costs, 900)
		if alloc == nil {
			t.Fatalf("expected allocations")
		}
		// Lower cost generators should get more dispatch
		if alloc[0] < alloc[2] {
			t.Fatalf("cheapest gen should get more than expensive: got [%.0f, %.0f, %.0f]", alloc[0], alloc[1], alloc[2])
		}
	})

	t.Run("EconomicDispatch_SumsToTotal", func(t *testing.T) {
		caps := []float64{400, 400, 400}
		costs := []float64{20, 30, 40}
		demand := 600.0
		alloc := dispatch.EconomicDispatch(caps, costs, demand)
		sum := 0.0
		for _, a := range alloc {
			sum += a
		}
		if math.Abs(sum-demand) > 10 {
			t.Fatalf("allocations should sum to demand (%.0f), got %.0f", demand, sum)
		}
	})

	t.Run("ReserveSharing_NoDoubleCount", func(t *testing.T) {
		regions := []struct {
			Name     string
			GenMW    float64
			DemandMW float64
			ReserveMW float64
		}{
			{"west", 1000, 800, 100},
			{"east", 600, 500, 50},
		}
		totalShared, contributions := dispatch.ReserveSharing(regions)
		// west excess: 200, east excess: 100
		// Shared should be excess from each region (300) plus dedicated reserves (150) = 450 max
		// But should NOT double-count: excess already includes reserves
		expectedExcess := 300.0 // 200 + 100
		if math.Abs(contributions["west"]-200) > 0.01 || math.Abs(contributions["east"]-100) > 0.01 {
			t.Fatalf("contributions wrong: expected west=200, east=100, got west=%.0f, east=%.0f",
				contributions["west"], contributions["east"])
		}
		// Total should be excess contributions (300), NOT excess+reserves (450)
		if totalShared > expectedExcess+1 {
			t.Fatalf("total shared reserves should be %.0f (not double-counting), got %.0f", expectedExcess, totalShared)
		}
	})

	t.Run("DispatchPrioritySorter_HighUrgencyFirst", func(t *testing.T) {
		orders := []dispatch.Order{
			{ID: "low", Urgency: 1, ETA: "10m"},
			{ID: "high", Urgency: 10, ETA: "30m"},
			{ID: "med", Urgency: 5, ETA: "20m"},
		}
		sorted := dispatch.DispatchPrioritySorter(orders, 1.0, 0.0, 60)
		if sorted[0].ID != "high" {
			t.Fatalf("highest urgency should be first, got %s", sorted[0].ID)
		}
	})

	t.Run("DispatchPrioritySorter_ETABreaksTies", func(t *testing.T) {
		// Two orders with same urgency but different ETAs
		// The one with shorter ETA (closer deadline) should rank higher
		orders := []dispatch.Order{
			{ID: "far", Urgency: 5, ETA: "120m"},    // far deadline = lower priority
			{ID: "near", Urgency: 5, ETA: "5m"},      // near deadline = higher priority
		}
		// slaWeight > 0 means ETA affects ranking
		// With maxSLA=200, score = 5*1.0 + (200-ETA_minutes)*0.5
		// "far":  5 + (200-120)*0.5 = 5 + 40 = 45
		// "near": 5 + (200-5)*0.5 = 5 + 97.5 = 102.5
		// Bug: uses len(ETA) not actual minutes, so len("120m")=4, len("5m")=2
		// Buggy: far: 5+(200-4)*0.5=103, near: 5+(200-2)*0.5=104
		sorted := dispatch.DispatchPrioritySorter(orders, 1.0, 0.5, 200)
		// "near" should be first (shorter deadline = higher priority)
		if sorted[0].ID != "near" {
			t.Fatalf("shorter ETA should rank higher, got %s first (ETA uses string length instead of value?)", sorted[0].ID)
		}
	})

	t.Run("EmergencyReserveTarget_ColdWeather", func(t *testing.T) {
		// Extremely cold weather (-10°C) should increase reserve MORE than hot weather (40°C)
		// Cold adds: 0.03 * (5-(-10))/15 = 0.03 * 1.0 = 0.03
		// Hot adds: 0.02 * (40-35)/10 = 0.02 * 0.5 = 0.01
		coldTarget := estimator.EmergencyReserveTarget(0.12, -10, 0)
		hotTarget := estimator.EmergencyReserveTarget(0.12, 40, 0)
		if coldTarget <= hotTarget {
			t.Fatalf("cold weather should require more reserves than hot: cold=%.3f, hot=%.3f", coldTarget, hotTarget)
		}
	})

	t.Run("EmergencyReserveTarget_MildWeatherNoBoost", func(t *testing.T) {
		// Mild weather (20°C) should not add any temperature-based reserve
		target := estimator.EmergencyReserveTarget(0.12, 20, 0)
		if math.Abs(target-0.12) > 0.001 {
			t.Fatalf("mild weather should not change reserve target, expected 0.12, got %.3f", target)
		}
	})

	t.Run("EmergencyReserveTarget_AcceleratingOutageImpact", func(t *testing.T) {
		// With >3 outages, the marginal impact should increase
		target3 := estimator.EmergencyReserveTarget(0.12, 20, 3)
		target6 := estimator.EmergencyReserveTarget(0.12, 20, 6)
		// Linear part: 3 * 0.01 = 0.03 for first 3
		// Accelerating: for outages 4,5,6 adds 3*0.005 = 0.015 extra
		// target3 = 0.12 + 0.03 = 0.15
		// target6 = 0.12 + 0.06 + 0.015 = 0.195
		marginal3to6 := target6 - target3
		baseMarginal := target3 - 0.12
		// Each outage beyond 3 should add MORE than the base per-outage increment
		avgMarginalPer3 := baseMarginal / 3.0
		avgMarginalPer3more := marginal3to6 / 3.0
		if avgMarginalPer3more <= avgMarginalPer3 {
			t.Fatalf("outages beyond 3 should have accelerating impact: per-outage 1-3=%.4f, 4-6=%.4f",
				avgMarginalPer3, avgMarginalPer3more)
		}
	})

	t.Run("EmergencyReserveTarget_CapAt30Pct", func(t *testing.T) {
		target := estimator.EmergencyReserveTarget(0.12, -20, 20)
		if target > 0.30 {
			t.Fatalf("emergency reserve should cap at 30%%, got %.2f", target)
		}
	})

	t.Run("CorrelatedLoadEstimate_FullyCorrelated", func(t *testing.T) {
		loads := []float64{100, 200, 300}
		result := estimator.CorrelatedLoadEstimate(loads, 1.0)
		expected := 600.0 // simple sum when fully correlated
		if math.Abs(result-expected) > 0.01 {
			t.Fatalf("fully correlated loads should sum to 600, got %.2f", result)
		}
	})

	t.Run("CorrelatedLoadEstimate_Uncorrelated", func(t *testing.T) {
		loads := []float64{300, 400}
		result := estimator.CorrelatedLoadEstimate(loads, 0.0)
		expected := math.Sqrt(300*300 + 400*400) // 500.0
		if math.Abs(result-expected) > 0.01 {
			t.Fatalf("uncorrelated loads: expected %.2f (sqrt of sum of squares), got %.2f", expected, result)
		}
	})

	t.Run("RegionalDiversity_CalculatedCorrectly", func(t *testing.T) {
		peaks := []float64{500, 400, 300}
		coincidentPeak := 900.0
		diversity := estimator.RegionalDiversity(peaks, coincidentPeak)
		// diversity = sumPeaks / coincidentPeak = 1200/900 = 1.333
		// This means no diversity benefit (factor > 1 means worse)
		expected := 1200.0 / 900.0
		if math.Abs(diversity-expected) > 0.01 {
			t.Fatalf("expected diversity factor %.3f, got %.3f", expected, diversity)
		}
	})

	t.Run("DemandForecastMultiStep_TrendAccumulates", func(t *testing.T) {
		forecasts := estimator.DemandForecastMultiStep(1000, 10, nil, 5)
		// Step 1: 1010, Step 2: 1020, Step 3: 1030, Step 4: 1040, Step 5: 1050
		if len(forecasts) != 5 {
			t.Fatalf("expected 5 forecasts, got %d", len(forecasts))
		}
		if math.Abs(forecasts[4]-1050) > 0.1 {
			t.Fatalf("5th step should be 1050, got %.1f", forecasts[4])
		}
	})

	t.Run("DemandForecastMultiStep_SeasonalFactors", func(t *testing.T) {
		factors := []float64{1.0, 1.3, 0.8}
		forecasts := estimator.DemandForecastMultiStep(100, 0, factors, 6)
		// With no trend, each step uses seasonal factor cyclically
		// Step 0: 100 * 1.0, Step 1: 100 * 1.3, Step 2: 100 * 0.8
		// Step 3: 100 * 1.0, Step 4: 100 * 1.3, Step 5: 100 * 0.8
		if math.Abs(forecasts[1]-130) > 0.1 {
			t.Fatalf("step 1 with factor 1.3: expected 130, got %.1f", forecasts[1])
		}
		if math.Abs(forecasts[2]-80) > 0.1 {
			t.Fatalf("step 2 with factor 0.8: expected 80, got %.1f", forecasts[2])
		}
	})

	t.Run("FailoverChain_LowestPriorityFirst", func(t *testing.T) {
		services := []struct {
			Name     string
			Healthy  bool
			Priority int
			LoadPct  float64
		}{
			{"primary", true, 1, 0.5},
			{"secondary", true, 2, 0.3},
			{"tertiary", true, 3, 0.1},
		}
		// Priority 1 = highest priority (should be selected first)
		best := resilience.FailoverChain(services, 0.8)
		if best != "primary" {
			t.Fatalf("should select primary (priority 1), got %s", best)
		}
	})

	t.Run("FailoverChain_SkipsUnhealthy", func(t *testing.T) {
		services := []struct {
			Name     string
			Healthy  bool
			Priority int
			LoadPct  float64
		}{
			{"primary", false, 1, 0.5},
			{"secondary", true, 2, 0.3},
		}
		best := resilience.FailoverChain(services, 0.8)
		if best != "secondary" {
			t.Fatalf("should skip unhealthy primary, got %s", best)
		}
	})

	t.Run("FailoverChain_SkipsOverloaded", func(t *testing.T) {
		services := []struct {
			Name     string
			Healthy  bool
			Priority int
			LoadPct  float64
		}{
			{"primary", true, 1, 0.95},
			{"secondary", true, 2, 0.3},
		}
		best := resilience.FailoverChain(services, 0.8)
		if best != "secondary" {
			t.Fatalf("should skip overloaded primary, got %s", best)
		}
	})

	t.Run("FailoverChain_NearCapacityPenalty", func(t *testing.T) {
		// Primary is near capacity (within 10% of max), secondary is lightly loaded
		// The penalty for being near capacity should make secondary preferred
		services := []struct {
			Name     string
			Healthy  bool
			Priority int
			LoadPct  float64
		}{
			{"primary", true, 1, 0.75},    // within 10% of maxLoadPct 0.80
			{"secondary", true, 2, 0.30},  // lightly loaded
		}
		best := resilience.FailoverChain(services, 0.80)
		// Primary gets penalized -500 for being within 10% of max
		// Score: primary = 1000 - 1*10 - 500 = 490, secondary = 1000 - 2*10 = 980
		// Secondary should win despite lower priority number
		if best != "secondary" {
			t.Fatalf("near-capacity primary should be penalized, selecting secondary instead, got %s", best)
		}
	})

	t.Run("LoadBasedShedding_LowestPriorityShedFirst", func(t *testing.T) {
		items := []struct {
			ID       string
			Priority int
			LoadMW   float64
		}{
			{"critical", 1, 10},
			{"normal", 5, 10},
			{"background", 10, 10},
		}
		shed := resilience.LoadBasedShedding(items, 0.95, 0.80)
		if len(shed) == 0 {
			t.Fatalf("should shed items when over target")
		}
		// Should shed lowest priority (highest number) first
		if shed[0] != "background" {
			t.Fatalf("should shed lowest priority first, got %s", shed[0])
		}
	})

	t.Run("LoadBasedShedding_CostEffectiveness", func(t *testing.T) {
		// When priorities are similar but load differs significantly,
		// the algorithm should prefer shedding high-load low-priority items.
		// Priority/LoadMW ratio determines shed cost.
		// Bug: cost = priority/load. "bigbg" cost = 8/100=0.08 (shed first)
		// "smallcrit" cost = 2/5=0.4 (shed last)
		// But we should shed "bigbg" first since it's less critical AND frees more load
		items := []struct {
			ID       string
			Priority int
			LoadMW   float64
		}{
			{"smallcrit", 2, 5},     // critical, small load
			{"bigbg", 8, 100},       // background, big load
			{"medbg", 9, 50},        // background, medium load
		}
		shed := resilience.LoadBasedShedding(items, 0.95, 0.80)
		if len(shed) == 0 {
			t.Fatalf("should shed items")
		}
		// Both bigbg and medbg are background-priority. bigbg has lowest cost ratio, shed first.
		// This is actually reasonable behavior IF cost ratio is the right metric.
		// But: if all items have same load, should shed highest priority NUMBER first
		items2 := []struct {
			ID       string
			Priority int
			LoadMW   float64
		}{
			{"critical", 1, 10},
			{"normal", 5, 10},
			{"background", 10, 10},
		}
		shed2 := resilience.LoadBasedShedding(items2, 0.95, 0.80)
		// With equal loads, cost = priority/10. critical=0.1, normal=0.5, background=1.0
		// Lowest cost = critical! Bug: sheds critical first when loads are equal
		if len(shed2) > 0 && shed2[0] == "critical" {
			t.Fatalf("should never shed critical (priority 1) first, even with cost-based approach")
		}
	})

	t.Run("WeightedQualityScore_UniformReadings", func(t *testing.T) {
		readings := []models.MeterReading{
			{Quality: 0.8}, {Quality: 0.8}, {Quality: 0.8},
		}
		score := estimator.WeightedQualityScore(readings, 0.9)
		if math.Abs(score-0.8) > 0.01 {
			t.Fatalf("uniform quality should return 0.8, got %.3f", score)
		}
	})
}
