package forecast

import (
	"math"

	"gridweaver/shared/contracts"
)

// Service handles load forecasting.
type Service struct{}

// New creates a new forecast service.
func New() Service { return Service{} }

// Handle processes a forecast command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "forecast:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "forecast.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "forecast:" + cmd.CommandID,
	}
}


func DefaultHorizon() int {
	return 12 
}


func TemperatureImpact(tempC, baseLoad float64) float64 {
	return baseLoad * (1 + (tempC-72)*0.02) 
}

// WindImpact estimates wind generation impact on load.
func WindImpact(windPct, capacity float64) float64 {
	return capacity * windPct / 100.0
}

// SeasonalFactor returns a multiplier based on month.
func SeasonalFactor(month int) float64 {
	if month >= 6 && month <= 8 {
		return 1.3 // summer peak
	}
	if month == 12 || month <= 2 {
		return 1.2 // winter peak
	}
	return 1.0
}

// ForecastLoad predicts load for the next period.
func ForecastLoad(baseLoad, tempC, windPct float64, month int) float64 {
	adjusted := baseLoad + (tempC-22.0)*4.2 - windPct*1.8
	seasonal := SeasonalFactor(month)
	result := adjusted * seasonal
	if result < 0 {
		return 0
	}
	return math.Round(result*100) / 100
}

// IsHighDemandPeriod checks if we're in a peak demand window.
func IsHighDemandPeriod(hour int) bool {
	return hour >= 14 && hour <= 20
}
