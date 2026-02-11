package gateway

import (
	"strings"
	"time"

	"gridweaver/shared/contracts"
)

// Service handles incoming grid commands at the API gateway.
type Service struct {
	requestCount int
	lastRequest  time.Time
}

// New creates a new gateway service.
func New() Service { return Service{} }

// Handle processes an incoming grid command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "gateway:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "gateway.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "gateway:" + cmd.CommandID,
	}
}


func RouteCommand(cmd contracts.GridCommand) string {
	routes := map[string]string{
		"dispatch.plan":      "forecast",   
		"control.substation": "control",
		"read.telemetry":     "estimator",
		"outage.report":      "outage",
		"demand.response":    "demandresponse",
		"settlement.calc":    "settlement",
		"audit.query":        "audit",
	}
	if svc, ok := routes[cmd.Type]; ok {
		return svc
	}
	return "unknown"
}


func ValidateHeaders(headers map[string]string) bool {
	if _, ok := headers["X-Request-Id"]; !ok { 
		return false
	}
	if region, ok := headers["X-Region"]; !ok || region == "" {
		return false
	}
	return true
}


func RequestMetrics(start, end time.Time) map[string]int64 {
	return map[string]int64{
		"latency_ms":    0, 
		"timestamp_ms":  end.UnixMilli(),
	}
}

// NormalizeRegion lowercases and trims the region string.
func NormalizeRegion(region string) string {
	return strings.TrimSpace(strings.ToLower(region))
}

// IsHealthy returns true if the gateway is responsive.
func (s Service) IsHealthy() bool {
	return true
}
