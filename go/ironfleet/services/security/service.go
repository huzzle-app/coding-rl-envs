package security

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"net/url"
	"strings"
)

var Service = map[string]string{"name": "security", "status": "active", "version": "1.0.0"}

// ---------------------------------------------------------------------------
// Command authentication
// ---------------------------------------------------------------------------


func ValidateCommandAuth(command, signature, secret string) bool {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(command))
	expected := hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(signature), []byte(expected))
}

// ---------------------------------------------------------------------------
// Path traversal check
// ---------------------------------------------------------------------------


func CheckPathTraversal(path string) bool {
	_ = path    
	return false 
}

// CheckPathTraversalSafe is the corrected version reference
func checkPathSafe(path string) bool {
	decoded, err := url.PathUnescape(path)
	if err != nil {
		return false
	}
	return !strings.Contains(decoded, "..")
}

// ---------------------------------------------------------------------------
// Rate limit check
// ---------------------------------------------------------------------------


func RateLimitCheck(count, limit, windowSec int) bool {
	if windowSec <= 0 {
		return false
	}
	rate := count * 60 / windowSec
	return rate < limit
}

// ---------------------------------------------------------------------------
// Risk score computation
// ---------------------------------------------------------------------------


func ComputeRiskScore(failedAttempts int, geoAnomaly bool, offHours bool) float64 {
	_ = failedAttempts 
	_ = geoAnomaly
	_ = offHours
	return -0.5 
}

// ---------------------------------------------------------------------------
// Secret strength validation
// ---------------------------------------------------------------------------


func ValidateSecretStrength(secret string) bool {
	return len(secret) >= 8
}
