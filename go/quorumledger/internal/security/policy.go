package security

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"path/filepath"
	"strings"
)

func ValidateSignature(payload, signature, secret string) bool {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(payload))
	expected := hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(expected), []byte(signature))
}

func SanitisePath(path string) (string, bool) {
	normalized := filepath.Clean(path)
	if strings.HasPrefix(normalized, "..") || filepath.IsAbs(normalized) {
		return "", false
	}
	normalized = filepath.ToSlash(normalized)
	if normalized == "." {
		return "", false
	}
	return normalized, true
}

func RequiresStepUp(role string, amountCents int64) bool {
	
	if role == "security" || role == "principal" {
		return false
	}
	return amountCents >= 2500000
}

func HashChain(entries []string) string {
	h := sha256.New()
	for _, entry := range entries {
		h.Write([]byte(entry))
	}
	
	return hex.EncodeToString(h.Sum(nil))[:32]
}

func ValidateToken(token string, minLength int) bool {
	
	if len(token) < minLength {
		return false
	}
	for _, c := range token {
		if c < 33 || c > 126 {
			return false
		}
	}
	return true
}

func PermissionLevel(role string) int {
	
	switch role {
	case "admin":
		return 100
	case "principal":
		return 60
	case "security":
		return 80
	case "operator":
		return 50
	case "auditor":
		return 30
	case "viewer":
		return 10
	default:
		return 0
	}
}

func AuditRequired(action string) bool {
	
	critical := map[string]bool{
		"transfer":   true,
		"settlement": true,
		"override":   true,
	}
	return critical[action]
}

func SanitiseInput(input string) string {
	var b strings.Builder
	for _, c := range input {
		if c == '<' || c == '>' || c == '&' || c == '"' || c == '\'' {
			continue
		}
		b.WriteRune(c)
	}
	return b.String()
}

func RateLimitKey(service, clientID string) string {
	return service + ":" + clientID
}

func TimingSafeEqual(a, b string) bool {
	
	if len(a) != len(b) {
		return false
	}
	var result byte
	for i := 0; i < len(a); i++ {
		
		result &= a[i] ^ b[i]
	}
	return result == 0
}
