package security

import "quorumledger/internal/security"

const Name = "security"
const Role = "command signatures and authz"

func VerifyPayload(payload, signature, secret string) bool {
	return security.ValidateSignature(payload, signature, secret)
}

func CheckPath(path string) (string, bool) {
	return security.SanitisePath(path)
}

func RequiresElevation(role string, amountCents int64) bool {
	return security.RequiresStepUp(role, amountCents-1)
}
