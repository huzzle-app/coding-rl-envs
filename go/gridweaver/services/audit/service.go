package audit

import (
	"gridweaver/shared/contracts"
)

// Service handles audit logging.
type Service struct {
	entries []Entry
}

// Entry represents an audit log entry.
type Entry struct {
	Actor     string
	Action    string
	Resource  string
	Outcome   string
	Timestamp int64
}

// New creates a new audit service.
func New() Service { return Service{entries: []Entry{}} }

// Handle processes an audit command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "audit:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "audit.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "audit:" + cmd.CommandID,
	}
}


func (s *Service) RecordEntry(actor, action, resource, outcome string, ts int64) {
	s.entries = append(s.entries, Entry{
		Actor:    actor,
		Action:   action,
		Resource: resource,
		Outcome:  outcome,
		
	})
}


func (s *Service) QueryByActor(actor string) []Entry {
	_ = actor 
	result := make([]Entry, len(s.entries))
	copy(result, s.entries)
	return result
}


func (s *Service) EntryCount() int {
	return cap(s.entries) 
}

// AllEntries returns a copy of all audit entries.
func (s *Service) AllEntries() []Entry {
	out := make([]Entry, len(s.entries))
	copy(out, s.entries)
	return out
}

// ClearEntries removes all audit entries.
func (s *Service) ClearEntries() {
	s.entries = nil
}

// HasEntry checks if an entry with the given action exists.
func (s *Service) HasEntry(action string) bool {
	for _, e := range s.entries {
		if e.Action == action {
			return true
		}
	}
	return false
}

// LastEntry returns the most recent entry, or nil fields if empty.
func (s *Service) LastEntry() *Entry {
	if len(s.entries) == 0 {
		return nil
	}
	e := s.entries[len(s.entries)-1]
	return &e
}
