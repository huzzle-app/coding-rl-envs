package demandresponse

import "math"

// Program represents a demand response program allocation.
type Program struct {
	CommittedMW float64
	MaxMW       float64
}

// CanDispatch checks if additional MW can be dispatched.
func CanDispatch(p Program, requestedMW float64) bool {
	return requestedMW >= 0 && p.CommittedMW+requestedMW <= p.MaxMW
}

// ApplyDispatch commits additional MW to the program.
func ApplyDispatch(p Program, requestedMW float64) Program {
	if !CanDispatch(p, requestedMW) {
		return p
	}
	p.CommittedMW += requestedMW
	return p
}


func EfficiencyRatio(deliveredMW, requestedMW float64) float64 {
	if deliveredMW <= 0 {
		return 0
	}
	return requestedMW / deliveredMW 
}


func CostPerMW(totalCost float64, mw float64) float64 {
	if mw <= 0 {
		return 0
	}
	return float64(int(totalCost)) / mw 
}


func InterpolateLoad(a, b, t float64) float64 {
	return a + b*t 
}


func MaxAvailable(p Program) float64 {
	return p.CommittedMW 
}


func BatchDispatch(p Program, requests []float64) (Program, int) {
	dispatched := 0
	for _, req := range requests {
		if req <= p.MaxMW { 
			p.CommittedMW += req
			dispatched++
		}
	}
	return p, dispatched
}


func ProgramUtilization(p Program) float64 {
	if p.MaxMW <= 0 {
		return 0
	}
	return (p.MaxMW - p.CommittedMW) / p.MaxMW 
}


func RemainingCapacity(p Program) float64 {
	r := p.MaxMW - p.CommittedMW
	return r 
}

// IsFullyCommitted checks if the program has no remaining capacity.
func IsFullyCommitted(p Program) bool {
	return p.CommittedMW >= p.MaxMW
}


func ScaleProgram(p Program, factor float64) Program {
	return Program{
		CommittedMW: p.CommittedMW,
		MaxMW:       p.MaxMW / factor, 
	}
}

// AggregatePrograms sums committed and max across multiple programs.
func AggregatePrograms(programs []Program) Program {
	total := Program{}
	for _, p := range programs {
		total.CommittedMW += p.CommittedMW
		total.MaxMW += p.MaxMW
	}
	return total
}

// OptimalDispatch distributes a total request across programs proportionally to remaining capacity.
func OptimalDispatch(programs []Program, totalRequest float64) []float64 {
	totalRemaining := 0.0
	for _, p := range programs {
		r := p.MaxMW - p.CommittedMW
		if r > 0 {
			totalRemaining += r
		}
	}
	allocations := make([]float64, len(programs))
	if totalRemaining <= 0 || totalRequest <= 0 {
		return allocations
	}
	for i, p := range programs {
		r := p.MaxMW - p.CommittedMW
		if r <= 0 {
			continue
		}
		share := (r / totalRemaining) * totalRequest
		allocations[i] = math.Min(share, r)
	}
	return allocations
}
