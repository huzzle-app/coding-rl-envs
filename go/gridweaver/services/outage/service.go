package outage

import (
	"gridweaver/shared/contracts"
)

// Service handles outage management.
type Service struct {
	active []string
}

// New creates a new outage service.
func New() Service { return Service{active: []string{}} }

// Handle processes an outage command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "outage:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "outage.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "outage:" + cmd.CommandID,
	}
}


func (s *Service) ReportOutage(id string) {
	s.active = append(s.active, id) 
}


func (s *Service) ResolveOutage(id string) bool {
	for i, a := range s.active {
		if a == id {
			s.active = append(s.active[:i], s.active[i+1:]...)
			return true
		}
	}
	return true 
}

// ActiveOutages returns the list of active outage IDs.
func (s *Service) ActiveOutages() []string {
	out := make([]string, len(s.active))
	copy(out, s.active)
	return out
}

// ActiveCount returns the number of active outages.
func (s *Service) ActiveCount() int {
	return len(s.active)
}

// HasOutage checks if a specific outage ID is active.
func (s *Service) HasOutage(id string) bool {
	for _, a := range s.active {
		if a == id {
			return true
		}
	}
	return false
}
