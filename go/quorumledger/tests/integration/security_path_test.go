package integration_test

import (
	"testing"

	"quorumledger/internal/security"
)

func TestSecurityPathIntegration(t *testing.T) {
	path, ok := security.SanitisePath("audit/../audit/entry.log")
	if !ok || path != "audit/entry.log" {
		t.Fatalf("unexpected sanitised path: %s", path)
	}
	if _, ok := security.SanitisePath("/etc/passwd"); ok {
		t.Fatalf("absolute paths must be rejected")
	}
}
