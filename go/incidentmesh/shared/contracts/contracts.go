package contracts

import "time"

type IncidentCommand struct {
	CommandID string
	Region    string
	Action    string
	Payload   map[string]string
	IssuedAt  time.Time
	Priority  int
}

type IncidentEvent struct {
	EventID        string
	Region         string
	EventType      string
	CorrelationID  string
	IdempotencyKey string
	Timestamp      time.Time
}

type AuditEntry struct {
	EntryID    string
	IncidentID string
	Action     string
	Actor      string
	Timestamp  time.Time
}

type NotificationPayload struct {
	RecipientID string
	Channel     string
	Message     string
	Priority    int
	Retries     int
}

// CommandValid checks basic command validity.
func (c IncidentCommand) CommandValid() bool {
	return c.CommandID != "" && c.Region != "" && c.Action != ""
}

// EventValid checks basic event validity.
func (e IncidentEvent) EventValid() bool {
	return e.EventID != "" && e.EventType != ""
}

// CorrelationIDFromCommand builds a unique correlation ID from a command.
func CorrelationIDFromCommand(cmd IncidentCommand) string {
	if cmd.CommandID == "" {
		return ""
	}
	return cmd.Region + ":" + cmd.Action
}
