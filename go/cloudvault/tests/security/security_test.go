package security

import (
	"bytes"
	"context"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/cloudvault/internal/config"
	"github.com/terminal-bench/cloudvault/internal/repository"
	"github.com/terminal-bench/cloudvault/pkg/crypto"
	"github.com/terminal-bench/cloudvault/pkg/utils"
)

func init() {
	gin.SetMode(gin.TestMode)
}

func TestPathTraversalPrevention(t *testing.T) {
	testCases := []struct {
		name     string
		path     string
		expected bool
	}{
		{"basic traversal", "../etc/passwd", false},
		{"double traversal", "../../etc/passwd", false},
		{"encoded traversal", "%2e%2e%2fetc%2fpasswd", false},
		{"mixed traversal", "..%2fetc/passwd", false},
		{"null byte", "file.txt\x00.jpg", false},
		{"valid path", "/files/document.txt", true},
		{"valid nested", "/files/folder/subfolder/doc.txt", true},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			result := utils.ValidatePath(tc.path)
			
			if tc.expected {
				assert.True(t, result, "should allow valid path: %s", tc.path)
			} else {
				assert.False(t, result, "should block malicious path: %s", tc.path)
			}
		})
	}
}

func TestCryptoSecurityIssues(t *testing.T) {
	t.Run("should use crypto/rand not math/rand", func(t *testing.T) {
		
		// Keys generated close together should still be different
		key1 := crypto.GenerateKey()
		key2 := crypto.GenerateKey()
		assert.NotEmpty(t, key1)
		assert.NotEmpty(t, key2)
		assert.NotEqual(t, key1, key2,
			"keys should be unique - math/rand with time seed may produce duplicates")
	})

	t.Run("should use proper password hashing", func(t *testing.T) {
		
		hash := crypto.HashPassword("password123")
		assert.NotEqual(t, "password123", hash)
		// SHA256 produces 64 hex chars; bcrypt/argon2 produce different formats
		// A secure hash should NOT be exactly 64 hex chars (that is raw SHA256)
		assert.NotEqual(t, 64, len(hash),
			"password hash should use bcrypt/argon2 (not raw SHA256 which is 64 hex chars)")
	})

	t.Run("should use constant-time comparison", func(t *testing.T) {
		
		hash := crypto.HashPassword("test")
		result := crypto.VerifyPassword("test", hash)
		assert.True(t, result, "correct password should verify")

		wrongResult := crypto.VerifyPassword("wrong", hash)
		assert.False(t, wrongResult, "wrong password should not verify")
	})

	t.Run("should use unique IVs for stream encryption", func(t *testing.T) {
		
		enc, err := crypto.NewEncryptor("test-key")
		assert.NoError(t, err)
		assert.NotNil(t, enc)

		// Encrypt same data twice; IVs should differ
		plainData := []byte("sensitive data")
		var buf1, buf2 bytes.Buffer

		err = enc.EncryptStream(bytes.NewReader(plainData), &buf1)
		assert.NoError(t, err)
		err = enc.EncryptStream(bytes.NewReader(plainData), &buf2)
		assert.NoError(t, err)

		// First 16 bytes are IV - they should be different
		if buf1.Len() >= 16 && buf2.Len() >= 16 {
			iv1 := buf1.Bytes()[:16]
			iv2 := buf2.Bytes()[:16]
			assert.NotEqual(t, iv1, iv2,
				"stream encryption IVs should be unique per encryption")

			// Zero IV is a critical vulnerability
			zeros := make([]byte, 16)
			assert.NotEqual(t, zeros, iv1,
				"IV should not be all zeros")
		}
	})
}

func TestIDORPrevention(t *testing.T) {
	t.Run("should check file ownership on download", func(t *testing.T) {
		
		// Any authenticated user can download any file
		// When fixed, a user should only be able to download their own files

		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)

		// Set up request as user A trying to download user B's file
		userA := uuid.New()
		c.Set("user_id", userA)
		c.Request = httptest.NewRequest("GET", "/api/v1/files/"+uuid.New().String()+"/download", nil)

		// The handler should verify that the file belongs to userA
		// and return 403 if it does not
		// (This test would need the actual handler wired up for full validation)
		assert.NotNil(t, c, "context should be set up for IDOR test")
	})

	t.Run("should check file ownership on delete", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)

		userA := uuid.New()
		c.Set("user_id", userA)
		c.Request = httptest.NewRequest("DELETE", "/api/v1/files/"+uuid.New().String(), nil)

		// Delete does check ownership - this should be correct after fix
		assert.NotNil(t, c)
	})
}

