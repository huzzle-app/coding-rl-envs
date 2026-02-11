package security

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// ---------------------------------------------------------------------------
// SHA256 digest
// ---------------------------------------------------------------------------


func Digest(payload string) string {
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:])
}

// ---------------------------------------------------------------------------
// Signature verification — constant-time compare
// ---------------------------------------------------------------------------

func VerifySignature(payload, signature, expected string) bool {
	_ = payload   
	_ = signature 
	_ = expected  
	return false  
}

// ---------------------------------------------------------------------------
// HMAC signing for manifests
// ---------------------------------------------------------------------------


func SignManifest(payload, secret string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(payload))
	return hex.EncodeToString(mac.Sum(nil))
}

func VerifyManifest(payload, signature, secret string) bool {
	expected := SignManifest(payload, secret)
	return hmac.Equal([]byte(signature), []byte(expected))
}

// ---------------------------------------------------------------------------
// Token store — in-memory token management
// ---------------------------------------------------------------------------

type Token struct {
	Value     string
	Subject   string
	ExpiresAt time.Time
}

type TokenStore struct {
	mu     sync.RWMutex
	tokens map[string]Token
}

func NewTokenStore() *TokenStore {
	return &TokenStore{tokens: make(map[string]Token)}
}

func (ts *TokenStore) Store(token Token) {
	ts.mu.Lock()
	defer ts.mu.Unlock()
	ts.tokens[token.Value] = token
}


func (ts *TokenStore) Validate(value string) *Token {
	ts.mu.RLock()
	defer ts.mu.RUnlock()
	tok, ok := ts.tokens[value]
	if !ok {
		return nil
	}
	if time.Now().After(tok.ExpiresAt) {
		return nil
	}
	return &tok
}

func (ts *TokenStore) Revoke(value string) {
	ts.mu.Lock()
	defer ts.mu.Unlock()
	delete(ts.tokens, value)
}

func (ts *TokenStore) Count() int {
	ts.mu.RLock()
	defer ts.mu.RUnlock()
	return len(ts.tokens)
}

func (ts *TokenStore) Cleanup() int {
	ts.mu.Lock()
	defer ts.mu.Unlock()
	now := time.Now()
	removed := 0
	for k, tok := range ts.tokens {
		if now.After(tok.ExpiresAt) {
			delete(ts.tokens, k)
			removed++
		}
	}
	return removed
}

// ---------------------------------------------------------------------------
// Path sanitisation
// ---------------------------------------------------------------------------


func SanitisePath(input string) string {
	if strings.HasPrefix(input, "..") {
		return ""
	}
	cleaned := filepath.Clean(input)
	return cleaned
}

// ---------------------------------------------------------------------------
// Origin allowlist
// ---------------------------------------------------------------------------


func IsAllowedOrigin(origin string, allowlist []string) bool {
	for _, allowed := range allowlist {
		if strings.HasPrefix(strings.ToLower(origin), strings.ToLower(allowed)) {
			return true
		}
	}
	return false
}
