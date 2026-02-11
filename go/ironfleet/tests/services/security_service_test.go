package services

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"ironfleet/services/security"
	"testing"
)

func TestValidateCommandAuthCorrectSignature(t *testing.T) {
	secret := "test-secret-key"
	command := "DEPLOY:fleet-alpha"
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(command))
	sig := hex.EncodeToString(mac.Sum(nil))
	if !security.ValidateCommandAuth(command, sig, secret) {
		t.Fatal("expected valid auth")
	}
}

func TestCheckPathTraversalBlocksDotDot(t *testing.T) {
	if !security.CheckPathTraversal("/safe/path/file.txt") {
		t.Fatal("expected safe path to pass")
	}
	if security.CheckPathTraversal("../../etc/passwd") {
		t.Fatal("expected path traversal to be blocked")
	}
}

func TestRateLimitCheckRespectsLimit(t *testing.T) {
	if !security.RateLimitCheck(5, 10, 60) {
		t.Fatal("expected under limit")
	}
	if security.RateLimitCheck(10, 10, 60) {
		t.Fatal("expected at limit to be blocked")
	}
}

func TestComputeRiskScoreInRange(t *testing.T) {
	score := security.ComputeRiskScore(3, true, true)
	if score < 0 || score > 1.0 {
		t.Fatalf("score out of range: %f", score)
	}
}
