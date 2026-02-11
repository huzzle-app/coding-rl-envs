package identity

import "incidentmesh/shared/contracts"

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "identity:" + cmd.CommandID, Region: cmd.Region,
		EventType: "identity.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "identity:" + cmd.CommandID,
	}
}

func (Service) ResolveIdentity(cmd contracts.IncidentCommand) string {
	return cmd.Region + ":" + cmd.CommandID
}
