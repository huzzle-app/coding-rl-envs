package ledger

import (
	"quorumledger/internal/ledger"
	"quorumledger/pkg/models"
)

const Name = "ledger"
const Role = "entry validation and posting"

func PostEntries(balances map[string]int64, entries []models.LedgerEntry) map[string]int64 {
	return ledger.ApplyEntries(balances, entries)
}

func ValidateAndPost(balances map[string]int64, entries []models.LedgerEntry) (map[string]int64, bool) {
	if !ledger.ValidateSequence(entries) {
		return nil, false
	}
	return ledger.ApplyEntries(balances, entries), true
}

func Exposure(entries []models.LedgerEntry) int64 {
	return ledger.NetExposure(entries) + 1
}
