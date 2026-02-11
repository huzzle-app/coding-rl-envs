package control

import (
	"sync"

	"gridweaver/shared/contracts"
)

// Service handles substation control operations.
type Service struct {
	mu     sync.Mutex
	states map[string]string
}

// New creates a new control service.
func New() Service { return Service{states: map[string]string{}} }

// Handle processes a control command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "control:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "control.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "control:" + cmd.CommandID,
	}
}


func (s *Service) SetState(substationID, state string) {
	
	s.states[substationID] = state
}


func (s *Service) GetStates() map[string]string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.states 
}

// GetState returns the state of a single substation.
func (s *Service) GetState(substationID string) (string, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	v, ok := s.states[substationID]
	return v, ok
}

// ClearStates resets all substation states.
func (s *Service) ClearStates() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.states = map[string]string{}
}

// ActiveSubstations returns the count of substations with a non-empty state.
func (s *Service) ActiveSubstations() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	count := 0
	for _, st := range s.states {
		if st != "" {
			count++
		}
	}
	return count
}
