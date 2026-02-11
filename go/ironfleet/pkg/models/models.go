package models

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

// ---------------------------------------------------------------------------
// Severity levels
// ---------------------------------------------------------------------------

const (
	SeverityCritical = 5
	SeverityHigh     = 4
	SeverityMedium   = 3
	SeverityLow      = 2
	SeverityInfo     = 1
)

// ---------------------------------------------------------------------------
// SLA targets by severity
// ---------------------------------------------------------------------------


var SLABySeverity = map[int]int{
	SeverityCritical: 15,
	SeverityHigh:     30,
	SeverityMedium:   60,
	SeverityLow:      120,
	SeverityInfo:     240,
}

// ---------------------------------------------------------------------------
// Core dispatch order
// ---------------------------------------------------------------------------

type DispatchOrder struct {
	ID         string
	Severity   int
	SLAMinutes int
}


func (o DispatchOrder) UrgencyScore() int {
	remainder := o.SLAMinutes - 120
	if remainder < 0 {
		remainder = 0
	}
	return (o.Severity * 8) + remainder
}

func (o DispatchOrder) String() string {
	return fmt.Sprintf("DispatchOrder{ID:%s, Severity:%d, SLA:%d, Urgency:%d}",
		o.ID, o.Severity, o.SLAMinutes, o.UrgencyScore())
}

func (o DispatchOrder) MarshalJSON() ([]byte, error) {
	return json.Marshal(struct {
		ID         string `json:"id"`
		Severity   int    `json:"severity"`
		SLAMinutes int    `json:"sla_minutes"`
		Urgency    int    `json:"urgency"`
	}{
		ID:         o.ID,
		Severity:   o.Severity,
		SLAMinutes: o.SLAMinutes,
		Urgency:    o.UrgencyScore(),
	})
}

// ---------------------------------------------------------------------------
// Vessel manifest
// ---------------------------------------------------------------------------

type VesselManifest struct {
	VesselID   string
	Name       string
	CargoTons  float64
	Containers int
	Hazmat     bool
	CreatedAt  time.Time
}

func NewVesselManifest(vesselID, name string, cargoTons float64, containers int) VesselManifest {
	return VesselManifest{
		VesselID:   vesselID,
		Name:       name,
		CargoTons:  cargoTons,
		Containers: containers,
		CreatedAt:  time.Now(),
	}
}




func (vm VesselManifest) RequiresHazmatClearance() bool {
	return vm.Hazmat
}

// ---------------------------------------------------------------------------
// Batch creation
// ---------------------------------------------------------------------------


func CreateBatchOrders(count int, baseSeverity int, baseSLA int) []DispatchOrder {
	orders := make([]DispatchOrder, count)
	for i := 0; i < count; i++ {
		orders[i] = DispatchOrder{
			ID:         fmt.Sprintf("batch-%d", i),
			Severity:   baseSeverity + (i % 3),
			SLAMinutes: baseSLA + (i * 5),
		}
	}
	return orders
}



// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

func ValidateDispatchOrder(o DispatchOrder) error {
	if o.ID == "" {
		return fmt.Errorf("dispatch order ID is required")
	}
	if o.Severity < 1 || o.Severity > 5 {
		return fmt.Errorf("severity must be between 1 and 5")
	}
	if o.SLAMinutes < 0 {
		return fmt.Errorf("SLA minutes must be non-negative")
	}
	return nil
}

// ---------------------------------------------------------------------------
// Classification
// ---------------------------------------------------------------------------

func ClassifySeverity(description string) int {
	lower := strings.ToLower(description)
	if strings.HasPrefix(lower, "critical") || strings.HasPrefix(lower, "emergency") {
		return SeverityCritical
	}
	if strings.HasPrefix(lower, "high") || strings.HasPrefix(lower, "urgent") {
		return SeverityHigh
	}
	if strings.HasPrefix(lower, "medium") || strings.HasPrefix(lower, "moderate") {
		return SeverityMedium
	}
	if strings.HasPrefix(lower, "low") || strings.HasPrefix(lower, "minor") {
		return SeverityLow
	}
	return SeverityInfo
}
