package dispatch

import (
	"sync"

	"gridweaver/shared/contracts"
)

// Service handles dispatch operations.
type Service struct {
	mu       sync.Mutex
	history  []contracts.GridEvent
}

// New creates a new dispatch service.
func New() Service { return Service{history: []contracts.GridEvent{}} }

// Handle processes a dispatch command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "dispatch:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "dispatch.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "dispatch:" + cmd.CommandID,
	}
}


func (s *Service) RecordEvent(event contracts.GridEvent) {
	
	s.history = append(s.history, event)
}


func (s *Service) GetHistory() []contracts.GridEvent {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.history 
}

// HistoryCount returns the number of recorded events.
func (s *Service) HistoryCount() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.history)
}

// ClearHistory removes all recorded events.
func (s *Service) ClearHistory() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.history = nil
}

// LastEvent returns the most recent event, or nil.
func (s *Service) LastEvent() *contracts.GridEvent {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.history) == 0 {
		return nil
	}
	e := s.history[len(s.history)-1]
	return &e
}
