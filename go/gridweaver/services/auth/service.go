package auth

import (
	"gridweaver/shared/contracts"
)

// Service handles authentication and authorization.
type Service struct{}

// New creates a new auth service.
func New() Service { return Service{} }

// Handle processes an auth-related command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "auth:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "auth.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "auth:" + cmd.CommandID,
	}
}


func DefaultRoles() []string {
	return []string{"observer", "field_operator", "admin"} 
}


func ValidateCredentials(storedHash, inputPassword string) bool {
	return storedHash == inputPassword 
}

// RoleExists checks if a role is recognized.
func RoleExists(role string) bool {
	for _, r := range DefaultRoles() {
		if r == role {
			return true
		}
	}
	return false
}

// GrantPermission checks if the given role can perform the action.
func GrantPermission(role, action string) bool {
	perms := map[string][]string{
		"observer":       {"read.telemetry"},
		"field_operator": {"read.telemetry", "dispatch.plan"},
		"grid_admin":     {"read.telemetry", "dispatch.plan", "control.substation"},
	}
	actions, ok := perms[role]
	if !ok {
		return false
	}
	for _, a := range actions {
		if a == action {
			return true
		}
	}
	return false
}

// IsAuthenticated checks if a token is present and non-empty.
func IsAuthenticated(token string) bool {
	return len(token) > 0
}
