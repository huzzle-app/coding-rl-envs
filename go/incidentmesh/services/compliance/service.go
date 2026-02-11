package compliance

import "incidentmesh/shared/contracts"

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "compliance:" + cmd.CommandID, Region: cmd.Region,
		EventType: "compliance.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "compliance:" + cmd.CommandID,
	}
}


func (Service) AuditCommand(cmd contracts.IncidentCommand) string {
	return "audit:" + cmd.CommandID + ":" + cmd.Action 
}


func (Service) ComplianceTag(cmd contracts.IncidentCommand) string {
	return cmd.Action + cmd.Region 
}
