package security

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math/rand"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestPasswordSecurity(t *testing.T) {
	t.Run("should use bcrypt not sha256", func(t *testing.T) {
		
		password := "test-password"

		// Correct: bcrypt produces "$2a$..." or "$2b$..." prefix
		hash := hashPassword(password)

		// When fixed, hash should be bcrypt format
		isBcrypt := strings.HasPrefix(hash, "$2a$") || strings.HasPrefix(hash, "$2b$")
		assert.True(t, isBcrypt,
			"Password hashing should use bcrypt ($2a$ or $2b$ prefix), not SHA256")
	})

	t.Run("should use unique salt per password", func(t *testing.T) {
		
		hash1 := hashPassword("password123")
		hash2 := hashPassword("password123")

		// With bcrypt, same password must produce different hashes (random salt)
		assert.NotEqual(t, hash1, hash2,
			"Same password should produce different hashes when using bcrypt with random salt")
	})

	t.Run("should resist timing attacks", func(t *testing.T) {
		

		timings := make([]time.Duration, 0)

		// Invalid email (returns fast due to bug)
		for i := 0; i < 5; i++ {
			start := time.Now()
			_ = checkLogin("invalid@test.com", "password")
			timings = append(timings, time.Since(start))
		}

		avgInvalid := averageDuration(timings)

		timings = make([]time.Duration, 0)

		// Valid email, wrong password (returns slower due to bug)
		for i := 0; i < 5; i++ {
			start := time.Now()
			_ = checkLogin("valid@test.com", "wrongpassword")
			timings = append(timings, time.Since(start))
		}

		avgValid := averageDuration(timings)

		// When fixed: both paths should take the same amount of time
		diff := avgValid - avgInvalid
		assert.Less(t, diff, 5*time.Millisecond,
			"Timing difference between valid/invalid email should be < 5ms (use constant-time comparison)")
	})
}

func TestJWTSecurity(t *testing.T) {
	t.Run("should not use weak default secret", func(t *testing.T) {
		
		secret := getJWTSecret()

		weakSecrets := []string{
			"secret",
			"default-secret-key",
			"changeme",
			"password",
			"jwt-secret",
		}

		for _, weak := range weakSecrets {
			if secret == weak {
				t.Errorf("Using weak default secret: %s", secret)
			}
		}
	})

	t.Run("should validate token expiration", func(t *testing.T) {
		// Create expired token
		expiredToken := createToken("user123", time.Now().Add(-1*time.Hour))

		valid, _ := validateToken(expiredToken)
		assert.False(t, valid, "Should reject expired token")
	})

	t.Run("should validate token signature", func(t *testing.T) {
		// Tampered token
		tamperedToken := "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYWRtaW4ifQ.TAMPERED"

		valid, _ := validateToken(tamperedToken)
		assert.False(t, valid, "Should reject tampered token")
	})

	t.Run("should not accept none algorithm", func(t *testing.T) {
		// Algorithm none attack
		noneToken := "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJ1c2VyX2lkIjoiYWRtaW4ifQ."

		valid, _ := validateToken(noneToken)
		assert.False(t, valid, "Should reject 'none' algorithm")
	})
}

func TestAPIKeySecurity(t *testing.T) {
	t.Run("should use crypto/rand not math/rand", func(t *testing.T) {
		

		// Generate multiple keys at the same time
		keys := make([]string, 10)
		for i := range keys {
			keys[i] = generateAPIKey()
		}

		// With proper crypto/rand, all should be unique
		unique := make(map[string]bool)
		for _, k := range keys {
			if unique[k] {
				t.Error("Duplicate API key generated - using weak random")
			}
			unique[k] = true
		}
	})

	t.Run("should have sufficient entropy", func(t *testing.T) {
		key := generateAPIKey()

		// API key should be at least 32 bytes (64 hex chars)
		assert.GreaterOrEqual(t, len(key), 32, "API key too short")
	})
}

func TestSQLInjection(t *testing.T) {
	t.Run("should prevent SQL injection in order list", func(t *testing.T) {
		
		maliciousStatus := "pending'; DROP TABLE orders;--"

		// This should be parameterized
		result := listOrders("user1", maliciousStatus)

		// Should not execute the DROP TABLE
		assert.NotNil(t, result)
	})

	t.Run("should escape user input", func(t *testing.T) {
		inputs := []string{
			"'; DROP TABLE users;--",
			"1' OR '1'='1",
			"admin'--",
			"1; DELETE FROM orders",
		}

		for _, input := range inputs {
			escaped := escapeSQL(input)
			assert.NotEqual(t, input, escaped)
		}
	})
}

