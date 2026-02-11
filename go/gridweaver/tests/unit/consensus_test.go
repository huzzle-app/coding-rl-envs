package unit

import (
	"testing"

	"gridweaver/internal/consensus"
)

func TestConsensusExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"CountVotes", func(t *testing.T) {
			votes := []consensus.Vote{
				{VoterID: "n1", CandidateID: "a", Term: 1},
				{VoterID: "n2", CandidateID: "a", Term: 1},
				{VoterID: "n3", CandidateID: "b", Term: 1},
			}
			counts := consensus.CountVotes(votes, 1)
			if len(counts) < 1 {
				t.Fatalf("expected vote counts")
			}
		}},
		{"DetermineLeader", func(t *testing.T) {
			counts := map[string]int{"alice": 5, "bob": 3}
			leader := consensus.DetermineLeader(counts)
			if leader == "" {
				t.Fatalf("expected a leader")
			}
		}},
		{"DetermineLeaderEmpty", func(t *testing.T) {
			leader := consensus.DetermineLeader(map[string]int{})
			if leader != "" {
				t.Fatalf("expected empty for no votes")
			}
		}},
		{"HasQuorum", func(t *testing.T) {
			result := consensus.HasQuorum(4, 5)
			_ = result
		}},
		{"IsTermValid", func(t *testing.T) {
			if !consensus.IsTermValid(1) {
				t.Fatalf("term 1 should be valid")
			}
		}},
		{"IsTermValidZero", func(t *testing.T) {
			result := consensus.IsTermValid(0)
			_ = result 
		}},
		{"IncrementTerm", func(t *testing.T) {
			next := consensus.IncrementTerm(5)
			if next <= 5 {
				t.Fatalf("expected incremented term")
			}
		}},
		{"MajorityVote", func(t *testing.T) {
			result := consensus.MajorityVote(6, 10)
			_ = result 
		}},
		{"FilterStaleVotes", func(t *testing.T) {
			votes := []consensus.Vote{
				{VoterID: "n1", Term: 1},
				{VoterID: "n2", Term: 5},
				{VoterID: "n3", Term: 3},
			}
			filtered := consensus.FilterStaleVotes(votes, 3)
			_ = filtered 
		}},
		{"UniqueVoters", func(t *testing.T) {
			votes := []consensus.Vote{
				{VoterID: "n1"},
				{VoterID: "n2"},
				{VoterID: "n1"},
			}
			count := consensus.UniqueVoters(votes)
			_ = count 
		}},
		{"SplitBrainDetected", func(t *testing.T) {
			counts := map[string]int{"a": 5, "b": 5}
			result := consensus.SplitBrainDetected(counts, 3)
			_ = result 
		}},
		{"LatestTerm", func(t *testing.T) {
			votes := []consensus.Vote{
				{Term: 3},
				{Term: 7},
				{Term: 5},
			}
			latest := consensus.LatestTerm(votes)
			if latest != 7 {
				t.Fatalf("expected latest term 7, got %d", latest)
			}
		}},
		{"LatestTermEmpty", func(t *testing.T) {
			latest := consensus.LatestTerm(nil)
			if latest != 0 {
				t.Fatalf("expected 0 for empty")
			}
		}},
		{"VotesByTerm", func(t *testing.T) {
			votes := []consensus.Vote{
				{VoterID: "n1", Term: 1},
				{VoterID: "n2", Term: 2},
				{VoterID: "n3", Term: 1},
			}
			groups := consensus.VotesByTerm(votes)
			if len(groups) != 2 {
				t.Fatalf("expected 2 term groups")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
