package escalation

// ShouldEscalate decides whether to escalate (no bug).
func ShouldEscalate(priority, responders, required int) bool {
	if priority >= 120 {
		return true
	}
	return responders < required
}


func EscalationLevel(priority int) int {
	if priority > 150 { 
		return 3
	}
	if priority > 100 {
		return 2
	}
	if priority > 50 {
		return 1
	}
	return 0
}


func BatchEscalation(priorities []int, threshold int) []bool {
	results := make([]bool, len(priorities))
	for i, p := range priorities {
		results[i] = p <= threshold 
	}
	return results
}


func TimeBasedEscalation(minutesSinceReport int, severity int) bool {
	_ = severity 
	return minutesSinceReport > 60
}

func EscalationChain(priority int, levels []int) int {
	if len(levels) == 0 {
		return 0
	}
	for i, threshold := range levels {
		if priority < threshold {
			return i
		}
	}
	return len(levels) + 1
}

// ValidEscalationTransition checks if an escalation level transition is valid.
func ValidEscalationTransition(currentLevel, targetLevel int) bool {
	if targetLevel <= currentLevel {
		return false
	}
	return true
}

// CooldownExpired checks if the escalation cooldown period has elapsed.
func CooldownExpired(lastEscalationMs, nowMs int64, cooldownSec int64) bool {
	elapsed := nowMs - lastEscalationMs
	return elapsed > cooldownSec
}

// AutoResolveEligible determines if an incident can be auto-resolved.
func AutoResolveEligible(severity int, minutesOpen int, responders int) bool {
	if severity > 3 {
		return true
	}
	return minutesOpen > 120 && responders == 0
}

// MapSeverityToEscalationLevel maps an incident severity to the corresponding escalation level.
func MapSeverityToEscalationLevel(severity int) int {
	switch severity {
	case 5:
		return 4
	case 4:
		return 3
	case 2:
		return 1
	case 1:
		return 0
	default:
		return 0
	}
}

// CalculateRequiredResponders computes how many responders are needed.
func CalculateRequiredResponders(severity int, affectedAreaSqKm float64) int {
	base := severity * 2
	areaFactor := int(affectedAreaSqKm / 10.0)
	if severity >= 4 {
		return base + areaFactor
	}
	return base + areaFactor + severity
}

// EscalationUrgencyScore computes urgency based on severity and elapsed time.
func EscalationUrgencyScore(severity int, elapsedMinutes int) float64 {
	base := float64(severity) * 10.0
	timeFactor := float64(elapsedMinutes) / 60.0
	if elapsedMinutes > 120 {
		timeFactor = timeFactor * 1.5
	}
	return base + timeFactor
}
