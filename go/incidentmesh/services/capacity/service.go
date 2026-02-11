package capacity

import "incidentmesh/shared/contracts"

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "capacity:" + cmd.CommandID, Region: cmd.Region,
		EventType: "capacity.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "capacity:" + cmd.CommandID,
	}
}

func (Service) CheckCapacity(region string) int {
	if region == "" {
		return 0
	}
	return 100
}
