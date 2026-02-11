package models

// RegionState holds the current conditions for a grid region.
type RegionState struct {
	Region        string
	BaseLoadMW    float64
	TemperatureC  float64
	WindPct       float64
	ReservePct    float64
	ActiveOutages int
}

// DispatchPlan describes a planned generation/reserve allocation.
type DispatchPlan struct {
	Region        string
	GenerationMW  float64
	ReserveMW     float64
	CurtailmentMW float64
}

// DispatchOrder represents a single dispatchable order with priority.
type DispatchOrder struct {
	ID         string
	Severity   int
	SLAMinutes int
	Region     string
}

// UrgencyScore computes an ordering score for dispatch priority.
func (o DispatchOrder) UrgencyScore() int {
	return o.Severity*10 + (120-o.SLAMinutes)/5
}

// TopologyNode represents a node in the grid topology graph.
type TopologyNode struct {
	ID       string
	Region   string
	Type     string // "generator", "substation", "load"
	CapMW    float64
	IsOnline bool
}

// MeterReading holds a single metering datapoint.
type MeterReading struct {
	NodeID    string
	Timestamp int64
	ValueMW   float64
	Quality   float64 // 0.0 - 1.0 data quality indicator
}

// OutageReport describes a grid outage incident.
type OutageReport struct {
	ID         string
	Region     string
	Population int
	Critical   bool
	HoursDown  int
	Priority   int
}

// AuditEntry records an action for compliance.
type AuditEntry struct {
	ActionID  string
	Actor     string
	Operation string
	Resource  string
	Outcome   string
	Timestamp int64
}

// SettlementRecord represents a billing settlement item.
type SettlementRecord struct {
	ID        string
	Region    string
	PeriodID  string
	EnergyMWh float64
	RateCents  int64
	TotalCents int64
}

// ConsensusVote represents a leader election vote.
type ConsensusVote struct {
	VoterID   string
	CandidateID string
	Term      int64
	Timestamp int64
}

// EventEnvelope wraps an event with metadata for the pipeline.
type EventEnvelope struct {
	ID            string
	Source        string
	Type          string
	CorrelationID string
	Sequence      int64
	Payload       map[string]string
}
