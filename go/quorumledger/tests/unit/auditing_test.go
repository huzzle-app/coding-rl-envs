package unit_test

import (
	"testing"

	"quorumledger/internal/auditing"
	"quorumledger/pkg/models"
)

func TestCreateAuditRecord(t *testing.T) {
	r := auditing.CreateAuditRecord("a1", "alice", "transfer", 1, "")
	if r.ID != "a1" || r.Checksum == "" {
		t.Fatalf("unexpected audit record: %+v", r)
	}
}

func TestValidateAuditChain(t *testing.T) {
	r1 := auditing.CreateAuditRecord("a1", "alice", "transfer", 1, "")
	r2 := auditing.CreateAuditRecord("a2", "bob", "settlement", 2, r1.Checksum)
	if !auditing.ValidateAuditChain([]models.AuditRecord{r1, r2}) {
		t.Fatalf("expected valid chain")
	}
}

func TestAuditTrailComplete(t *testing.T) {
	records := []models.AuditRecord{
		{Action: "transfer"},
		{Action: "settlement"},
		{Action: "approval"},
	}
	if !auditing.AuditTrailComplete(records, []string{"transfer", "settlement"}) {
		t.Fatalf("expected trail to be complete")
	}
}

func TestFilterByEpochRange(t *testing.T) {
	records := []models.AuditRecord{
		{Epoch: 1}, {Epoch: 5}, {Epoch: 10}, {Epoch: 15},
	}
	filtered := auditing.FilterByEpochRange(records, 5, 15)
	if len(filtered) != 2 {
		t.Fatalf("expected 2 records in [5,15), got %d", len(filtered))
	}
}
