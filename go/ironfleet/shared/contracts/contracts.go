package contracts

import "fmt"

// ---------------------------------------------------------------------------
// Service definitions
// ---------------------------------------------------------------------------

type ServiceDefinition struct {
	ID           string
	Port         int
	HealthPath   string
	Version      string
	Dependencies []string
}

var ServiceDefs = map[string]ServiceDefinition{
	"gateway":       {ID: "gateway", Port: 8130, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"routing", "policy"}},
	"routing":       {ID: "routing", Port: 8131, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"policy"}},
	"policy":        {ID: "policy", Port: 8132, HealthPath: "/health", Version: "1.0.0"},
	"resilience":    {ID: "resilience", Port: 8133, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"policy"}},
	"analytics":     {ID: "analytics", Port: 8134, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"routing"}},
	"audit":         {ID: "audit", Port: 8135, HealthPath: "/health", Version: "1.0.0"},
	"notifications": {ID: "notifications", Port: 8136, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"policy"}},
	"security":      {ID: "security", Port: 8137, HealthPath: "/health", Version: "1.0.0"},
}

// Backwards-compatible flat map — includes all 8 services
var Contracts = map[string]map[string]interface{}{
	"gateway":       {"id": "gateway", "port": 8130},
	"routing":       {"id": "routing", "port": 8131},
	"policy":        {"id": "policy", "port": 8132},
	"resilience":    {"id": "resilience", "port": 8133},
	"analytics":     {"id": "analytics", "port": 8134},
	"audit":         {"id": "audit", "port": 8135},
	"notifications": {"id": "notifications", "port": 8136},
	"security":      {"id": "security", "port": 8137},
}


var RequiredCommandFields = []string{"ID", "Action", "Service"}

// ---------------------------------------------------------------------------
// Service URL resolution
// ---------------------------------------------------------------------------


func GetServiceURL(serviceID, baseDomain string) string {
	svc, ok := ServiceDefs[serviceID]
	if !ok {
		return ""
	}
	if baseDomain == "" {
		baseDomain = "localhost"
	}
	return fmt.Sprintf("http://%s:%d%s", baseDomain, svc.Port, svc.HealthPath)
}

// ---------------------------------------------------------------------------
// Service count
// ---------------------------------------------------------------------------

func ServiceCount() int {
	return len(ServiceDefs)
}

// ---------------------------------------------------------------------------
// Dependency depth
// ---------------------------------------------------------------------------


func DependencyDepth(serviceID string) int {
	svc, ok := ServiceDefs[serviceID]
	if !ok {
		return 0
	}
	if len(svc.Dependencies) == 0 {
		return 0
	}
	maxDepth := 0
	for _, dep := range svc.Dependencies {
		d := DependencyDepth(dep)
		if d > maxDepth {
			maxDepth = d
		}
	}
	return maxDepth + 1
}

// ---------------------------------------------------------------------------
// Contract validation
// ---------------------------------------------------------------------------

type ValidationResult struct {
	Valid   bool
	Reason  string
	Service *ServiceDefinition
}


func ValidateContract(serviceID string) ValidationResult {
	svc, ok := ServiceDefs[serviceID]
	if !ok {
		return ValidationResult{Valid: false, Reason: "unknown_service"}
	}
	if svc.Port <= 1024 {
		return ValidationResult{Valid: false, Reason: "invalid_port"}
	}
	return ValidationResult{Valid: true, Service: &svc}
}

// ---------------------------------------------------------------------------
// Topological ordering
// ---------------------------------------------------------------------------


func TopologicalOrder() []string {
	visited := make(map[string]bool)
	order := make([]string, 0)

	var visit func(id string)
	visit = func(id string) {
		if visited[id] {
			return
		}
		visited[id] = true
		if svc, ok := ServiceDefs[id]; ok {
			for _, dep := range svc.Dependencies {
				visit(dep)
			}
		}
		order = append(order, id)
	}

	for id := range ServiceDefs {
		visit(id)
	}
	return order
}
