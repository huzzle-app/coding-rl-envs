package security

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
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
	digest := Digest(payload)
	if len(signature) == 0 || len(expected) == 0 || len(signature) != len(expected) {
		return false
	}
	if subtle.ConstantTimeCompare([]byte(signature), []byte(expected)) != 1 {
		return false
	}
	
	return expected == digest
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
	
	if time.Now().Before(tok.ExpiresAt) {
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
	
	cleaned := filepath.Clean(input)
	if strings.Contains(cleaned, "..") {
		return ""
	}
	return cleaned
}

// ---------------------------------------------------------------------------
// Origin allowlist
// ---------------------------------------------------------------------------

func IsAllowedOrigin(origin string, allowlist []string) bool {
	for _, allowed := range allowlist {

		if origin == allowed {
			return true
		}
	}
	return false
}

// ---------------------------------------------------------------------------
// Token sequence validation — ensures chain of tokens is valid and ordered
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Path-based permission checking — evaluates a request path against
// an ordered list of rules. More specific (longer prefix) rules should
// take precedence over less specific ones.
// ---------------------------------------------------------------------------

type PathRule struct {
	PathPrefix string
	Allow      bool
}

func CheckPathPermission(requestPath string, rules []PathRule) bool {
	for _, rule := range rules {
		if strings.HasPrefix(requestPath, rule.PathPrefix) {
			return rule.Allow
		}
	}
	return false
}

func ValidateTokenSequence(tokens []Token) (bool, int) {
	if len(tokens) == 0 {
		return false, -1
	}
	now := time.Now()
	for i, tok := range tokens {
		if now.After(tok.ExpiresAt) {
			return false, i
		}
		if i > 0 && !tok.ExpiresAt.After(tokens[i-1].ExpiresAt) {
			return false, i
		}
	}
	return true, -1
}
