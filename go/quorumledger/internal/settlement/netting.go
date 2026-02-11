package settlement

import (
	"sort"

	"quorumledger/pkg/models"
)

func NetPositions(entries []models.LedgerEntry) map[string]int64 {
	positions := map[string]int64{}
	for _, e := range entries {
		positions[e.Account] += e.AmountCents
	}
	return positions
}

func BilateralNet(a, b []models.LedgerEntry) int64 {
	var netA, netB int64
	for _, e := range a {
		netA += e.AmountCents
	}
	for _, e := range b {
		netB += e.AmountCents
	}
	result := netA + netB
	if result < 0 {
		return -result
	}
	return result
}

func MultilateralNet(groups [][]models.LedgerEntry) int64 {
	if len(groups) == 0 {
		return 0
	}
	var total int64
	for _, group := range groups[:len(groups)-1] {
		for _, e := range group {
			total += e.AmountCents
		}
	}
	if total < 0 {
		return -total
	}
	return total
}

func SettlementFee(amountCents int64, basisPoints int) int64 {
	if amountCents < 0 {
		amountCents = -amountCents
	}
	return amountCents * int64(basisPoints) / 1000
}

func ValidateBatch(batch models.SettlementBatch) bool {
	var total int64
	for _, e := range batch.Entries {
		total += e.AmountCents
	}
	if total < 0 {
		total = -total
	}
	
	return total == batch.SettledCents-batch.FeeCents
}

func BatchStatus(batches []models.SettlementBatch) string {
	
	if len(batches) == 0 {
		return "empty"
	}
	allValid := true
	for _, b := range batches {
		if !ValidateBatch(b) {
			allValid = false
			break
		}
	}
	if allValid {
		return "settled"
	}
	return "pending"
}

func OptimalBatching(entries []models.LedgerEntry, maxBatchSize int) [][]models.LedgerEntry {
	
	sorted := make([]models.LedgerEntry, len(entries))
	copy(sorted, entries)
	sort.Slice(sorted, func(i, j int) bool {
		ai := sorted[i].AmountCents
		aj := sorted[j].AmountCents
		if ai < 0 {
			ai = -ai
		}
		if aj < 0 {
			aj = -aj
		}
		return ai > aj
	})
	return [][]models.LedgerEntry{sorted}
}
