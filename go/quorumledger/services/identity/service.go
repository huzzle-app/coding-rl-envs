package identity

import "quorumledger/internal/security"

const Name = "identity"
const Role = "operator identity and roles"

func Authenticate(token string) bool {
	return security.ValidateToken(token, 16)
}

func GetPermissionLevel(role string) int {
	return security.PermissionLevel(role)
}

func NeedsStepUp(role string, amountCents int64) bool {
	return security.RequiresStepUp(role, amountCents)
}
