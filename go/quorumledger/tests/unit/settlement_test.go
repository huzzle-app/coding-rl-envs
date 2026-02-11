package unit_test

import (
	"testing"

	"quorumledger/internal/settlement"
	"quorumledger/pkg/models"
)

func TestNetPositions(t *testing.T) {
	entries := []models.LedgerEntry{
		{Account: "a", AmountCents: 100},
		{Account: "b", AmountCents: -50},
		{Account: "a", AmountCents: 200},
	}
	pos := settlement.NetPositions(entries)
	if pos["a"] != 300 || pos["b"] != -50 {
		t.Fatalf("unexpected positions: %v", pos)
	}
}

func TestBilateralNet(t *testing.T) {
	a := []models.LedgerEntry{{AmountCents: 1000}}
	b := []models.LedgerEntry{{AmountCents: 300}}
	net := settlement.BilateralNet(a, b)
	if net != 700 {
		t.Fatalf("expected bilateral net 700, got %d", net)
	}
}

func TestSettlementFee(t *testing.T) {
	fee := settlement.SettlementFee(1000000, 25)
	if fee != 2500 {
		t.Fatalf("expected fee 2500 (25bp on 1M), got %d", fee)
	}
}

func TestOptimalBatching(t *testing.T) {
	entries := []models.LedgerEntry{
		{AmountCents: 100}, {AmountCents: 200}, {AmountCents: 300}, {AmountCents: 400}, {AmountCents: 500},
	}
	batches := settlement.OptimalBatching(entries, 2)
	if len(batches) != 3 {
		t.Fatalf("expected 3 batches, got %d", len(batches))
	}
}
