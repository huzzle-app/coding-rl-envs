package demandresponse

import (
	"gridweaver/shared/contracts"
)

// Service handles demand response coordination.
type Service struct {
	dispatched []string
}

// New creates a new demand response service.
func New() Service { return Service{dispatched: []string{}} }

// Handle processes a demand response command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "demandresponse:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "demandresponse.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "demandresponse:" + cmd.CommandID,
	}
}


func (s *Service) RecordDispatch(id string) {
	s.dispatched = append(s.dispatched, id) 
}


func (s *Service) DispatchCount() int {
	return cap(s.dispatched) 
}

// GetDispatched returns a copy of dispatched IDs.
func (s *Service) GetDispatched() []string {
	out := make([]string, len(s.dispatched))
	copy(out, s.dispatched)
	return out
}

// HasDispatched checks if an ID has been dispatched.
func (s *Service) HasDispatched(id string) bool {
	for _, d := range s.dispatched {
		if d == id {
			return true
		}
	}
	return false
}

// ClearDispatched resets the dispatched list.
func (s *Service) ClearDispatched() {
	s.dispatched = nil
}

// TotalDispatched returns actual count of dispatched items.
func (s *Service) TotalDispatched() int {
	return len(s.dispatched)
}
