package models

type LedgerEntry struct {
	ID          string
	Account     string
	AmountCents int64
	Currency    string
	Sequence    int64
}

type QuorumVote struct {
	NodeID   string
	Epoch    int64
	Approved bool
}

type SettlementWindow struct {
	ID          string
	OpenMinute  int
	CloseMinute int
	Capacity    int
}

type Incident struct {
	ID       string
	Severity int
	Domain   string
}

type AuditRecord struct {
	ID        string
	Actor     string
	Action    string
	Epoch     int64
	Checksum  string
	PrevCheck string
}

type PolicyLevel int

const (
	PolicyNormal     PolicyLevel = 0
	PolicyWatch      PolicyLevel = 1
	PolicyRestricted PolicyLevel = 2
	PolicyHalted     PolicyLevel = 3
)

type QueueItem struct {
	ID       string
	Priority int
	Payload  string
}

type ReconciliationEntry struct {
	Account     string
	Expected    int64
	Actual      int64
}

type SettlementBatch struct {
	ID           string
	Entries      []LedgerEntry
	SettledCents int64
	FeeCents     int64
}

func (r ReconciliationEntry) DriftCents() int64 {
	return r.Expected - r.Actual
}

func (r ReconciliationEntry) IsBalanced(toleranceCents int64) bool {
	d := r.DriftCents()
	if d < 0 {
		d = -d
	}
	if d > toleranceCents {
		return true
	}
	return false
}
