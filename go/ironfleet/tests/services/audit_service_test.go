package services

import (
	"ironfleet/services/audit"
	"testing"
	"time"
)

func TestValidateAuditEntryRequiresFields(t *testing.T) {
	ok := audit.ValidateAuditEntry(audit.AuditEntry{Service: "gw", Action: "route", UserID: "u1"})
	if !ok {
		t.Fatal("expected valid entry")
	}
	bad := audit.ValidateAuditEntry(audit.AuditEntry{Service: "", Action: "route", UserID: "u1"})
	if bad {
		t.Fatal("expected invalid entry")
	}
}

func TestSummarizeTrailReturnsCorrectRate(t *testing.T) {
	trail := audit.AuditTrail{Entries: []audit.AuditEntry{
		{Service: "gw", Action: "route", UserID: "u1", Success: true, Timestamp: time.Now()},
		{Service: "gw", Action: "route", UserID: "u2", Success: false, Timestamp: time.Now()},
	}}
	total, rate := audit.SummarizeTrail(trail)
	if total != 2 {
		t.Fatalf("expected 2 entries, got %d", total)
	}
	if rate < 0 || rate > 1.0 {
		t.Fatalf("rate out of range: %f", rate)
	}
}

func TestIsCompliantChecksRequiredServices(t *testing.T) {
	trail := audit.AuditTrail{Entries: []audit.AuditEntry{
		{Service: "gateway", Action: "check", UserID: "u1", Timestamp: time.Now()},
		{Service: "routing", Action: "check", UserID: "u1", Timestamp: time.Now()},
	}}
	if !audit.IsCompliant(trail, []string{"gateway", "routing"}) {
		t.Fatal("expected compliant")
	}
}

func TestFilterByServiceReturnsMatches(t *testing.T) {
	trail := audit.AuditTrail{Entries: []audit.AuditEntry{
		{Service: "gateway", Action: "a", UserID: "u1", Timestamp: time.Now()},
		{Service: "routing", Action: "b", UserID: "u1", Timestamp: time.Now()},
	}}
	filtered := audit.FilterByService(trail, "gateway")
	if len(filtered) == 0 {
		t.Fatal("expected gateway entries")
	}
}
