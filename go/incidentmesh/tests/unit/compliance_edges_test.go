package unit

import (
	"testing"
	"incidentmesh/internal/compliance"
	"incidentmesh/pkg/models"
)

func TestOverrideReasonBoundary(t *testing.T) {
	if compliance.ValidOverrideReason("short") { t.Fatalf("too short") }
}

func TestOverrideReasonLong(t *testing.T) {
	if !compliance.ValidOverrideReason("this is a valid override reason") { t.Fatalf("should be valid") }
}

func TestComplianceExtended(t *testing.T) {
	cases := []struct{ name string; fn func(t *testing.T) }{
		{"AuditTrail", func(t *testing.T) {
			trail := compliance.AuditTrail([]models.AuditRecord{{ID:"a1",Action:"create"},{ID:"a2",Action:"update"}})
			if len(trail) != 2 { t.Fatalf("expected 2") }
		}},
		{"CompCheck", func(t *testing.T) {
			ok := compliance.ComplianceCheck("create", []string{"create","update"})
			if !ok { t.Fatalf("expected allowed") }
		}},
		{"CompCheckCase", func(t *testing.T) {
			ok := compliance.ComplianceCheck("Create", []string{"create"})
			
			if !ok { t.Fatalf("expected case-insensitive match") }
		}},
		{"Retention1", func(t *testing.T) {
			if compliance.RetentionDays(1) != 365 { t.Fatalf("expected 365") }
		}},
		{"Retention2", func(t *testing.T) {
			d := compliance.RetentionDays(2)
			
			if d != 180 { t.Fatalf("expected 180 days for tier 2, got %d", d) }
		}},
		{"Retention3", func(t *testing.T) {
			if compliance.RetentionDays(3) != 30 { t.Fatalf("expected 30") }
		}},
		{"ValidateRecord", func(t *testing.T) {
			ok := compliance.ValidateAuditRecord(models.AuditRecord{ID:"a1",Action:"create"})
			if !ok { t.Fatalf("expected valid") }
		}},
		{"ValidateEmpty", func(t *testing.T) {
			if compliance.ValidateAuditRecord(models.AuditRecord{}) { t.Fatalf("expected invalid") }
		}},
		{"AuditOrder", func(t *testing.T) {
			recs := compliance.AuditOrdering([]models.AuditRecord{{Timestamp:100},{Timestamp:50},{Timestamp:200}})
			if len(recs) != 3 { t.Fatalf("expected 3") }
		}},
		{"CompScore", func(t *testing.T) {
			s := compliance.ComplianceScore(7, 10)
			
			if s < 0.69 || s > 0.71 { t.Fatalf("expected 0.7 (7/10), got %.2f", s) }
		}},
		{"CompScoreZero", func(t *testing.T) {
			if compliance.ComplianceScore(0, 0) != 0 { t.Fatalf("expected 0") }
		}},
		{"RequiredFields", func(t *testing.T) {
			f := compliance.RequiredFields("create")
			if len(f) < 3 { t.Fatalf("expected at least 3") }
		}},
		{"RequiredFieldsOverride", func(t *testing.T) {
			f := compliance.RequiredFields("override.action")
			
			hasReason := false
			for _, field := range f {
				if field == "reason" { hasReason = true }
			}
			if !hasReason { t.Fatalf("override actions should require 'reason' field") }
		}},
		{"RetentionPolicy", func(t *testing.T) {
			// Records at timestamp 100 and 500, maxAge=1 day, now=1000
			// Record at 100: age=900 > 86400? No. Record at 500: age=500 > 86400? No.
			// Both should be kept. BUG(K04): keeps expired, removes valid
			recs := compliance.RetentionPolicy([]models.AuditRecord{{Timestamp:100},{Timestamp:500}}, 1, 1000)
			if len(recs) != 2 { t.Fatalf("both records are recent, expected 2 kept, got %d", len(recs)) }
		}},
	}
	for _, tc := range cases { t.Run(tc.name, tc.fn) }
}
