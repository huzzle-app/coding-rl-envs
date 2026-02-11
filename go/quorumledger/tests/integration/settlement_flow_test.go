package integration_test

import (
	"testing"

	"quorumledger/internal/ledger"
	"quorumledger/internal/workflow"
	"quorumledger/pkg/models"
)

func TestSettlementFlowIntegration(t *testing.T) {
	windows := []models.SettlementWindow{{ID: "w1", OpenMinute: 10, CloseMinute: 20, Capacity: 2}, {ID: "w2", OpenMinute: 20, CloseMinute: 30, Capacity: 2}}
	assignments := workflow.PlanSettlement(windows, 3)
	if len(assignments) != 3 {
		t.Fatalf("expected 3 assignments")
	}
	balances := ledger.ApplyEntries(map[string]int64{"acct-a": 1000}, []models.LedgerEntry{{Account: "acct-a", AmountCents: -200, Sequence: 1}})
	if balances["acct-a"] != 800 {
		t.Fatalf("unexpected settlement balance")
	}
}
