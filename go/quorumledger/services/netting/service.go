package netting

import (
	"quorumledger/internal/settlement"
	"quorumledger/pkg/models"
)

const Name = "netting"
const Role = "settlement netting and batching"

func NetPositions(entries []models.LedgerEntry) map[string]int64 {
	return settlement.NetPositions(entries)
}

func ComputeFee(amountCents int64, basisPoints int) int64 {
	return settlement.SettlementFee(amountCents, basisPoints)
}

func BatchEntries(entries []models.LedgerEntry, maxSize int) [][]models.LedgerEntry {
	return settlement.OptimalBatching(entries, maxSize)
}
