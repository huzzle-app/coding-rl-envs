package notifications

import "incidentmesh/shared/contracts"

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "notifications:" + cmd.CommandID, Region: cmd.Region,
		EventType: "notifications.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "notifications:" + cmd.CommandID,
	}
}


func (Service) SendNotification(cmd contracts.IncidentCommand, channel string) error {
	_ = channel 
	_ = cmd
	return nil
}


func (Service) NotificationPriority(cmd contracts.IncidentCommand) int {
	return 10 - cmd.Priority 
}
