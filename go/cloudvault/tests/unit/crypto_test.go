package unit

import (
	"bytes"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/terminal-bench/cloudvault/pkg/crypto"
)

func TestEncryptorCreation(t *testing.T) {
	t.Run("should create encryptor with key", func(t *testing.T) {
		enc, err := crypto.NewEncryptor("test-key")
		require.NoError(t, err)
		assert.NotNil(t, enc)
	})

	t.Run("should reject empty key", func(t *testing.T) {
		enc, err := crypto.NewEncryptor("")
		assert.Error(t, err)
		assert.Nil(t, enc)
	})

	t.Run("should use salted key derivation", func(t *testing.T) {
		
		// Same key always produces same derived key
		enc1, _ := crypto.NewEncryptor("password")
		enc2, _ := crypto.NewEncryptor("password")

		plaintext := []byte("test data")
		ct1, err1 := enc1.Encrypt(plaintext)
		ct2, err2 := enc2.Encrypt(plaintext)
		assert.NoError(t, err1)
		assert.NoError(t, err2)

		// With proper salt, ciphertexts should always differ
		// With BUG E1 (no salt + predictable nonce), they may be identical
		assert.NotEqual(t, ct1, ct2,
			"encryptions with same password should produce different ciphertexts (requires salt/random nonce)")
	})
}

func TestEncryptDecrypt(t *testing.T) {
	enc, _ := crypto.NewEncryptor("test-key")

	t.Run("should encrypt and decrypt successfully", func(t *testing.T) {
		plaintext := []byte("Hello, World!")

		ciphertext, err := enc.Encrypt(plaintext)
		require.NoError(t, err)
		assert.NotEqual(t, plaintext, ciphertext)

		decrypted, err := enc.Decrypt(ciphertext)
		require.NoError(t, err)
		assert.Equal(t, plaintext, decrypted)
	})

	t.Run("should fail with tampered ciphertext", func(t *testing.T) {
		plaintext := []byte("Secret data")

		ciphertext, _ := enc.Encrypt(plaintext)
		ciphertext[len(ciphertext)-1] ^= 0xFF // Flip bits

		_, err := enc.Decrypt(ciphertext)
		assert.Error(t, err)
	})

	t.Run("should produce predictable nonces", func(t *testing.T) {
		
		plaintext := []byte("test")

		// If math/rand is seeded with time, running at same time
		// could produce same nonce (very bad for GCM)
		ct1, _ := enc.Encrypt(plaintext)
		ct2, _ := enc.Encrypt(plaintext)

		// These should always be different (nonce should be random)
		// But with math/rand, they might collide
		assert.NotEqual(t, ct1, ct2)
	})
}

func TestStreamEncryption(t *testing.T) {
	enc, _ := crypto.NewEncryptor("stream-key")

	t.Run("should encrypt and decrypt stream", func(t *testing.T) {
		plaintext := bytes.Repeat([]byte("test data\n"), 1000)
		reader := bytes.NewReader(plaintext)
		var encrypted bytes.Buffer

		err := enc.EncryptStream(reader, &encrypted)
		require.NoError(t, err)

		var decrypted bytes.Buffer
		err = enc.DecryptStream(&encrypted, &decrypted)
		require.NoError(t, err)

		assert.Equal(t, plaintext, decrypted.Bytes())
	})

	t.Run("should use random IV for stream", func(t *testing.T) {
		
		plaintext := []byte("sensitive data")
		reader := bytes.NewReader(plaintext)
		var encrypted bytes.Buffer

		enc.EncryptStream(reader, &encrypted)

		if encrypted.Len() >= 16 {
			// First 16 bytes are IV - should NOT be all zeros
			iv := encrypted.Bytes()[:16]
			zeros := make([]byte, 16)
			assert.NotEqual(t, zeros, iv,
				"stream IV should be random, not all zeros (BUG E1: zero IV)")
		}
	})
}

func TestGenerateKey(t *testing.T) {
	t.Run("should generate key", func(t *testing.T) {
		key := crypto.GenerateKey()
		assert.Len(t, key, 64) // 32 bytes = 64 hex chars
	})

	t.Run("should generate predictable keys with math/rand", func(t *testing.T) {
		
		// if seed is known (time-based)

		// Keys should be unique but with time-based seeding
		// keys generated at same moment could be identical
		key1 := crypto.GenerateKey()
		key2 := crypto.GenerateKey()
		assert.NotEqual(t, key1, key2)
	})
}

func TestHashPassword(t *testing.T) {
	t.Run("should hash password", func(t *testing.T) {
		hash := crypto.HashPassword("password123")
		assert.NotEqual(t, "password123", hash)
		assert.Len(t, hash, 64) // SHA256 = 64 hex chars
	})

	t.Run("should produce different hashes for same password with salt", func(t *testing.T) {
		
		// With proper salting (bcrypt/argon2), same password produces different hashes
		hash1 := crypto.HashPassword("password123")
		hash2 := crypto.HashPassword("password123")
		assert.NotEqual(t, hash1, hash2,
			"same password should produce different hashes when salt is used (BUG E1: no salt)")
	})

	t.Run("should be resistant to rainbow tables", func(t *testing.T) {
		
		// With proper hashing (bcrypt/argon2), same password produces different hashes
		hash := crypto.HashPassword("password")
		assert.NotEmpty(t, hash)
		// SHA256 of "password" is a well-known value; proper KDF should not match it
		assert.NotEqual(t, 64, len(hash),
			"password hash should not be raw SHA256 (64 hex chars = rainbow table vulnerable)")
	})
}

func TestVerifyPassword(t *testing.T) {
	t.Run("should verify correct password", func(t *testing.T) {
		hash := crypto.HashPassword("correct")
		assert.True(t, crypto.VerifyPassword("correct", hash))
	})

	t.Run("should reject incorrect password", func(t *testing.T) {
		hash := crypto.HashPassword("correct")
		assert.False(t, crypto.VerifyPassword("wrong", hash))
	})

	t.Run("should use constant-time comparison", func(t *testing.T) {
		
		// VerifyPassword should use subtle.ConstantTimeCompare
		hash := crypto.HashPassword("password")

		// Correct password should verify
		assert.True(t, crypto.VerifyPassword("password", hash),
			"correct password should verify")
		// Wrong password should not verify
		assert.False(t, crypto.VerifyPassword("p", hash),
			"wrong password should not verify")
		assert.False(t, crypto.VerifyPassword("wrong", hash),
			"incorrect password should not verify")
	})
}

func TestGenerateToken(t *testing.T) {
	t.Run("should generate token of specified length", func(t *testing.T) {
		token := crypto.GenerateToken(32)
		assert.Len(t, token, 32)
	})

	t.Run("should generate predictable tokens", func(t *testing.T) {
		
		// Tokens could be predicted if seed is known
		token1 := crypto.GenerateToken(32)
		token2 := crypto.GenerateToken(32)
		assert.NotEqual(t, token1, token2)
	})
}
