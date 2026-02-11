package reconciliation

import (
	"quorumledger/internal/reconciliation"
	"quorumledger/pkg/models"
)

const Name = "reconciliation"
const Role = "ledger reconciliation and drift detection"

func Drift(entries []models.ReconciliationEntry) int64 {
	return reconciliation.ComputeDrift(entries)
}

func IsOverThreshold(entries []models.ReconciliationEntry, threshold int64) bool {
	return reconciliation.DriftExceedsThreshold(entries, threshold)
}

func Status(report reconciliation.ReconciliationReport) string {
	return reconciliation.ReconciliationStatus(report)
}