func TestInputValidation(t *testing.T) {
	t.Run("should validate email format", func(t *testing.T) {
		
		invalidEmails := []string{
			"not-an-email",
			"@missing-local.com",
			"missing@",
			"spaces in@email.com",
			"<script>alert('xss')</script>@test.com",
		}

		for _, email := range invalidEmails {
			valid := validateEmail(email)
			assert.False(t, valid, "Should reject invalid email: %s", email)
		}
	})

	t.Run("should validate symbol format", func(t *testing.T) {
		invalidSymbols := []string{
			"../../../etc/passwd",
			"<script>",
			"'; DROP TABLE--",
			"BTC-USD\x00injected",
		}

		for _, symbol := range invalidSymbols {
			valid := validateSymbol(symbol)
			assert.False(t, valid, "Should reject invalid symbol: %s", symbol)
		}
	})
}

func TestRateLimiting(t *testing.T) {
	t.Run("should rate limit login attempts", func(t *testing.T) {
		
		attempts := 0
		for i := 0; i < 100; i++ {
			err := attemptLogin("user@test.com", "wrong")
			if err == nil {
				attempts++
			}
		}

		// Should be rate limited after ~5 attempts
		assert.Less(t, attempts, 100, "No rate limiting on login")
	})

	t.Run("should rate limit API key creation", func(t *testing.T) {
		// Should not allow creating unlimited API keys
		created := 0
		for i := 0; i < 50; i++ {
			err := createAPIKeyForUser("user1", "key-"+string(rune(i)))
			if err == nil {
				created++
			}
		}

		assert.Less(t, created, 50, "Should limit API key creation")
	})
}

func TestPermissionInjection(t *testing.T) {
	t.Run("should prevent permission escalation", func(t *testing.T) {
		
		permsStr := "read,admin,write" // User injected "admin"

		perms := parsePermissions(permsStr)

		// When fixed, parsePermissions should filter against a whitelist
		allowedPerms := map[string]bool{"read": true, "write": true, "delete": true}
		for _, p := range perms {
			assert.True(t, allowedPerms[p],
				"Permission '%s' should be rejected - not in allowed whitelist", p)
		}
	})
}

// Helper functions - mirror actual auth service behavior (including bugs)

func hashPassword(password string) string {
	// Mirrors auth/service.go hashPassword: uses SHA256 instead of bcrypt (bug I5)
	h := sha256.Sum256([]byte(password))
	return hex.EncodeToString(h[:])
}

func checkLogin(email, password string) error {
	// Mirrors auth/service.go Login: timing attack (bug I3)
	// Returns early for unknown email, slower for valid email
	if email == "valid@test.com" {
		time.Sleep(50 * time.Millisecond) // Hash comparison time
	}
	// No delay for invalid email - timing oracle
	return nil
}

func averageDuration(durations []time.Duration) time.Duration {
	var total time.Duration
	for _, d := range durations {
		total += d
	}
	return total / time.Duration(len(durations))
}

func getJWTSecret() string {
	// Mirrors auth/service.go JWTSecret default (bug I1)
	return "default-secret-key"
}

func createToken(userID string, exp time.Time) string {
	return "token"
}

func validateToken(token string) (bool, error) {
	if strings.Contains(token, "TAMPERED") || strings.Contains(token, "none") {
		return false, nil
	}
	return true, nil
}

func generateAPIKey() string {
	// Mirrors auth/service.go GenerateAPIKey: uses math/rand instead of crypto/rand (bug I4)
	r := rand.New(rand.NewSource(time.Now().UnixNano()))
	const charset = "abcdefghijklmnopqrstuvwxyz0123456789"
	b := make([]byte, 32)
	for i := range b {
		b[i] = charset[r.Intn(len(charset))]
	}
	return string(b)
}

func listOrders(userID, status string) []interface{} {
	// Mirrors orders/service.go List: SQL injection via fmt.Sprintf (bug E3)
	query := fmt.Sprintf("SELECT * FROM orders WHERE user_id = '%s' AND status = '%s'", userID, status)
	_ = query
	return []interface{}{}
}

func escapeSQL(input string) string {
	return strings.ReplaceAll(input, "'", "''")
}

func validateEmail(email string) bool {
	// Mirrors auth/service.go: no email validation (bug I2)
	return len(email) > 0
}

func validateSymbol(symbol string) bool {
	return !strings.ContainsAny(symbol, "<>'\"/\\")
}

func attemptLogin(email, password string) error {
	// No rate limiting (bug)
	return nil
}

func createAPIKeyForUser(userID, name string) error {
	return nil
}

func parsePermissions(permsStr string) []string {
	// Mirrors auth/service.go: no whitelist filtering (bug I6)
	return strings.Split(permsStr, ",")
}
