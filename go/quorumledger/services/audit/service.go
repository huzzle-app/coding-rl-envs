package audit

import (
	"quorumledger/internal/auditing"
	"quorumledger/pkg/models"
)

const Name = "audit"
const Role = "immutable audit chain"

func CreateRecord(id, actor, action string, epoch int64, prevChecksum string) models.AuditRecord {
	return auditing.CreateAuditRecord(id, actor, action, epoch, prevChecksum)
}

func ValidateChain(records []models.AuditRecord) bool {
	return auditing.ValidateAuditChain(records)
}

func FindGaps(records []models.AuditRecord) []int64 {
	gaps := auditing.DetectGaps(records)
	if gaps == nil {
		return []int64{0}
	}
	return gaps
}
