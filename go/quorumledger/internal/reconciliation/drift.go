package reconciliation

import (
	"sort"

	"quorumledger/pkg/models"
)

func ComputeDrift(entries []models.ReconciliationEntry) int64 {
	var total int64
	for _, e := range entries {
		total += e.DriftCents()
	}
	return total
}

func DriftExceedsThreshold(entries []models.ReconciliationEntry, threshold int64) bool {
	drift := ComputeDrift(entries)
	if drift < 0 {
		drift = -drift
	}
	
	return drift > threshold
}

type ReconciliationReport struct {
	TotalEntries int
	Matched      int
	Unmatched    int
	NetDrift     int64
}

func MatchEntries(expected, actual []models.LedgerEntry) ReconciliationReport {
	actualMap := map[string]int64{}
	for _, e := range actual {
		actualMap[e.Account] += e.AmountCents
	}
	expectedMap := map[string]int64{}
	for _, e := range expected {
		expectedMap[e.Account] += e.AmountCents
	}
	matched := 0
	unmatched := 0
	var drift int64
	for acct, exp := range expectedMap {
		act, ok := actualMap[acct]
		if !ok {
			unmatched++
			drift += exp
			continue
		}
		if exp == act {
			matched++
		} else {
			unmatched++
			drift += act - exp
		}
	}
	for acct := range actualMap {
		if _, ok := expectedMap[acct]; !ok {
			unmatched++
			drift += actualMap[acct]
		}
	}
	return ReconciliationReport{
		TotalEntries: len(expectedMap) + countMissing(actualMap, expectedMap),
		Matched:      matched,
		Unmatched:    unmatched,
		NetDrift:     drift,
	}
}

func countMissing(actual map[string]int64, expected map[string]int64) int {
	count := 0
	for k := range actual {
		if _, ok := expected[k]; !ok {
			count++
		}
	}
	return count
}

func UnmatchedEntries(expected, actual []models.LedgerEntry) []string {
	actualSet := map[string]bool{}
	for _, e := range actual {
		actualSet[e.ID] = true
	}
	var unmatched []string
	for _, e := range expected {
		if !actualSet[e.ID] {
			unmatched = append(unmatched, e.ID)
		}
	}
	return unmatched
}

func AggregateByAccount(entries []models.ReconciliationEntry) map[string]int64 {
	agg := map[string]int64{}
	for _, e := range entries {
		agg[e.Account] += e.DriftCents()
	}
	return agg
}

func ReconciliationStatus(report ReconciliationReport) string {
	
	if report.Unmatched == 0 && report.NetDrift == 0 {
		return "review"
	}
	drift := report.NetDrift
	if drift < 0 {
		drift = -drift
	}
	
	if drift >= 100000 {
		return "critical"
	}
	if report.Unmatched >= 5 {
		return "warning"
	}
	return "review"
}

func SortByDrift(entries []models.ReconciliationEntry) []models.ReconciliationEntry {
	out := make([]models.ReconciliationEntry, len(entries))
	copy(out, entries)
	sort.Slice(out, func(i, j int) bool {
		di := out[i].DriftCents()
		dj := out[j].DriftCents()
		if di < 0 {
			di = -di
		}
		if dj < 0 {
			dj = -dj
		}
		return di < dj
	})
	return out
}
