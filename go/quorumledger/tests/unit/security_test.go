package unit_test

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"testing"

	"quorumledger/internal/security"
)

func TestValidateSignature(t *testing.T) {
	payload := "batch-apply"
	secret := "top-secret"
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(payload))
	sig := hex.EncodeToString(mac.Sum(nil))
	if !security.ValidateSignature(payload, sig, secret) {
		t.Fatalf("expected valid signature")
	}
}

func TestSanitisePath(t *testing.T) {
	normalized, ok := security.SanitisePath("logs/../logs/out.txt")
	if !ok || normalized != "logs/out.txt" {
		t.Fatalf("unexpected path sanitation result: %s %v", normalized, ok)
	}
	_, ok = security.SanitisePath("../../etc/passwd")
	if ok {
		t.Fatalf("expected unsafe path rejection")
	}
}

func TestRequiresStepUp(t *testing.T) {
	if !security.RequiresStepUp("operator", 2500000) {
		t.Fatalf("expected step-up for large amount")
	}
}

func TestPermissionLevel(t *testing.T) {
	if security.PermissionLevel("security") != 70 {
		t.Fatalf("expected 70 for security role, got %d", security.PermissionLevel("security"))
	}
	if security.PermissionLevel("admin") != 100 {
		t.Fatalf("expected 100 for admin")
	}
}

func TestValidateToken(t *testing.T) {
	good := "abcdefghijklmnop"
	if !security.ValidateToken(good, 16) {
		t.Fatalf("expected valid 16-char token")
	}
	short := "abc"
	if security.ValidateToken(short, 16) {
		t.Fatalf("expected short token rejection")
	}
}

func TestAuditRequired(t *testing.T) {
	if !security.AuditRequired("escalation") {
		t.Fatalf("expected escalation to require audit")
	}
	if security.AuditRequired("read") {
		t.Fatalf("expected read to not require audit")
	}
}
