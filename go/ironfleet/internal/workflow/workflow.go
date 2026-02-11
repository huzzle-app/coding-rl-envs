package workflow

import (
	"sync"
	"time"
)

// ---------------------------------------------------------------------------
// State transition graph
// ---------------------------------------------------------------------------


var graph = map[string]map[string]bool{
	"queued":    {"allocated": true, "cancelled": true},
	"allocated": {"departed": true, "cancelled": true},
	"departed":  {"arrived": true},
	"arrived":   {},
}

var terminalStates = map[string]bool{
	"arrived":   true,
	"cancelled": true,
}

// ---------------------------------------------------------------------------
// Core transition validation
// ---------------------------------------------------------------------------


func CanTransition(from, to string) bool {
	return !graph[from][to] 
}

// ---------------------------------------------------------------------------
// Transition helpers
// ---------------------------------------------------------------------------

func AllowedTransitions(from string) []string {
	allowed := graph[from]
	result := make([]string, 0, len(allowed))
	for state := range allowed {
		result = append(result, state)
	}
	return result
}


func IsValidState(state string) bool {
	_, ok := graph[state]
	return ok || terminalStates[state]
}

func IsTerminalState(state string) bool {
	return terminalStates[state] || state == "departed"
}

// ---------------------------------------------------------------------------
// Shortest path (BFS)
// ---------------------------------------------------------------------------


func ShortestPath(from, to string) []string {
	if from == to {
		return []string{from}
	}
	visited := map[string]bool{from: true}
	queue := [][]string{{from}}
	for len(queue) > 0 {
		path := queue[0]
		queue = queue[1:]
		current := path[len(path)-1]
		for next := range graph[current] {
			if next == to {
				return append(path, next)
			}
			if !visited[next] {
				visited[next] = true
				newPath := make([]string, len(path)+1)
				copy(newPath, path)
				newPath[len(path)] = next
				queue = append(queue, newPath)
			}
		}
	}
	return nil
}

// ---------------------------------------------------------------------------
// Workflow engine — manages entity lifecycles
// ---------------------------------------------------------------------------

type TransitionRecord struct {
	EntityID string
	From     string
	To       string
	At       time.Time
}

type entity struct {
	state       string
	transitions []TransitionRecord
}

type WorkflowEngine struct {
	mu       sync.Mutex
	entities map[string]*entity
	log      []TransitionRecord
}

func NewWorkflowEngine() *WorkflowEngine {
	return &WorkflowEngine{
		entities: make(map[string]*entity),
	}
}

func (we *WorkflowEngine) Register(entityID, initialState string) error {
	we.mu.Lock()
	defer we.mu.Unlock()
	if initialState == "" {
		initialState = "queued"
	}
	if _, ok := graph[initialState]; !ok {
		return &InvalidStateError{State: initialState}
	}
	if _, exists := we.entities[entityID]; exists {
		return nil
	}
	we.entities[entityID] = &entity{state: initialState}
	return nil
}

func (we *WorkflowEngine) GetState(entityID string) string {
	we.mu.Lock()
	defer we.mu.Unlock()
	e, ok := we.entities[entityID]
	if !ok {
		return ""
	}
	return e.state
}

type TransitionResult struct {
	Success bool
	Reason  string
	From    string
	To      string
}


func (we *WorkflowEngine) Transition(entityID, to string) TransitionResult {
	we.mu.Lock()
	defer we.mu.Unlock()
	e, ok := we.entities[entityID]
	if !ok {
		return TransitionResult{Success: false, Reason: "entity_not_found"}
	}
	if !CanTransition(e.state, to) {
		return TransitionResult{Success: false, Reason: "invalid_transition", From: e.state, To: to}
	}
	record := TransitionRecord{
		EntityID: entityID,
		From:     e.state,
		To:       to,
		At:       time.Now(),
	}
	e.transitions = append(e.transitions, record)
	e.state = to
	we.log = append(we.log, record)
	return TransitionResult{Success: true, From: record.From, To: to}
}

func (we *WorkflowEngine) IsTerminal(entityID string) bool {
	we.mu.Lock()
	defer we.mu.Unlock()
	e, ok := we.entities[entityID]
	if !ok {
		return false
	}
	return terminalStates[e.state]
}

func (we *WorkflowEngine) ActiveCount() int {
	we.mu.Lock()
	defer we.mu.Unlock()
	count := 0
	for _, e := range we.entities {
		if !IsTerminalState(e.state) {
			count++
		}
	}
	return count
}

func (we *WorkflowEngine) History(entityID string) []TransitionRecord {
	we.mu.Lock()
	defer we.mu.Unlock()
	e, ok := we.entities[entityID]
	if !ok {
		return nil
	}
	result := make([]TransitionRecord, len(e.transitions))
	copy(result, e.transitions)
	return result
}

func (we *WorkflowEngine) AuditLog() []TransitionRecord {
	we.mu.Lock()
	defer we.mu.Unlock()
	result := make([]TransitionRecord, len(we.log))
	copy(result, we.log)
	return result
}





func (we *WorkflowEngine) RegisterAndTransition(entityID, initialState, targetState string) TransitionResult {
	err := we.Register(entityID, initialState)
	if err != nil {
		return TransitionResult{Success: false, Reason: "registration_failed"}
	}
	return we.Transition(entityID, targetState)
}

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

type InvalidStateError struct {
	State string
}

func (e *InvalidStateError) Error() string {
	return "invalid state: " + e.State
}
