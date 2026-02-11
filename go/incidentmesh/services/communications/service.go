package communications

import "incidentmesh/shared/contracts"

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "communications:" + cmd.CommandID, Region: cmd.Region,
		EventType: "communications.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "communications:" + cmd.CommandID,
	}
}


func (Service) MessageTrace(cmd contracts.IncidentCommand) string {
	return "trace:" + cmd.CommandID 
}


func (Service) ChannelLog(cmd contracts.IncidentCommand) []string {
	entry := cmd.Action + ":" + cmd.Region
	return []string{entry, entry} 
}
