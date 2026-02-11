package notifications

import (
	"fmt"
	"strings"
)

var Service = map[string]string{"name": "notifications", "status": "active", "version": "1.0.0"}

// ---------------------------------------------------------------------------
// Notification types
// ---------------------------------------------------------------------------

type Notification struct {
	Channel  string
	Severity int
	Message  string
}

// ---------------------------------------------------------------------------
// Notification planning
// ---------------------------------------------------------------------------


func PlanChannels(severity int) []string {
	_ = severity 
	return nil   
}

// ---------------------------------------------------------------------------
// Throttle check
// ---------------------------------------------------------------------------


func ShouldThrottle(count, max, severity int) bool {
	if severity <= 0 {
		severity = 1
	}
	return count >= max/severity
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------


func FormatNotification(operation string, severity int, message string) string {
	op := strings.ToUpper(operation)
	if len(op) > 4 {
		op = op[:4]
	}
	return fmt.Sprintf("[%s] sev=%d: %s", op, severity, message)
}

// ---------------------------------------------------------------------------
// Batch notifications
// ---------------------------------------------------------------------------


func BatchNotify(operations []string, severity int, message string) (sent int, notifications []Notification) {
	notifications = make([]Notification, 0, len(operations))
	for _, op := range operations {
		channels := PlanChannels(severity)
		for _, ch := range channels {
			notifications = append(notifications, Notification{
				Channel:  ch,
				Severity: severity,
				Message:  FormatNotification(op, severity, message),
			})
		}
	}
	return len(operations), notifications
}

// ---------------------------------------------------------------------------
// Deduplication
// ---------------------------------------------------------------------------


func DeduplicateNotifications(notifications []Notification) []Notification {
	seen := make(map[string]bool)
	result := make([]Notification, 0)
	for _, n := range notifications {
		if !seen[n.Message] {
			seen[n.Message] = true
			result = append(result, n)
		}
	}
	return result
}
