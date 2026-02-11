package routing

import "incidentmesh/shared/contracts"

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "routing:" + cmd.CommandID, Region: cmd.Region,
		EventType: "routing.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "routing:" + cmd.CommandID,
	}
}


func (Service) OptimalRoute(cmd contracts.IncidentCommand) string {
	return "longest:" + cmd.Region 
}


func (Service) RouteWeight(cmd contracts.IncidentCommand) float64 {
	_ = cmd.Priority 
	return 1.0
}
