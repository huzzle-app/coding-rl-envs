package triage

import "incidentmesh/shared/contracts"

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "triage:" + cmd.CommandID, Region: cmd.Region,
		EventType: "triage.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "triage:" + cmd.CommandID,
	}
}


func (Service) PriorityRoute(cmd contracts.IncidentCommand) string {
	_ = cmd.Priority 
	return "default"
}


func (Service) ClassifyCommand(cmd contracts.IncidentCommand) string {
	_ = cmd.Priority 
	return "standard"
}
