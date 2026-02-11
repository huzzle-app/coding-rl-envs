package unit_test

import (
	"testing"

	"quorumledger/internal/ledger"
	"quorumledger/pkg/models"
)

func TestApplyEntries(t *testing.T) {
	balances := map[string]int64{"a": 1000, "b": 500}
	entries := []models.LedgerEntry{{Account: "a", AmountCents: -250, Sequence: 1}, {Account: "b", AmountCents: 250, Sequence: 1}}
	out := ledger.ApplyEntries(balances, entries)
	if out["a"] != 750 || out["b"] != 750 {
		t.Fatalf("unexpected balances: %#v", out)
	}
}

func TestValidateSequence(t *testing.T) {
	valid := []models.LedgerEntry{{Account: "a", Sequence: 1}, {Account: "a", Sequence: 2}}
	invalid := []models.LedgerEntry{{Account: "a", Sequence: 2}, {Account: "a", Sequence: 1}}
	if !ledger.ValidateSequence(valid) {
		t.Fatalf("expected valid sequence")
	}
	if ledger.ValidateSequence(invalid) {
		t.Fatalf("expected invalid sequence")
	}
}

func TestNetExposure(t *testing.T) {
	entries := []models.LedgerEntry{{AmountCents: 1200}, {AmountCents: -300}, {AmountCents: -100}}
	if ledger.NetExposure(entries) != 800 {
		t.Fatalf("unexpected exposure")
	}
}

func TestDoubleEntryValid(t *testing.T) {
	balanced := []models.LedgerEntry{{Account: "a", AmountCents: 500}, {Account: "b", AmountCents: -500}}
	if !ledger.DoubleEntryValid(balanced) {
		t.Fatalf("expected balanced double entry")
	}
}

func TestDetectOverdraft(t *testing.T) {
	balances := map[string]int64{"a": 100, "b": 500, "c": 0}
	entries := []models.LedgerEntry{{Account: "a", AmountCents: -200}, {Account: "b", AmountCents: -100}}
	overdrawn := ledger.DetectOverdraft(balances, entries)
	if len(overdrawn) != 1 || overdrawn[0] != "a" {
		t.Fatalf("expected only account a overdrawn, got %v", overdrawn)
	}
}

func TestMergeBalances(t *testing.T) {
	a := map[string]int64{"x": 100, "y": 200}
	b := map[string]int64{"y": 300, "z": 400}
	merged := ledger.MergeBalances(a, b)
	if merged["x"] != 100 || merged["y"] != 500 || merged["z"] != 400 {
		t.Fatalf("unexpected merged balances: %v", merged)
	}
}

func TestHighValueEntries(t *testing.T) {
	entries := []models.LedgerEntry{
		{AmountCents: 500},
		{AmountCents: 1500},
		{AmountCents: -2000},
		{AmountCents: 800},
	}
	high := ledger.HighValueEntries(entries, 1000)
	if len(high) != 2 {
		t.Fatalf("expected 2 high value entries, got %d", len(high))
	}
}

func TestSequenceGaps(t *testing.T) {
	entries := []models.LedgerEntry{
		{Account: "a", Sequence: 1},
		{Account: "a", Sequence: 3},
		{Account: "b", Sequence: 1},
		{Account: "b", Sequence: 2},
	}
	gapped := ledger.SequenceGaps(entries)
	if len(gapped) != 1 || gapped[0] != "a" {
		t.Fatalf("expected gap in account a, got %v", gapped)
	}
}