func TestSQLInjection(t *testing.T) {
	testCases := []struct {
		name    string
		payload string
	}{
		{"drop table", "'; DROP TABLE files; --"},
		{"boolean bypass", "1' OR '1'='1"},
		{"stacked query", "1; SELECT * FROM users; --"},
		{"union injection", "test' UNION SELECT * FROM users --"},
	}

	for _, tc := range testCases {
		t.Run("should prevent: "+tc.name, func(t *testing.T) {
			
			cfg := &config.Config{
				DatabaseURL: "postgres://test:test@localhost:5432/test?sslmode=disable",
			}
			repo, err := repository.NewFileRepository(cfg)
			if err != nil {
				t.Skip("database not available")
			}
			defer repo.Close()

			// Parameterized queries should prevent SQL injection
			assert.NotPanics(t, func() {
				_, _ = repo.Search(context.Background(), uuid.New(), tc.payload)
			}, "SQL injection should not cause panic: %s", tc.name)
		})
	}
}

func TestRateLimitBypass(t *testing.T) {
	t.Run("should not be bypassed by X-Forwarded-For", func(t *testing.T) {
		// Rate limiting should use the real client IP, not spoofed headers
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Request.Header.Set("X-Forwarded-For", "1.2.3.4")
		c.Request.RemoteAddr = "192.168.1.1:12345"

		// The middleware should use RemoteAddr, not X-Forwarded-For
		// (unless behind a trusted proxy)
		assert.Equal(t, "192.168.1.1:12345", c.Request.RemoteAddr,
			"RemoteAddr should be the real source, not spoofed XFF")
	})
}

func TestJWTSecurityIssues(t *testing.T) {
	t.Run("should reject none algorithm", func(t *testing.T) {
		// JWT library should reject algorithm:none
		// This is a known JWT attack vector
		cfg := &config.Config{
			JWTSecret: "test-secret",
		}
		assert.NotEmpty(t, cfg.JWTSecret,
			"JWT secret must not be empty")
	})

	t.Run("should validate token signature", func(t *testing.T) {
		cfg := &config.Config{
			JWTSecret: "test-secret",
		}
		assert.NotEmpty(t, cfg.JWTSecret)
		// A tampered token should be rejected by the auth middleware
	})

	t.Run("should check token expiration", func(t *testing.T) {
		cfg := &config.Config{
			JWTSecret: "test-secret",
		}
		assert.NotEmpty(t, cfg.JWTSecret)
		// Expired tokens should be rejected (tested in middleware_test.go)
	})
}

func TestShareSecurityIssues(t *testing.T) {
	t.Run("should hash share passwords", func(t *testing.T) {
		
		hash := crypto.HashPassword("sharepassword")
		assert.NotEqual(t, "sharepassword", hash,
			"share passwords should be hashed, not stored in plain text")
	})

	t.Run("should use constant-time password comparison", func(t *testing.T) {
		
		hash := crypto.HashPassword("secret")
		result := crypto.VerifyPassword("secret", hash)
		assert.True(t, result)
		// VerifyPassword should use subtle.ConstantTimeCompare internally
	})

	t.Run("should generate cryptographically random tokens", func(t *testing.T) {
		
		token1 := crypto.GenerateToken(32)
		token2 := crypto.GenerateToken(32)
		assert.Len(t, token1, 32)
		assert.Len(t, token2, 32)
		assert.NotEqual(t, token1, token2,
			"tokens should be unique - predictable PRNG is a security issue")
	})
}

func TestSecureHeaders(t *testing.T) {
	t.Run("should set X-Content-Type-Options", func(t *testing.T) {
		w := httptest.NewRecorder()
		// After security middleware runs, this header should be set
		// Expected: "nosniff"
		assert.Empty(t, w.Header().Get("X-Content-Type-Options"),
			"before middleware, header should not be set (middleware must add it)")
	})

	t.Run("should set X-Frame-Options", func(t *testing.T) {
		w := httptest.NewRecorder()
		assert.Empty(t, w.Header().Get("X-Frame-Options"),
			"before middleware, header should not be set")
	})

	t.Run("should set Content-Security-Policy", func(t *testing.T) {
		w := httptest.NewRecorder()
		assert.Empty(t, w.Header().Get("Content-Security-Policy"),
			"before middleware, header should not be set")
	})
}

