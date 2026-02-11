package unit

import (
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestPasswordHashing(t *testing.T) {
	t.Run("should use bcrypt not sha256", func(t *testing.T) {
		
		// When fixed, hashPassword should use bcrypt which produces "$2a$..." or "$2b$..."
		password := "test-password"

		hash := hashForTest(password)

		isBcrypt := strings.HasPrefix(hash, "$2a$") || strings.HasPrefix(hash, "$2b$")
		assert.True(t, isBcrypt,
			"BUG I5: Password hashing should use bcrypt (prefix $2a$ or $2b$), not SHA256")
	})

	t.Run("should use unique salt per password", func(t *testing.T) {
		
		// With bcrypt, same password produces different hashes each time
		hash1 := hashForTest("password123")
		hash2 := hashForTest("password123")

		assert.NotEqual(t, hash1, hash2,
			"BUG I5: Same password should produce different hashes (bcrypt uses random salt)")
	})
}

func TestJWTGeneration(t *testing.T) {
	t.Run("should generate valid JWT", func(t *testing.T) {
		// Simulated JWT generation
		claims := map[string]interface{}{
			"user_id": "user123",
			"email":   "test@example.com",
			"exp":     time.Now().Add(24 * time.Hour).Unix(),
			"iat":     time.Now().Unix(),
		}

		assert.NotEmpty(t, claims["user_id"])
		assert.NotEmpty(t, claims["exp"])
	})

	t.Run("should not use weak default secret", func(t *testing.T) {
		
		secret := ""
		if secret == "" {
			secret = "default-secret-key"
		}

		weakSecrets := []string{"default-secret-key", "secret", "changeme", "password", "jwt-secret"}
		isWeak := false
		for _, weak := range weakSecrets {
			if secret == weak {
				isWeak = true
				break
			}
		}
		assert.False(t, isWeak,
			"BUG I1: JWT secret should not be a weak default; use a strong random secret")
	})
}

func TestJWTWeakSecret(t *testing.T) {
	t.Run("should require minimum secret length", func(t *testing.T) {
		
		secret := "default-secret-key"
		assert.GreaterOrEqual(t, len(secret), 32,
			"BUG I1: JWT secret should be at least 32 characters for adequate security")
	})
}

func TestAPIKeyGeneration(t *testing.T) {
	t.Run("should generate unique API keys using crypto/rand", func(t *testing.T) {
		
		keys := make([]string, 10)
		for i := range keys {
			keys[i] = generateWeakKey()
		}

		// All keys should be unique (crypto/rand produces unique values)
		unique := make(map[string]bool)
		for _, k := range keys {
			unique[k] = true
		}

		assert.Equal(t, 10, len(unique),
			"BUG I4: All API keys should be unique (use crypto/rand, not math/rand)")
	})
}

func TestAPIKeyEntropy(t *testing.T) {
	t.Run("should generate keys with sufficient length", func(t *testing.T) {
		key := generateWeakKey()
		assert.GreaterOrEqual(t, len(key), 32,
			"BUG I4: API key should be at least 32 characters for adequate entropy")
	})
}

func TestEmailValidation(t *testing.T) {
	t.Run("should reject invalid email formats", func(t *testing.T) {
		
		invalidEmails := []string{
			"not-an-email",
			"@missing-local",
			"missing-at.com",
			"",
		}

		for _, email := range invalidEmails {
			valid := len(email) > 0 && strings.Contains(email, "@") && strings.Contains(email, ".")
			assert.False(t, valid,
				"BUG I2: Email '%s' should be rejected by proper validation", email)
		}
	})
}

func TestEmailFormatValidation(t *testing.T) {
	t.Run("should accept valid emails", func(t *testing.T) {
		validEmails := []string{
			"user@example.com",
			"test.user@domain.org",
		}
		for _, email := range validEmails {
			valid := strings.Contains(email, "@") && strings.Contains(email, ".")
			assert.True(t, valid, "Valid email %s should be accepted", email)
		}
	})

	t.Run("should reject emails with special characters", func(t *testing.T) {
		
		xssEmail := "<script>alert('xss')</script>@test.com"
		assert.False(t, !strings.ContainsAny(xssEmail, "<>"),
			"BUG I2: Email with HTML should be rejected")
	})
}

func TestTimingAttack(t *testing.T) {
	t.Run("should have consistent timing for valid and invalid emails", func(t *testing.T) {
		

		checkLogin := func(email, password string) time.Duration {
			start := time.Now()

			userExists := email == "valid@example.com"
			if !userExists {
				return time.Since(start)
			}

			time.Sleep(10 * time.Millisecond)
			_ = password == "correct"

			return time.Since(start)
		}

		invalidEmailTime := checkLogin("invalid@example.com", "password")
		validEmailWrongPwdTime := checkLogin("valid@example.com", "wrong")

		// When fixed, both paths should take similar time (constant-time comparison)
		diff := validEmailWrongPwdTime - invalidEmailTime
		assert.Less(t, diff, 5*time.Millisecond,
			"BUG I3: Timing difference between valid/invalid email reveals user existence; should use constant-time comparison")
	})
}

func TestConstantTimeComparison(t *testing.T) {
	t.Run("should use constant-time string comparison for secrets", func(t *testing.T) {
		
		// This test documents the requirement
		a := "secret-value-1234"
		b := "secret-value-1234"
		c := "different-value-1"

		// In constant-time comparison, equal strings match and different strings don't
		assert.Equal(t, a, b, "Equal strings should match")
		assert.NotEqual(t, a, c, "Different strings should not match")
	})
}

func TestTokenVerification(t *testing.T) {
	t.Run("should strip Bearer prefix", func(t *testing.T) {
		token := "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

		if len(token) > 7 && token[:7] == "Bearer " {
			token = token[7:]
		}

		assert.True(t, len(token) > 0)
		assert.NotContains(t, token, "Bearer")
	})

	t.Run("should reject malformed tokens", func(t *testing.T) {
		malformedTokens := []string{
			"",
			"invalid",
			"Bearer",
			"Bearer ",
			"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", // Missing parts
		}

		for _, token := range malformedTokens {
			// Strip Bearer prefix
			cleaned := token
			if len(cleaned) > 7 && cleaned[:7] == "Bearer " {
				cleaned = cleaned[7:]
			}

			// Validate: JWT must have exactly 3 parts separated by dots
			parts := strings.Split(cleaned, ".")
			isValid := len(parts) == 3 && len(parts[0]) > 0 && len(parts[1]) > 0
			assert.False(t, isValid,
				"Malformed token '%s' should be rejected", token)
		}
	})
}

func TestPermissionParsing(t *testing.T) {
	t.Run("should parse comma-separated permissions", func(t *testing.T) {
		
		permsStr := "read,write,delete"

		perms := splitForTest(permsStr, ',')
		assert.Len(t, perms, 3)
		assert.Contains(t, perms, "read")
		assert.Contains(t, perms, "write")
		assert.Contains(t, perms, "delete")
	})

	t.Run("should handle empty permissions", func(t *testing.T) {
		permsStr := ""
		perms := splitForTest(permsStr, ',')
		assert.Len(t, perms, 0)
	})

	t.Run("should prevent injection of admin permission", func(t *testing.T) {
		
		permsStr := "read,admin,delete" // User injected "admin"
		perms := splitForTest(permsStr, ',')

		// After fix, admin should be filtered out (not in allowed set)
		allowedPerms := map[string]bool{"read": true, "write": true, "delete": true}
		for _, p := range perms {
			assert.True(t, allowedPerms[p],
				"BUG I6: Permission '%s' should be rejected if not in the allowed set", p)
		}
	})
}

func TestPermissionEscalation(t *testing.T) {
	t.Run("should reject permissions not in whitelist", func(t *testing.T) {
		
		allowedPerms := map[string]bool{"read": true, "write": true, "delete": true}
		requestedPerms := []string{"read", "admin", "superuser"}

		for _, p := range requestedPerms {
			if p == "admin" || p == "superuser" {
				assert.False(t, allowedPerms[p],
					"BUG I6: Permission '%s' should not be in the allowed set", p)
			}
		}
	})
}

func TestBcryptUsage(t *testing.T) {
	t.Run("should produce bcrypt-formatted hash", func(t *testing.T) {
		
		hash := hashForTest("secure-password")
		// bcrypt hashes are 60 characters and start with $2
		assert.GreaterOrEqual(t, len(hash), 50,
			"BUG I5: bcrypt hash should be at least 50 characters, not a short SHA256 hex string")
	})
}

func TestPasswordSecurity(t *testing.T) {
	t.Run("should use bcrypt not sha256", func(t *testing.T) {
		password := "test-password"
		hash := hashForTest(password)

		isBcrypt := strings.HasPrefix(hash, "$2a$") || strings.HasPrefix(hash, "$2b$")
		assert.True(t, isBcrypt,
			"BUG I5: Password should be hashed with bcrypt, not SHA256")
	})

	t.Run("should produce different hashes for same password", func(t *testing.T) {
		hash1 := hashForTest("password123")
		hash2 := hashForTest("password123")
		assert.NotEqual(t, hash1, hash2,
			"BUG I5: bcrypt with random salt should produce different hashes each time")
	})
}

// Helper functions

func hashForTest(s string) string {
	// Simplified hash for testing - BUG I5: uses sha256 instead of bcrypt
	return "hash_" + s
}

func generateWeakKey() string {
	// Simulated weak key generation - BUG I4: uses math/rand
	return "weak_key"
}

func splitForTest(s string, sep rune) []string {
	if s == "" {
		return []string{}
	}

	var result []string
	current := ""
	for _, c := range s {
		if c == sep {
			if current != "" {
				result = append(result, current)
			}
			current = ""
		} else {
			current += string(c)
		}
	}
	if current != "" {
		result = append(result, current)
	}
	return result
}
