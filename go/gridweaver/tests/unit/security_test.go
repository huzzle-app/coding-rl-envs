package unit

import (
	"testing"

	"gridweaver/internal/security"
)

func TestSecurityObserverReadOnly(t *testing.T) {
	if !security.Authorize("observer", "read.telemetry") {
		t.Fatalf("observer should read")
	}
	if security.Authorize("observer", "dispatch.plan") {
		t.Fatalf("observer should not dispatch")
	}
}

func TestSecurityGridAdmin(t *testing.T) {
	if !security.Authorize("grid_admin", "control.substation") {
		t.Fatalf("grid admin should control substation")
	}
}

func TestSecurityUnknownRole(t *testing.T) {
	if security.Authorize("unknown", "read.telemetry") {
		t.Fatalf("unknown role should be denied")
	}
}

func TestSecurityExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"ValidateTokenEmpty", func(t *testing.T) {
			result := security.ValidateToken("")
			_ = result
		}},
		{"ValidateTokenValid", func(t *testing.T) {
			if !security.ValidateToken("some-token-123") {
				t.Fatalf("expected valid token to pass")
			}
		}},
		{"HashPassword", func(t *testing.T) {
			h := security.HashPassword("test123")
			if h == "" {
				t.Fatalf("expected non-empty hash")
			}
		}},
		{"CheckPermission", func(t *testing.T) {
			if !security.CheckPermission("grid_admin", "control.substation") {
				t.Fatalf("expected permission granted")
			}
		}},
		{"SanitizeInput", func(t *testing.T) {
			out := security.SanitizeInput("hello'world;drop")
			if out == "hello'world;drop" {
				t.Fatalf("expected sanitized output")
			}
		}},
		{"EscapeSQL", func(t *testing.T) {
			out := security.EscapeSQL("O'Brien")
			if out != "O''Brien" {
				t.Fatalf("expected escaped quotes")
			}
		}},
		{"ValidateRegion", func(t *testing.T) {
			if !security.ValidateRegion("west") {
				t.Fatalf("expected valid region")
			}
			if security.ValidateRegion("") {
				t.Fatalf("expected empty region to fail")
			}
		}},
		{"GenerateSessionID", func(t *testing.T) {
			id := security.GenerateSessionID("user1")
			if id == "" {
				t.Fatalf("expected non-empty session ID")
			}
		}},
		{"RateLimitCheck", func(t *testing.T) {
			result := security.RateLimitCheck(100, 50)
			_ = result
		}},
		{"VerifySignature", func(t *testing.T) {
			sig := "abcdefghijklmnop"
			result := security.VerifySignature(sig, sig)
			if !result {
				t.Fatalf("expected matching signatures")
			}
		}},
		{"AuditLog", func(t *testing.T) {
			log := security.AuditLog("admin", "dispatch.plan", "west-grid")
			if log["actor"] != "admin" {
				t.Fatalf("expected actor in audit log")
			}
		}},
		{"RoleHierarchy", func(t *testing.T) {
			roles := security.RoleHierarchy("grid_admin")
			if len(roles) != 3 {
				t.Fatalf("expected 3 roles in hierarchy")
			}
		}},
		{"RoleHierarchyUnknown", func(t *testing.T) {
			roles := security.RoleHierarchy("unknown")
			if roles != nil {
				t.Fatalf("expected nil for unknown role")
			}
		}},
		{"HasAnyPermission", func(t *testing.T) {
			if !security.HasAnyPermission("observer", []string{"read.telemetry", "dispatch.plan"}) {
				t.Fatalf("expected observer to have read.telemetry")
			}
		}},
		{"IsSuperUser", func(t *testing.T) {
			if !security.IsSuperUser("grid_admin") {
				t.Fatalf("expected grid_admin to be super user")
			}
			if security.IsSuperUser("observer") {
				t.Fatalf("observer should not be super user")
			}
		}},
		{"ValidateCommandType", func(t *testing.T) {
			if !security.ValidateCommandType("dispatch.plan") {
				t.Fatalf("expected valid command type")
			}
			if security.ValidateCommandType("invalid.type") {
				t.Fatalf("expected invalid command type")
			}
		}},
		{"MaskSensitive", func(t *testing.T) {
			data := map[string]string{"user": "admin", "password": "secret", "region": "west"}
			masked := security.MaskSensitive(data, []string{"password"})
			if masked["password"] != "***" {
				t.Fatalf("expected masked password")
			}
			if masked["user"] != "admin" {
				t.Fatalf("expected unmasked user")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