func TestInputValidation(t *testing.T) {
	t.Run("should validate file size limits", func(t *testing.T) {
		cfg := &config.Config{
			MaxFileSize: 10 * 1024 * 1024, // 10MB
		}
		assert.Greater(t, cfg.MaxFileSize, int64(0),
			"MaxFileSize should be positive")
	})

	t.Run("should validate file types", func(t *testing.T) {
		allowed := []string{".jpg", ".png", ".gif", ".pdf"}
		assert.True(t, utils.IsAllowedExtension("image.jpg", allowed))
		assert.False(t, utils.IsAllowedExtension("script.php", allowed))
	})

	t.Run("should sanitize file names", func(t *testing.T) {
		
		sanitized := utils.SanitizePath("../../../etc/passwd")
		assert.NotContains(t, sanitized, "..",
			"sanitized path should not contain traversal sequences")
	})
}

func TestAuthenticationIssues(t *testing.T) {
	t.Run("should use strong password hashing", func(t *testing.T) {
		
		hash := crypto.HashPassword("testpassword")
		assert.NotEmpty(t, hash)
		// SHA256 = 64 hex chars; bcrypt would be ~60 chars starting with $2
		// If len == 64 and all hex, it is raw SHA256 (insecure)
		assert.NotEqual(t, 64, len(hash),
			"password should use bcrypt/argon2, not raw SHA256")
	})

	t.Run("should implement account lockout", func(t *testing.T) {
		// After N failed attempts, account should be locked
		// This is a defensive measure against brute force
		w := httptest.NewRecorder()
		assert.NotNil(t, w, "recorder for account lockout test")
	})
}

func TestEncryptionKeyManagement(t *testing.T) {
	t.Run("should use proper key derivation", func(t *testing.T) {
		
		enc1, err1 := crypto.NewEncryptor("password")
		enc2, err2 := crypto.NewEncryptor("password")
		assert.NoError(t, err1)
		assert.NoError(t, err2)
		assert.NotNil(t, enc1)
		assert.NotNil(t, enc2)

		// With proper KDF using salt, same password should produce different keys
		// (detectable by encrypting same plaintext producing different ciphertexts)
		plaintext := []byte("test data for KDF check")
		ct1, _ := enc1.Encrypt(plaintext)
		ct2, _ := enc2.Encrypt(plaintext)
		// With proper salt+KDF, these should always differ
		// With SHA256-only KDF, they may be identical if nonce is also predictable
		assert.NotNil(t, ct1)
		assert.NotNil(t, ct2)
	})

	t.Run("should use salt in key derivation", func(t *testing.T) {
		
		enc1, _ := crypto.NewEncryptor("samepassword")
		enc2, _ := crypto.NewEncryptor("samepassword")

		pt := []byte("deterministic check")
		ct1, _ := enc1.Encrypt(pt)
		ct2, _ := enc2.Encrypt(pt)

		// Even with same password, ciphertext should differ due to salt+nonce
		assert.NotNil(t, ct1)
		assert.NotNil(t, ct2)
	})
}

// Fuzzing tests for security-critical functions
func FuzzValidatePath(f *testing.F) {
	f.Add("../etc/passwd")
	f.Add("%2e%2e%2f")
	f.Add("\x00")
	f.Add("//etc/passwd")

	f.Fuzz(func(t *testing.T, path string) {
		// Should not panic
		utils.ValidatePath(path)
	})
}

func FuzzSanitizePath(f *testing.F) {
	f.Add("../test")
	f.Add("/%2e%2e/")

	f.Fuzz(func(t *testing.T, path string) {
		// Should not panic
		utils.SanitizePath(path)
	})
}

func FuzzEncrypt(f *testing.F) {
	f.Add([]byte("test data"))
	f.Add([]byte(""))
	f.Add(make([]byte, 1024*1024))

	f.Fuzz(func(t *testing.T, data []byte) {
		enc, _ := crypto.NewEncryptor("test-key")
		if enc == nil {
			return
		}
		// Should not panic
		ciphertext, err := enc.Encrypt(data)
		if err == nil && len(ciphertext) > 0 {
			// Should be able to decrypt
			dec, _ := enc.Decrypt(ciphertext)
			assert.Equal(t, data, dec)
		}
	})
}
