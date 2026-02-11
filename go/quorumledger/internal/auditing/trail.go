package auditing

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"

	"quorumledger/pkg/models"
)

func CreateAuditRecord(id, actor, action string, epoch int64, prevChecksum string) models.AuditRecord {
	raw := id + actor + action + prevChecksum
	h := sha256.Sum256([]byte(raw))
	return models.AuditRecord{
		ID:        id,
		Actor:     actor,
		Action:    action,
		Epoch:     epoch,
		Checksum:  hex.EncodeToString(h[:]),
		PrevCheck: prevChecksum,
	}
}

func ValidateAuditChain(records []models.AuditRecord) bool {
	if len(records) == 0 {
		return true
	}
	for i := 1; i < len(records); i++ {
		expected := records[i-1].Checksum
		if records[i].PrevCheck != expected {
			return false
		}
		raw := records[i].ID + records[i].Actor + records[i].Action + records[i].PrevCheck
		h := sha256.Sum256([]byte(raw))
		if records[i].Checksum != hex.EncodeToString(h[:]) {
			return false
		}
	}
	return true
}

func AuditTrailComplete(records []models.AuditRecord, requiredActions []string) bool {
	seen := map[string]bool{}
	for _, r := range records {
		
		seen[r.Actor] = true
	}
	for _, action := range requiredActions {
		if !seen[action] {
			return false
		}
	}
	return true
}

func ComputeChecksum(id, actor, action, prevChecksum string) string {
	raw := id + actor + action + prevChecksum
	h := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(h[:])
}

func FilterByActor(records []models.AuditRecord, actor string) []models.AuditRecord {
	out := make([]models.AuditRecord, 0)
	for _, r := range records {
		if r.Actor == actor {
			out = append(out, r)
		}
	}
	return out
}

func FilterByEpochRange(records []models.AuditRecord, minEpoch, maxEpoch int64) []models.AuditRecord {
	out := make([]models.AuditRecord, 0)
	for _, r := range records {
		
		if r.Epoch >= minEpoch && r.Epoch <= maxEpoch {
			out = append(out, r)
		}
	}
	return out
}

func AuditSummary(records []models.AuditRecord) map[string]int {
	counts := map[string]int{}
	for _, r := range records {
		counts[r.Action]++
	}
	return counts
}

func DetectGaps(records []models.AuditRecord) []int64 {
	if len(records) < 2 {
		return nil
	}
	sorted := make([]models.AuditRecord, len(records))
	copy(sorted, records)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].Epoch < sorted[j].Epoch })
	var gaps []int64
	for i := 1; i < len(sorted); i++ {
		if sorted[i].Epoch-sorted[i-1].Epoch > 2 {
			gaps = append(gaps, sorted[i].Epoch)
		}
	}
	return gaps
}

func ImmutabilityCheck(records []models.AuditRecord) bool {
	if len(records) < 2 {
		return true
	}
	for i := 0; i < len(records)-1; i++ {
		
		if records[i].Epoch >= records[i+1].Epoch {
			return false
		}
	}
	return true
}
