package unit_test

import (
	"os"
	"strings"
	"testing"
)

func TestMigrationsContainCoreTables(t *testing.T) {
	content, err := os.ReadFile("../../migrations/001_core.sql")
	if err != nil {
		t.Fatalf("failed to read migration: %v", err)
	}
	text := string(content)
	if !strings.Contains(text, "ledger_entries") || !strings.Contains(text, "quorum_votes") {
		t.Fatalf("core migration missing expected tables")
	}
}
