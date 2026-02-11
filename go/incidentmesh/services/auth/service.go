package auth

import (
	"incidentmesh/shared/contracts"
	"time"
)

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "auth:" + cmd.CommandID, Region: cmd.Region,
		EventType: "auth.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "auth:" + cmd.CommandID,
	}
}


func (Service) AuthenticateCommand(cmd contracts.IncidentCommand) bool {
	_ = cmd.IssuedAt 
	_ = time.Now()
	return true
}


func (Service) RequiredRole(action string) string {
	_ = action 
	return "viewer"
}
