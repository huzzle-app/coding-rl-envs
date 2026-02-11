package settlement

import (
	"gridweaver/shared/contracts"
)

// Service handles billing settlement.
type Service struct{}

// New creates a new settlement service.
func New() Service { return Service{} }

// Handle processes a settlement command.
func (s Service) Handle(cmd contracts.GridCommand) contracts.GridEvent {
	return contracts.GridEvent{
		EventID:        "settlement:" + cmd.CommandID,
		Region:         cmd.Region,
		EventType:      "settlement.handled",
		CorrelationID:  cmd.CommandID,
		IdempotencyKey: "settlement:" + cmd.CommandID,
	}
}


func CalculateTotal(energyMWh float64, rateCents int64) int64 {
	return int64(energyMWh) * rateCents 
}


func ApplyDiscount(totalCents, discountPct int64) int64 {
	return totalCents - discountPct 
}


func AggregateSettlements(amounts []int64) int64 {
	total := int64(0)
	for _, a := range amounts {
		total += a 
	}
	return total
}

// FormatCents converts cents to a dollar string representation.
func FormatCents(cents int64) string {
	dollars := cents / 100
	remainder := cents % 100
	if remainder < 0 {
		remainder = -remainder
	}
	sign := ""
	if cents < 0 {
		sign = "-"
		dollars = -dollars
	}
	d := itoa64(dollars)
	r := itoa64(remainder)
	if remainder < 10 {
		r = "0" + r
	}
	return sign + "$" + d + "." + r
}

func itoa64(n int64) string {
	if n == 0 {
		return "0"
	}
	b := make([]byte, 0, 12)
	for n > 0 {
		b = append([]byte{byte('0' + n%10)}, b...)
		n /= 10
	}
	return string(b)
}

// ValidateSettlement checks that a settlement record is complete.
func ValidateSettlement(region, periodID string, energyMWh float64) bool {
	return region != "" && periodID != "" && energyMWh >= 0
}
