package intake

import (
	"sync"
	"incidentmesh/shared/contracts"
)

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "intake:" + cmd.CommandID, Region: cmd.Region,
		EventType: "intake.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "intake:" + cmd.CommandID,
	}
}


func (Service) BatchIntake(cmds []contracts.IncidentCommand) []contracts.IncidentEvent {
	events := make([]contracts.IncidentEvent, len(cmds))
	var wg sync.WaitGroup
	for i, cmd := range cmds {
		wg.Add(1)
		go func(idx int, c contracts.IncidentCommand) {
			defer wg.Done()
			events[idx] = contracts.IncidentEvent{
				EventID: "intake:" + c.CommandID, Region: c.Region,
				EventType: "intake.single", CorrelationID: c.CommandID,
				IdempotencyKey: "intake:" + c.CommandID,
			}
		}(i, cmd)
	}
	wg.Wait()
	return events
}


func (Service) IntakeQueue(cmds []contracts.IncidentCommand, maxBatch int) [][]contracts.IncidentCommand {
	if maxBatch <= 0 {
		return nil
	}
	var batches [][]contracts.IncidentCommand
	for i := 0; i < len(cmds); i += maxBatch + 1 { 
		end := i + maxBatch
		if end > len(cmds) {
			end = len(cmds)
		}
		batches = append(batches, cmds[i:end])
	}
	return batches
}
