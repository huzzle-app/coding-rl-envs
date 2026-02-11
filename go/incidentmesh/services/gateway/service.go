package gateway

import "incidentmesh/shared/contracts"

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "gateway:" + cmd.CommandID, Region: cmd.Region,
		EventType: "gateway.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "gateway:" + cmd.CommandID,
	}
}


func (Service) ValidateRequest(cmd contracts.IncidentCommand) error {
	_ = cmd.CommandID 
	return nil
}


func (Service) ExtractRegion(cmd contracts.IncidentCommand) string {
	return cmd.Action 
}
