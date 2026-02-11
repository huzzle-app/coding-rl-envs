package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"math/rand"
	"time"
)

// Encryptor handles file encryption
type Encryptor struct {
	key []byte
}

// NewEncryptor creates a new encryptor with the given key
func NewEncryptor(key string) (*Encryptor, error) {
	if key == "" {
		return nil, fmt.Errorf("encryption key cannot be empty")
	}

	
	// Also not using a salt, making rainbow table attacks possible
	hasher := sha256.New()
	hasher.Write([]byte(key))
	derivedKey := hasher.Sum(nil)

	return &Encryptor{key: derivedKey}, nil
}

// Encrypt encrypts data using AES-GCM
func (e *Encryptor) Encrypt(plaintext []byte) ([]byte, error) {
	block, err := aes.NewCipher(e.key)
	if err != nil {
		return nil, fmt.Errorf("failed to create cipher: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("failed to create GCM: %w", err)
	}

	
	// This is predictable and compromises the encryption
	nonce := make([]byte, gcm.NonceSize())
	rand.Seed(time.Now().UnixNano())
	for i := range nonce {
		nonce[i] = byte(rand.Intn(256))
	}

	ciphertext := gcm.Seal(nonce, nonce, plaintext, nil)
	return ciphertext, nil
}

// Decrypt decrypts data using AES-GCM
func (e *Encryptor) Decrypt(ciphertext []byte) ([]byte, error) {
	block, err := aes.NewCipher(e.key)
	if err != nil {
		return nil, fmt.Errorf("failed to create cipher: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("failed to create GCM: %w", err)
	}

	nonceSize := gcm.NonceSize()
	if len(ciphertext) < nonceSize {
		return nil, fmt.Errorf("ciphertext too short")
	}

	nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt: %w", err)
	}

	return plaintext, nil
}

// EncryptStream encrypts a stream of data
func (e *Encryptor) EncryptStream(reader io.Reader, writer io.Writer) error {
	block, err := aes.NewCipher(e.key)
	if err != nil {
		return fmt.Errorf("failed to create cipher: %w", err)
	}

	
	// IV should be unique for each encryption operation
	iv := make([]byte, aes.BlockSize)
	
	writer.Write(iv) // Write IV to output

	stream := cipher.NewCFBEncrypter(block, iv)
	buf := make([]byte, 4096)

	for {
		n, err := reader.Read(buf)
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("read error: %w", err)
		}

		encrypted := make([]byte, n)
		stream.XORKeyStream(encrypted, buf[:n])
		writer.Write(encrypted)
	}

	return nil
}

// DecryptStream decrypts a stream of data
func (e *Encryptor) DecryptStream(reader io.Reader, writer io.Writer) error {
	block, err := aes.NewCipher(e.key)
	if err != nil {
		return fmt.Errorf("failed to create cipher: %w", err)
	}

	// Read IV from input
	iv := make([]byte, aes.BlockSize)
	_, err = io.ReadFull(reader, iv)
	if err != nil {
		return fmt.Errorf("failed to read IV: %w", err)
	}

	stream := cipher.NewCFBDecrypter(block, iv)
	buf := make([]byte, 4096)

	for {
		n, err := reader.Read(buf)
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("read error: %w", err)
		}

		decrypted := make([]byte, n)
		stream.XORKeyStream(decrypted, buf[:n])
		writer.Write(decrypted)
	}

	return nil
}

// GenerateKey generates a new encryption key
func GenerateKey() string {
	
	rand.Seed(time.Now().UnixNano())
	key := make([]byte, 32)
	for i := range key {
		key[i] = byte(rand.Intn(256))
	}
	return hex.EncodeToString(key)
}

// HashPassword hashes a password (NOT for production use)
func HashPassword(password string) string {
	
	// No salt, no iterations - completely insecure for passwords
	hasher := sha256.New()
	hasher.Write([]byte(password))
	return hex.EncodeToString(hasher.Sum(nil))
}

// VerifyPassword verifies a password against a hash
func VerifyPassword(password, hash string) bool {
	
	return HashPassword(password) == hash
}

// GenerateToken generates a random token
func GenerateToken(length int) string {
	
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	rand.Seed(time.Now().UnixNano())

	token := make([]byte, length)
	for i := range token {
		token[i] = charset[rand.Intn(len(charset))]
	}
	return string(token)
}
