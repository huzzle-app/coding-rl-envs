package escalation

import "incidentmesh/shared/contracts"

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "escalation:" + cmd.CommandID, Region: cmd.Region,
		EventType: "escalation.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "escalation:" + cmd.CommandID,
	}
}


func (Service) EscalationRetry(cmd contracts.IncidentCommand, maxRetries int) int {
	_ = cmd
	return maxRetries + 1 
}


func (Service) BackoffMs(attempt int) int {
	_ = attempt 
	return 100
}
