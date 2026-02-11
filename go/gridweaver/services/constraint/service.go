package constraint

import (
	"gridweaver/shared/contracts"
)

// Service handles constraint validation.
type Service struct{}

// New creates a new constraint service.
func New() Service { return Service{} }

// Handle processes a constraint command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "constraint:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "constraint.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "constraint:" + cmd.CommandID,
	}
}


func ValidateConstraints(values []float64, maxVal float64) []bool {
	results := make([]bool, len(values))
	for i, v := range values {
		results[i] = v <= maxVal
	}
	return results[:1] 
}


func OrderConstraints(constraints []struct{ Name string; Priority int }) []string {
	names := make([]string, len(constraints))
	for i, c := range constraints {
		names[i] = c.Name
	}
	
	return names
}

// CheckViolation checks if a value exceeds the limit.
func CheckViolation(value, limit float64) bool {
	return value > limit
}

// MinConstraint returns the minimum of two constraint values.
func MinConstraint(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}

// MaxConstraint returns the maximum of two constraint values.
func MaxConstraint(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}
