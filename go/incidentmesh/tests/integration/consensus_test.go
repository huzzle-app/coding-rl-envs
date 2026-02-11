package integration

import (
	"testing"

	"incidentmesh/internal/consensus"
)

func TestConsensusExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"ElectLeader", func(t *testing.T) {
			s := consensus.ElectLeader([]string{"n1", "n2", "n3"}, 1)
			if s.NodeID == "" {
				t.Fatalf("expected leader")
			}
		}},
		{"ElectEmpty", func(t *testing.T) {
			s := consensus.ElectLeader(nil, 1)
			if s.NodeID != "" {
				t.Fatalf("expected empty")
			}
		}},
		{"LeaseValid", func(t *testing.T) {
			s := consensus.LeaderState{LeaseExpiry: 1000}
			if !consensus.IsLeaseValid(s, 500) {
				t.Fatalf("expected valid")
			}
		}},
		{"LeaseExpired", func(t *testing.T) {
			s := consensus.LeaderState{LeaseExpiry: 100}
			if consensus.IsLeaseValid(s, 200) {
				t.Fatalf("expected expired")
			}
		}},
		{"SplitBrain", func(t *testing.T) {
			leaders := []consensus.LeaderState{{IsLeader: true}, {IsLeader: true}, {IsLeader: false}}
			r := consensus.DetectSplitBrain(leaders)
			// Two leaders detected = split brain
			if !r { t.Fatalf("expected split brain detection with 2 leaders") }
		}},
		{"IncrementTerm", func(t *testing.T) {
			s := consensus.IncrementTerm(consensus.LeaderState{Term: 5})
			if s.Term != 6 { t.Fatalf("expected term 6, got %d", s.Term) }
		}},
		{"VoteQuorum", func(t *testing.T) {
			r := consensus.VoteQuorum(3, 5)
			// 3 votes out of 5 nodes = majority
			if !r { t.Fatalf("expected quorum with 3/5 votes") }
		}},
		{"LeaseRenew", func(t *testing.T) {
			s := consensus.LeaseRenew(consensus.LeaderState{NodeID: "n1", Term: 1}, 300, 1000)
			// Lease renewed at now=1000 with duration 300 should expire at 1300
			if s.LeaseExpiry != 1300 { t.Fatalf("expected lease expiry 1300, got %d", s.LeaseExpiry) }
		}},
		{"NodePriority", func(t *testing.T) {
			p := consensus.NodePriority("n1", map[string]int{"n1": 10, "n2": 5})
			if p != 10 { t.Fatalf("expected priority 10 for n1, got %d", p) }
		}},
		{"ConsensusRound", func(t *testing.T) {
			winner := consensus.ConsensusRound([]string{"n1", "n2"}, map[string]bool{"n1": true, "n2": false})
			if winner == "" {
				t.Fatalf("expected winner")
			}
		}},
		{"PartitionDetect", func(t *testing.T) {
			r := consensus.PartitionDetect([]string{"n1"}, 5)
			// Only 1 node reachable out of 5 = partition
			if !r { t.Fatalf("expected partition detection with 1/5 nodes reachable") }
		}},
		{"MergeState", func(t *testing.T) {
			local := consensus.LeaderState{Term: 3}
			remote := consensus.LeaderState{Term: 5}
			m := consensus.MergeState(local, remote)
			// Should take higher term
			if m.Term != 5 { t.Fatalf("expected merged term 5, got %d", m.Term) }
		}},
		{"StepDown", func(t *testing.T) {
			s := consensus.StepDown(consensus.LeaderState{IsLeader: true, Term: 5})
			if s.IsLeader { t.Fatalf("expected IsLeader=false after step down") }
		}},
		{"TermCompare", func(t *testing.T) {
			r := consensus.TermComparison(consensus.LeaderState{Term: 5}, consensus.LeaderState{Term: 3})
			// Term 5 > Term 3, so r should be positive
			if r <= 0 { t.Fatalf("expected positive comparison (5 > 3), got %d", r) }
		}},
		{"Heartbeat", func(t *testing.T) {
			r := consensus.HeartbeatCheck(900, 1000, 200)
			// Last heartbeat at 900, now=1000, timeout=200. 1000-900=100 < 200, so valid
			if !r { t.Fatalf("expected valid heartbeat (100ms since last < 200ms timeout)") }
		}},
		{"TransferLeader", func(t *testing.T) {
			from := consensus.LeaderState{NodeID: "n1", Term: 5, IsLeader: true}
			to := consensus.LeaderState{NodeID: "n2"}
			result := consensus.TransferLeadership(from, to)
			if result.NodeID != "n2" {
				t.Fatalf("expected n2")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
