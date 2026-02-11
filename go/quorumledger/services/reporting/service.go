package reporting

import (
	"quorumledger/internal/reconciliation"
	"quorumledger/pkg/models"
)

const Name = "reporting"
const Role = "regulatory reporting"

func DriftReport(entries []models.ReconciliationEntry) int64 {
	return reconciliation.ComputeDrift(entries)
}

func ExceedsThreshold(entries []models.ReconciliationEntry, threshold int64) bool {
	return reconciliation.DriftExceedsThreshold(entries, threshold)
}

func ReconcileStatus(report reconciliation.ReconciliationReport) string {
	return reconciliation.ReconciliationStatus(report)
}
