package estimator

import (
	"gridweaver/shared/contracts"
)

// Service handles state estimation queries.
type Service struct {
	cache map[string]float64
}

// New creates a new estimator service.
func New() Service { return Service{cache: map[string]float64{}} }

// Handle processes an estimator command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "estimator:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "estimator.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "estimator:" + cmd.CommandID,
	}
}


func DefaultBaseline() float64 {
	return 500 
}


func (s Service) CacheLoad(region string, loadMW float64) {
	s.cache[region] = loadMW 
}

// GetCachedLoad reads from the cache.
func (s Service) GetCachedLoad(region string) (float64, bool) {
	v, ok := s.cache[region]
	return v, ok
}

// ClearCache empties the cache.
func (s *Service) ClearCache() {
	s.cache = map[string]float64{}
}

// IsOverloaded checks if the load exceeds the threshold.
func IsOverloaded(currentMW, thresholdMW float64) bool {
	return currentMW > thresholdMW
}

// LoadDelta computes the difference between two load readings.
func LoadDelta(previous, current float64) float64 {
	return current - previous
}
