package integration

import (
	"testing"

	"incidentmesh/internal/security"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
)

func TestSecurityIntegration(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"AdminCreate", func(t *testing.T) {
			if !security.Authorize("admin", "incident.create") {
				t.Fatalf("admin should create")
			}
		}},
		{"DispatcherWorkflow", func(t *testing.T) {
			i := models.Incident{Severity: 3, Region: "north", Criticality: 2}
			_ = triage.PriorityScore(i)
			if !security.Authorize("dispatcher", "incident.create") {
				t.Fatalf("dispatcher should create")
			}
		}},
		{"ObserverRestricted", func(t *testing.T) {
			if security.Authorize("observer", "incident.create") {
				t.Fatalf("observer denied")
			}
		}},
		{"TokenAndSession", func(t *testing.T) {
			valid := security.ValidateToken("long-enough-token-here")
			if !valid { t.Fatalf("expected valid token") }
			sessionOk := security.SessionValid(2000, 1000)
			// Session expires at 2000, now is 1000 - should be valid
			if !sessionOk { t.Fatalf("expected valid session (now < expiry)") }
		}},
		{"RateLimitFlow", func(t *testing.T) {
			for i := 0; i < 5; i++ {
				if !security.RateLimitCheck(i, 10) {
					t.Fatalf("should be allowed")
				}
			}
		}},
		{"RegionValidation", func(t *testing.T) {
			if !security.ValidateRegion("north", []string{"north", "south", "east", "west"}) {
				t.Fatalf("expected valid")
			}
		}},
		{"AuditFlow", func(t *testing.T) {
			a := security.AuditAction("admin", "create.incident")
			if a == "" {
				t.Fatalf("expected audit")
			}
		}},
		{"EncryptionFlow", func(t *testing.T) {
			e := security.EncryptField("sensitive-data", "encryption-key")
			// Should be encrypted, not returned as-is
			if e == "sensitive-data" { t.Fatalf("expected encrypted output") }
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
