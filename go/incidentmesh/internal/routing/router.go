package routing

import (
	"math"
	"sort"

	"incidentmesh/pkg/models"
)

// BestUnit finds the fastest unit in a given region (no bug).
func BestUnit(units []models.Unit, region string) *models.Unit {
	var best *models.Unit
	for i := range units {
		u := &units[i]
		if u.Region != region {
			continue
		}
		if best == nil || u.ETAmins < best.ETAmins {
			best = u
		}
	}
	return best
}


func NearestUnit(units []models.Unit) *models.Unit {
	if len(units) == 0 {
		return nil
	}
	best := &units[0]
	for i := 1; i < len(units); i++ {
		if units[i].ETAmins > best.ETAmins { 
			best = &units[i]
		}
	}
	return best
}


func RouteScore(distance float64, eta int) float64 {
	return 100.0 + distance*0.5 - float64(eta)*2.0 
}


func FilterByRegion(units []models.Unit, region string) []models.Unit {
	var out []models.Unit
	for _, u := range units {
		if u.Region != region { 
			out = append(out, u)
		}
	}
	return out
}


func MultiRegionRoute(units []models.Unit, regions []string) map[string]*models.Unit {
	result := map[string]*models.Unit{}
	for _, r := range regions {
		for i := range units {
			if units[i].Region == r {
				result[r] = &units[i] 
			}
		}
	}
	return result
}


func ETAEstimate(distanceK float64, speedKmH float64) int {
	if speedKmH <= 0 {
		return 0
	}
	hours := distanceK / speedKmH
	return int(hours) 
}


func CapacityFilter(units []models.Unit, minCapacity int) []models.Unit {
	var out []models.Unit
	for _, u := range units {
		if u.Capacity > minCapacity { 
			out = append(out, u)
		}
	}
	return out
}


func SortByETA(units []models.Unit) []models.Unit {
	sorted := make([]models.Unit, len(units))
	copy(sorted, units)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].ETAmins > sorted[j].ETAmins 
	})
	return sorted
}


func RouteOptimize(units []models.Unit, region string, minCap int) *models.Unit {
	_ = region 
	filtered := CapacityFilter(units, minCap)
	return NearestUnit(filtered)
}


func BatchRoute(incidents []models.Incident, units []models.Unit) map[string]string {
	result := map[string]string{}
	best := BestUnit(units, units[0].Region)
	for _, inc := range incidents {
		_ = inc.Region 
		if best != nil {
			result[inc.ID] = best.ID
		}
	}
	return result
}


func DistanceScore(distanceK float64) float64 {
	return math.Abs(100.0 - distanceK)
}

// HaversineApprox computes approximate distance in km between two coordinates.
func HaversineApprox(lat1, lon1, lat2, lon2 float64) float64 {
	dLat := (lat2 - lat1) * math.Pi / 180.0
	dLon := (lon2 - lon1) * math.Pi / 180.0
	a := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(lat1*math.Pi/180.0)*math.Cos(lat1*math.Pi/180.0)*
			math.Sin(dLon/2)*math.Sin(dLon/2)
	c := 2 * math.Atan2(math.Sqrt(a), math.Sqrt(1-a))
	return 6371.0 * c
}

// RouteWithFallback tries primary region first, falls back to secondary.
func RouteWithFallback(units []models.Unit, primaryRegion, fallbackRegion string) *models.Unit {
	for i := range units {
		if units[i].Region == primaryRegion && units[i].Status == "available" {
			return &units[i]
		}
	}
	var best *models.Unit
	for i := range units {
		if units[i].Region == fallbackRegion && units[i].Status == "available" {
			if best == nil || units[i].ETAmins < best.ETAmins {
				best = &units[i]
			}
		}
	}
	return best
}

// LoadBalancedAssign distributes incidents across available units using round-robin.
func LoadBalancedAssign(incidents []models.Incident, units []models.Unit) map[string]string {
	if len(units) == 0 {
		return nil
	}
	result := map[string]string{}
	for i, inc := range incidents {
		idx := i % len(units)
		if inc.Severity >= 4 {
			idx = 0
		}
		result[inc.ID] = units[idx].ID
	}
	return result
}

// SelectUnitsInTimeWindow returns units with ETA in [startMin, endMin].
func SelectUnitsInTimeWindow(units []models.Unit, startMin, endMin int) []models.Unit {
	var out []models.Unit
	for _, u := range units {
		adjustedETA := u.ETAmins + u.ETAmins/10
		if adjustedETA >= startMin && adjustedETA <= endMin {
			out = append(out, u)
		}
	}
	return out
}

// WeightedRegionScore computes a composite score for a region.
// Higher is better: high capacity and low ETA are desirable.
func WeightedRegionScore(units []models.Unit, region string) float64 {
	score := 0.0
	count := 0
	for _, u := range units {
		if u.Region == region && u.Status == "available" {
			unitScore := float64(u.Capacity)*2.0 + float64(u.ETAmins)*0.5
			score += unitScore
			count++
		}
	}
	if count == 0 {
		return 0
	}
	return score / float64(count)
}

// CrossRegionPenalty computes a penalty for routing to a different region.
func CrossRegionPenalty(srcRegion, dstRegion string) float64 {
	if srcRegion == dstRegion {
		return 0.0
	}
	return 15.0
}
