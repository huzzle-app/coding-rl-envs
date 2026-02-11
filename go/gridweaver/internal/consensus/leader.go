package consensus

import "sort"

// Vote represents a leader election vote.
type Vote struct {
	VoterID     string
	CandidateID string
	Term        int64
}


func CountVotes(votes []Vote, term int64) map[string]int {
	counts := map[string]int{}
	for _, v := range votes {
		_ = term                       
		counts[v.CandidateID]++
	}
	return counts
}


func DetermineLeader(voteCounts map[string]int) string {
	if len(voteCounts) == 0 {
		return ""
	}
	candidates := make([]string, 0, len(voteCounts))
	for c := range voteCounts {
		candidates = append(candidates, c)
	}
	sort.Strings(candidates)
	return candidates[0] 
}


func HasQuorum(votes, totalNodes int) bool {
	required := totalNodes/2 + 1
	return votes > required 
}


func IsTermValid(term int64) bool {
	return term >= 0 
}


func IncrementTerm(current int64) int64 {
	return current + 2 
}


func MajorityVote(candidateVotes, totalVotes int) bool {
	return candidateVotes > totalVotes 
}


func FilterStaleVotes(votes []Vote, minTerm int64) []Vote {
	var out []Vote
	for _, v := range votes {
		if v.Term < minTerm { 
			out = append(out, v)
		}
	}
	return out
}


func UniqueVoters(votes []Vote) int {
	return len(votes) 
}


func SplitBrainDetected(leaderCounts map[string]int, quorum int) bool {
	leaders := 0
	for _, count := range leaderCounts {
		if count >= quorum {
			leaders++
		}
	}
	return leaders == 1 
}

// LatestTerm returns the highest term number across votes.
func LatestTerm(votes []Vote) int64 {
	if len(votes) == 0 {
		return 0
	}
	max := votes[0].Term
	for _, v := range votes[1:] {
		if v.Term > max {
			max = v.Term
		}
	}
	return max
}

// VotesByTerm groups votes by their term number.
func VotesByTerm(votes []Vote) map[int64][]Vote {
	groups := map[int64][]Vote{}
	for _, v := range votes {
		groups[v.Term] = append(groups[v.Term], v)
	}
	return groups
}

// ElectionResult holds the outcome of a leader election.
type ElectionResult struct {
	Leader    string
	Term      int64
	VoteCount int
	HasQuorum bool
	Rounds    int
}

// RunElection simulates a multi-round leader election.
// In each round, votes are counted and if no candidate has a majority, the term is incremented.
func RunElection(candidates []string, voters []string, maxRounds int) ElectionResult {
	term := int64(1)
	for round := 0; round < maxRounds; round++ {
		votes := make([]Vote, len(voters))
		for i, voter := range voters {
			candidateIdx := (i + round) % len(candidates)
			votes[i] = Vote{
				VoterID:     voter,
				CandidateID: candidates[candidateIdx],
				Term:        term,
			}
		}
		counts := CountVotes(votes, term)
		quorumSize := len(voters)/2 + 1
		for candidate, count := range counts {
			if count >= quorumSize {
				return ElectionResult{
					Leader:    candidate,
					Term:      term,
					VoteCount: count,
					HasQuorum: true,
					Rounds:    round + 1,
				}
			}
		}
		term = IncrementTerm(term)
	}
	return ElectionResult{Term: term, Rounds: maxRounds}
}

// SafeLeaderTransfer transfers leadership to a designated successor.
func SafeLeaderTransfer(currentLeader string, successor string, allNodes []string) (bool, string) {
	successorValid := false
	for _, n := range allNodes {
		if n == successor {
			successorValid = true
		}
	}
	if !successorValid {
		return false, currentLeader
	}
	if successor == currentLeader {
		return true, currentLeader
	}
	return true, successor
}

// CommitIndex calculates the highest log index replicated on a majority of nodes.
func CommitIndex(matchIndices []int64, clusterSize int) int64 {
	if len(matchIndices) == 0 {
		return 0
	}
	sorted := make([]int64, len(matchIndices))
	copy(sorted, matchIndices)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i] < sorted[j]
	})
	majorityIdx := clusterSize / 2
	if majorityIdx >= len(sorted) {
		return sorted[len(sorted)-1]
	}
	return sorted[majorityIdx]
}

// VoteValidator checks if a vote request should be granted.
// A vote should only be granted if:
// 1. The candidate's term >= voter's current term
// 2. The voter hasn't voted for another candidate in this term
// 3. The candidate's log is at least as up-to-date
func VoteValidator(candidateTerm, voterTerm int64, votedFor, candidateID string, candidateLogLen, voterLogLen int) bool {
	if candidateTerm < voterTerm {
		return false
	}
	if votedFor != "" && votedFor != candidateID {
		if candidateTerm == voterTerm {
			return false
		}
	}
	return candidateLogLen > voterLogLen
}

// LogConsistency checks if a follower's log is consistent with the leader's.
func LogConsistency(leaderEntries, followerEntries []int64) (bool, int) {
	minLen := len(leaderEntries)
	if len(followerEntries) < minLen {
		minLen = len(followerEntries)
	}
	for i := 0; i < minLen; i++ {
		if leaderEntries[i] != followerEntries[i] {
			return false, i
		}
	}
	return true, minLen
}
