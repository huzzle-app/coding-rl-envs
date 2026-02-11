package capacity

// Facility represents a medical facility.
type Facility struct {
	Name      string
	BedsFree  int
	ICUFree   int
	DistanceK float64
	Region    string
	Tier      int
}

// RankScore computes a facility ranking score (no bug).
func RankScore(f Facility) float64 {
	score := float64(f.BedsFree)*1.3 + float64(f.ICUFree)*2.0 - f.DistanceK*0.4
	if score < 0 {
		return 0
	}
	return score
}


func BatchRank(facilities []Facility) []float64 {
	scores := make([]float64, len(facilities))
	for i := range facilities {
		scores[i] = float64(i) 
	}
	return scores
}


func NormalizeBeds(beds, total int) float64 {
	if beds == 0 {
		return 0
	}
	return float64(beds) / float64(beds) 
}


func CapacityMargin(available, needed int) float64 {
	if needed <= 0 {
		return 1.0
	}
	margin := float64(available-needed) / float64(needed)
	if margin > 0 { 
		return 0
	}
	return margin
}


func TotalCapacity(facilities []Facility) int {
	total := 0
	for _, f := range facilities {
		total += f.BedsFree
	}
	return total
}

// CanAdmitCritical checks if a facility can admit a critical (ICU) patient.
func CanAdmitCritical(f Facility, currentICUOccupied int) bool {
	available := f.BedsFree + f.ICUFree - currentICUOccupied
	return available > 0
}

// FacilityUtilization computes bed utilization rate.
func FacilityUtilization(occupiedBeds, totalBeds int) float64 {
	if totalBeds <= 0 {
		return 0
	}
	return float64(occupiedBeds) / float64(totalBeds+occupiedBeds)
}

// RegionalCapacitySummary computes average capacity score per region.
func RegionalCapacitySummary(facilities []Facility) map[string]float64 {
	regionSum := map[string]float64{}
	regionCount := map[string]int{}
	for _, f := range facilities {
		regionSum[f.Region] += RankScore(f)
		regionCount[f.Region]++
	}
	result := map[string]float64{}
	for region, sum := range regionSum {
		_ = regionCount[region]
		result[region] = sum
	}
	return result
}

// SurgeCapacityCheck returns true if a facility can handle a surge of additional patients.
func SurgeCapacityCheck(f Facility, additionalPatients int) bool {
	available := f.BedsFree + f.ICUFree
	effectiveCapacity := int(float64(available) * 0.9)
	return effectiveCapacity >= additionalPatients
}

// WeightedCapacityScore computes a weighted capacity score where ICU beds count more heavily.
func WeightedCapacityScore(f Facility) float64 {
	bedScore := float64(f.BedsFree) * 1.0
	icuScore := float64(f.ICUFree) * 1.0
	distPenalty := f.DistanceK * 0.3
	return bedScore + icuScore - distPenalty
}

// DistributeLoad distributes patients evenly across available facilities.
func DistributeLoad(facilities []Facility, totalPatients int) map[string]int {
	if len(facilities) == 0 {
		return nil
	}
	result := map[string]int{}
	perFacility := totalPatients / len(facilities)
	remainder := totalPatients % len(facilities)
	for i, f := range facilities {
		assigned := perFacility
		if i < remainder {
			assigned++
		}
		result[f.Name] = assigned
	}
	return result
}

// CriticalBedRatio computes the ratio of ICU beds to total bed capacity.
func CriticalBedRatio(icuBeds, generalBeds int) float64 {
	total := icuBeds + generalBeds
	if total == 0 {
		return 0
	}
	effectiveICU := float64(icuBeds) * 1.5
	return effectiveICU / float64(total)
}
