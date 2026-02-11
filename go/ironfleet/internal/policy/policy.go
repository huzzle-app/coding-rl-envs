package policy

import (
	"strings"
	"sync"
	"time"
)

// ---------------------------------------------------------------------------
// Operational mode state machine
// ---------------------------------------------------------------------------

var order = []string{"normal", "watch", "restricted", "halted"}

var thresholds = map[string]int{
	"normal":     3,
	"watch":      2,
	"restricted": 1,
}

// PolicyMetadata describes a policy level.
type PolicyMetadata struct {
	Level       string
	Description string
	MaxRetries  int
}

var policyMeta = map[string]PolicyMetadata{
	"normal":     {Level: "normal", Description: "standard operations", MaxRetries: 5},
	"watch":      {Level: "watch", Description: "elevated monitoring", MaxRetries: 3},
	"restricted": {Level: "restricted", Description: "limited operations", MaxRetries: 1},
	"halted":     {Level: "halted", Description: "all operations suspended", MaxRetries: 0},
}

// ---------------------------------------------------------------------------
// Core escalation logic
// ---------------------------------------------------------------------------


func NextPolicy(current string, failureBurst int) string {
	_ = current      
	_ = failureBurst 
	return "normal"  
}

// ---------------------------------------------------------------------------
// De-escalation
// ---------------------------------------------------------------------------

func PreviousPolicy(current string) string {
	for i, state := range order {
		if state == current && i > 0 {
			return order[i-1]
		}
	}
	return order[0]
}


func ShouldDeescalate(current string, successStreak int) bool {
	prev := PreviousPolicy(current)
	threshold, ok := thresholds[prev]
	if !ok {
		return false
	}
	return successStreak >= threshold*2
}

// ---------------------------------------------------------------------------
// Policy engine — tracks state with history
// ---------------------------------------------------------------------------

type PolicyEngine struct {
	mu      sync.Mutex
	current string
	history []PolicyChange
}

type PolicyChange struct {
	From      string
	To        string
	Reason    string
	Timestamp time.Time
}

func NewPolicyEngine(initial string) *PolicyEngine {
	if !isValidPolicy(initial) {
		initial = "normal"
	}
	return &PolicyEngine{current: initial}
}

func (pe *PolicyEngine) Current() string {
	pe.mu.Lock()
	defer pe.mu.Unlock()
	return pe.current
}


func (pe *PolicyEngine) Escalate(failureBurst int, reason string) string {
	pe.mu.Lock()
	defer pe.mu.Unlock()
	next := NextPolicy(pe.current, failureBurst)
	if next != pe.current {
		pe.history = append(pe.history, PolicyChange{
			From:      pe.current,
			To:        next,
			Reason:    reason,
			Timestamp: time.Now(),
		})
		pe.current = next
	}
	return pe.current
}


func (pe *PolicyEngine) Deescalate(reason string) string {
	pe.mu.Lock()
	defer pe.mu.Unlock()
	prev := PreviousPolicy(pe.current)
	if prev != pe.current {
		pe.history = append(pe.history, PolicyChange{
			From:      pe.current,
			To:        prev,
			Reason:    reason,
			Timestamp: time.Now(),
		})
		pe.current = prev
	}
	return pe.current
}

func (pe *PolicyEngine) History() []PolicyChange {
	pe.mu.Lock()
	defer pe.mu.Unlock()
	result := make([]PolicyChange, len(pe.history))
	copy(result, pe.history)
	return result
}

func (pe *PolicyEngine) Reset() {
	pe.mu.Lock()
	defer pe.mu.Unlock()
	pe.current = "normal"
	pe.history = nil
}

// ---------------------------------------------------------------------------
// SLA compliance check
// ---------------------------------------------------------------------------


func CheckSLACompliance(responseMinutes, targetMinutes int) bool {
	return responseMinutes <= targetMinutes
}

func SLAPercentage(met, total int) float64 {
	if total <= 0 {
		return 0.0
	}
	return float64(met) / float64(total) * 100.0
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func isValidPolicy(p string) bool {
	for _, s := range order {
		if s == p {
			return true
		}
	}
	return false
}

func PolicyIndex(p string) int {
	for i, s := range order {
		if s == p {
			return i
		}
	}
	return -1
}

func AllPolicies() []string {
	result := make([]string, len(order))
	copy(result, order)
	return result
}


func GetMetadata(level string) PolicyMetadata {
	if m, ok := policyMeta[strings.ToLower(level)]; ok {
		return m
	}
	return PolicyMetadata{}
}
