package unit

import (
	"os"
	"strings"
	"testing"
)

func TestMigrationsContainCoreTables(t *testing.T) {
	core, err := os.ReadFile("../../migrations/001_core.sql")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(core), "CREATE TABLE IF NOT EXISTS grid_commands") {
		t.Fatalf("missing grid_commands table")
	}
	dispatchSQL, err := os.ReadFile("../../migrations/002_dispatch.sql")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(dispatchSQL), "CREATE TABLE IF NOT EXISTS dispatch_plans") {
		t.Fatalf("missing dispatch_plans table")
	}
}
