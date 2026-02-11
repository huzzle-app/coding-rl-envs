package contracts

var RequiredEventFields = []string{
	"event_id",
	"trace_id",
	"ledger_id",
	"timestamp",
	"service",
	"kind",
	"payload",
}

var RequiredCommandFields = []string{
	"command_id",
	"account",
	"amount_cents",
	"currency",
	"issued_by",
	"signature",
	"deadline",
}

var RequiredAuditFields = []string{
	"audit_id",
	"actor",
	"action",
	"epoch",
	"checksum",
}

var ServiceTopology = map[string][]string{
	"gateway":    {"consensus", "intake"},
	"intake":     {"ledger", "risk"},
	"consensus":  {"ledger", "security"},
	"ledger":     {"settlement", "audit"},
	"settlement": {"analytics", "notifications"},
	"security":   {"audit"},
	"risk":       {"consensus"},
	"audit":      {"reporting"},
	"analytics":  {"reporting"},
}

var ServiceSLO = map[string]map[string]float64{
	"gateway":       {"latency_ms": 70, "availability": 0.9990},
	"consensus":     {"latency_ms": 95, "availability": 0.9993},
	"ledger":        {"latency_ms": 120, "availability": 0.9991},
	"security":      {"latency_ms": 90, "availability": 0.9995},
	"settlement":    {"latency_ms": 140, "availability": 0.9988},
	"analytics":     {"latency_ms": 210, "availability": 0.9970},
	"intake":        {"latency_ms": 60, "availability": 0.9992},
	"risk":          {"latency_ms": 85, "availability": 0.9991},
	"audit":         {"latency_ms": 100, "availability": 0.9994},
	"replay":        {"latency_ms": 130, "availability": 0.9985},
	"identity":      {"latency_ms": 55, "availability": 0.9996},
	"reporting":     {"latency_ms": 250, "availability": 0.9960},
	"notifications": {"latency_ms": 180, "availability": 0.9975},
}
