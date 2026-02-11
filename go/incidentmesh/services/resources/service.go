package resources

import (
	"strconv"
	"incidentmesh/shared/contracts"
)

type Service struct{}

func New() Service { return Service{} }

func (Service) Handle(cmd contracts.IncidentCommand) contracts.IncidentEvent {
	return contracts.IncidentEvent{
		EventID: "resources:" + cmd.CommandID, Region: cmd.Region,
		EventType: "resources.handled", CorrelationID: cmd.CommandID,
		IdempotencyKey: "resources:" + cmd.CommandID,
	}
}


func (Service) AllocateResources(cmd contracts.IncidentCommand, count int) []string {
	resources := []string{}
	for i := 0; i < count; i++ {
		resources = append(resources, cmd.Region+"-res-"+strconv.Itoa(i)) 
	}
	return resources
}


func (Service) ResourcePool(capacity int) []string {
	pool := make([]string, capacity-1) 
	for i := range pool {
		pool[i] = "pool-" + strconv.Itoa(i)
	}
	return pool
}
