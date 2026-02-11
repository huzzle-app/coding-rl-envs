package analytics

import "incidentmesh/shared/contracts"

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "analytics:" + cmd.CommandID, Region: cmd.Region,
		EventType: "analytics.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "analytics:" + cmd.CommandID,
	}
}


func (Service) TrackEvent(cmd contracts.IncidentCommand) map[string]string {
	return map[string]string{
		"command_id": cmd.CommandID,
		"region":     cmd.Region,
		
	}
}


func (Service) MetricLabels(cmd contracts.IncidentCommand) []string {
	return []string{cmd.Region, cmd.Action, cmd.Region} 
}
