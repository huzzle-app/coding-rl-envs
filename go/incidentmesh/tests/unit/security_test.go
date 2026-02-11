package unit

import (
	"strings"
	"testing"
	"incidentmesh/internal/security"
)

func TestSecurityAdminAuth(t *testing.T) {
	if !security.Authorize("admin", "incident.create") { t.Fatalf("admin should be authorized") }
}

func TestSecurityExtended(t *testing.T) {
	cases := []struct{ name string; fn func(t *testing.T) }{
		{"DispatcherAuth", func(t *testing.T) {
			if !security.Authorize("dispatcher", "incident.create") { t.Fatalf("should be authorized") }
		}},
		{"ObserverDenied", func(t *testing.T) {
			if security.Authorize("observer", "incident.create") { t.Fatalf("should be denied") }
		}},
		{"UnknownRole", func(t *testing.T) {
			if security.Authorize("unknown", "anything") { t.Fatalf("should be denied") }
		}},
		{"ValidToken", func(t *testing.T) {
			if !security.ValidateToken("valid-token-12345") { t.Fatalf("expected valid") }
		}},
		{"EmptyToken", func(t *testing.T) {
			r := security.ValidateToken("")
			
			if r { t.Fatalf("empty token should be invalid") }
		}},
		{"ShortToken", func(t *testing.T) {
			r := security.ValidateToken("x")
			
			if r { t.Fatalf("short token should be invalid") }
		}},
		{"Sanitize", func(t *testing.T) {
			s := security.SanitizeInput("<script>alert(1)</script>")
			if strings.Contains(s, "<script>") { t.Fatalf("expected sanitized") }
		}},
		{"HashPwd", func(t *testing.T) {
			h := security.HashPassword("secret")
			
			if h == "secret" { t.Fatalf("password should be hashed, not returned unchanged") }
		}},
		{"CheckPermEmpty", func(t *testing.T) {
			r := security.CheckPermission("admin", nil)
			
			if r { t.Fatalf("empty perms list should mean no access") }
		}},
		{"RateLimit", func(t *testing.T) {
			if !security.RateLimitCheck(5, 10) { t.Fatalf("should be allowed") }
		}},
		{"RateLimitExact", func(t *testing.T) {
			r := security.RateLimitCheck(10, 10)
			
			if r { t.Fatalf("requests at limit should be denied") }
		}},
		{"SessionValid", func(t *testing.T) {
			r := security.SessionValid(1000, 500)
			
			if !r { t.Fatalf("session expiring at 1000 should be valid at now=500") }
		}},
		{"IPAllowed", func(t *testing.T) {
			r := security.IPAllowed("5.5.5.5", []string{"1.2.3.4"})
			
			if r { t.Fatalf("IP not in allowlist should be denied") }
		}},
		{"Nonce", func(t *testing.T) {
			n := security.GenerateNonce(16)
			if n == "" { t.Fatalf("expected non-empty") }
		}},
		{"ValidRegion", func(t *testing.T) {
			if !security.ValidateRegion("north", []string{"north","south"}) { t.Fatalf("expected valid") }
		}},
		{"ValidRegionCase", func(t *testing.T) {
			r := security.ValidateRegion("North", []string{"north"})
			
			if !r { t.Fatalf("region validation should be case-insensitive") }
		}},
		{"AuditAct", func(t *testing.T) {
			a := security.AuditAction("user1", "create")
			if a == "" { t.Fatalf("expected non-empty") }
		}},
		{"Encrypt", func(t *testing.T) {
			e := security.EncryptField("sensitive", "key123")
			
			if e == "sensitive" { t.Fatalf("value should be encrypted, not returned unchanged") }
		}},
	}
	for _, tc := range cases { t.Run(tc.name, tc.fn) }
}
