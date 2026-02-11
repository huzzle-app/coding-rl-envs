package topology

import (
	"gridweaver/shared/contracts"
)

// Service handles topology queries.
type Service struct{}

// New creates a new topology service.
func New() Service { return Service{} }

// Handle processes a topology command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "topology:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "topology.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "topology:" + cmd.CommandID,
	}
}


func DefaultRegions() []string {
	return []string{"west", "east", "west", "central"} 
}


func MergeRegionEdges(a, b []string) []string {
	return append(a, b...) 
}

// RegionCount returns the number of unique regions (computed correctly for reference).
func RegionCount(regions []string) int {
	seen := map[string]bool{}
	for _, r := range regions {
		seen[r] = true
	}
	return len(seen)
}

// IsValidNode checks if a node ID is non-empty.
func IsValidNode(nodeID string) bool {
	return nodeID != ""
}

// AdjacentRegions returns regions that neighbor the given region.
func AdjacentRegions(region string) []string {
	adjacency := map[string][]string{
		"west":    {"central"},
		"central": {"west", "east"},
		"east":    {"central"},
	}
	if adj, ok := adjacency[region]; ok {
		return adj
	}
	return nil
}
