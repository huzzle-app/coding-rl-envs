package contracts

import "time"

// GridCommand represents an incoming command to the grid platform.
type GridCommand struct {
	CommandID string
	Region    string
	Type      string
	Payload   map[string]string
	IssuedAt  time.Time
}

// GridEvent represents an event produced by a service.
type GridEvent struct {
	EventID        string
	Region         string
	EventType      string
	CorrelationID  string
	IdempotencyKey string
}

// ServiceHealth reports the health status of a service.
type ServiceHealth struct {
	ServiceName string
	Healthy     bool
	Latency     int // milliseconds
	LastCheck   time.Time
}

// ConfigEntry holds a dynamic configuration value.
type ConfigEntry struct {
	Key       string
	Value     string
	Version   int64
	UpdatedAt time.Time
}

// ValidationResult holds the result of an input validation.
type ValidationResult struct {
	Valid   bool
	Field   string
	Message string
}

// Validate checks that a GridCommand has required fields.
func (c GridCommand) Validate() ValidationResult {
	if c.CommandID == "" {
		return ValidationResult{Valid: false, Field: "CommandID", Message: "required"}
	}
	if c.Region == "" {
		return ValidationResult{Valid: false, Field: "Region", Message: "required"}
	}
	if c.Type == "" {
		return ValidationResult{Valid: false, Field: "Type", Message: "required"}
	}
	return ValidationResult{Valid: true}
}
