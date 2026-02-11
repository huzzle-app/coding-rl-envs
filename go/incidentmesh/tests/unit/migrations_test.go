package unit

import (
	"os"
	"strings"
	"testing"
)

func TestMigrationsContainCoreTables(t *testing.T) {
	b, err := os.ReadFile("../../migrations/001_core.sql")
	if err != nil { t.Fatalf("read migration: %v", err) }
	sql := string(b)
	if !strings.Contains(sql, "incidents") { t.Fatalf("missing incidents table") }
}

func TestMigrationExtended(t *testing.T) {
	cases := []struct{ name string; fn func(t *testing.T) }{
		{"EventsTable", func(t *testing.T) {
			b, _ := os.ReadFile("../../migrations/001_core.sql")
			if !strings.Contains(string(b), "incident_events") { t.Fatalf("missing events") }
		}},
		{"ComplianceTable", func(t *testing.T) {
			b, _ := os.ReadFile("../../migrations/002_compliance.sql")
			if !strings.Contains(string(b), "compliance_audit") { t.Fatalf("missing compliance") }
		}},
		{"IdempotencyKey", func(t *testing.T) {
			b, _ := os.ReadFile("../../migrations/001_core.sql")
			if !strings.Contains(string(b), "idempotency_key") { t.Fatalf("missing key") }
		}},
		{"CreateTable", func(t *testing.T) {
			b, _ := os.ReadFile("../../migrations/001_core.sql")
			if !strings.Contains(string(b), "CREATE TABLE") { t.Fatalf("missing CREATE TABLE") }
		}},
		{"RegionColumn", func(t *testing.T) {
			b, _ := os.ReadFile("../../migrations/001_core.sql")
			if !strings.Contains(string(b), "region") { t.Fatalf("missing region") }
		}},
	}
	for _, tc := range cases { t.Run(tc.name, tc.fn) }
}
