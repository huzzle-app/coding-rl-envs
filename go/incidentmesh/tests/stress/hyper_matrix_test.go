package stress

import (
	"fmt"
	"testing"

	"incidentmesh/internal/capacity"
	"incidentmesh/internal/communications"
	"incidentmesh/internal/compliance"
	"incidentmesh/internal/config"
	"incidentmesh/internal/consensus"
	"incidentmesh/internal/escalation"
	"incidentmesh/internal/events"
	"incidentmesh/internal/resilience"
	"incidentmesh/internal/routing"
	"incidentmesh/internal/security"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
)

func TestHyperMatrix(t *testing.T) {
	// Section 1: triage_priority (10 x 8 = 80)
	// Tests ClassifyIncident BUG(P01): always returns "low"
	for sev := 0; sev < 10; sev++ {
		for crit := 0; crit < 8; crit++ {
			sev, crit := sev, crit
			t.Run(fmt.Sprintf("triage_priority/s%d_c%d", sev, crit), func(t *testing.T) {
				i := models.Incident{Severity: sev, Criticality: crit}
				score := triage.PriorityScore(i)
				class := triage.ClassifyIncident(i)
				
				// High severity (>=4) should return "critical"
				if sev >= 4 && class != "critical" {
					t.Errorf("severity %d should classify as critical, got %s", sev, class)
				}
				
				boost := triage.CriticalityBoost(crit)
				expected := 10 + crit*3
				if boost != expected {
					t.Errorf("CriticalityBoost(%d) = %d, want %d", crit, boost, expected)
				}
				_ = score
			})
		}
	}

	// Section 2: routing_eta (12 x 8 = 96)
	// Tests ETAEstimate BUG(R05): returns floor instead of ceil
	for dist := 0; dist < 12; dist++ {
		for speed := 1; speed <= 8; speed++ {
			dist, speed := dist, speed
			t.Run(fmt.Sprintf("routing_eta/d%d_s%d", dist, speed), func(t *testing.T) {
				distKm := float64(dist) * 10
				speedKmH := float64(speed) * 10
				eta := routing.ETAEstimate(distKm, speedKmH)
				// ETA in minutes = ceil(distance / speed * 60)
				if speedKmH > 0 {
					expectedMin := int((distKm / speedKmH) * 60)
					if eta < expectedMin-5 || eta > expectedMin+5 {
						t.Errorf("ETAEstimate(%.0f, %.0f) = %d, expected ~%d minutes", distKm, speedKmH, eta, expectedMin)
					}
				}
				
				score := routing.RouteScore(distKm, eta)
				if dist > 0 && score > 100 {
					t.Errorf("RouteScore should decrease with distance, got %.1f for dist=%.0f", score, distKm)
				}
			})
		}
	}

	// Section 3: capacity_rank (10 x 8 = 80)
	// Tests NormalizeBeds BUG(S16) and CapacityMargin BUG(S17)
	for beds := 0; beds < 10; beds++ {
		for icu := 0; icu < 8; icu++ {
			beds, icu := beds, icu
			t.Run(fmt.Sprintf("capacity_rank/b%d_i%d", beds, icu), func(t *testing.T) {
				f := capacity.Facility{BedsFree: beds * 5, ICUFree: icu * 2, DistanceK: 5}
				score := capacity.RankScore(f)
				
				if beds > 0 {
					norm := capacity.NormalizeBeds(beds*5, 100)
					expected := float64(beds*5) / 100.0
					if norm < expected-0.01 || norm > expected+0.01 {
						t.Errorf("NormalizeBeds(%d, 100) = %.2f, want %.2f", beds*5, norm, expected)
					}
				}
				_ = score
			})
		}
	}

	// Section 4: resilience_replay (15 x 8 = 120)
	// Tests QueueDepth BUG(D05): subtracts instead of adding
	for base := 0; base < 15; base++ {
		for ver := int64(0); ver < 8; ver++ {
			base, ver := base, ver
			t.Run(fmt.Sprintf("resilience_replay/b%d_v%d", base, ver), func(t *testing.T) {
				evs := []resilience.IncidentEvent{
					{Version: ver, IdempotencyKey: fmt.Sprintf("k%d", base), PriorityDelta: base},
				}
				s := resilience.ReplayIncidentState(base*10, base, ver, evs)
				
				depth := resilience.QueueDepth(base, int(ver))
				expected := base + int(ver)
				if depth != expected {
					t.Errorf("QueueDepth(%d, %d) = %d, want %d", base, ver, depth, expected)
				}
				_ = s
			})
		}
	}

	// Section 5: security_auth (8 x 6 = 48)
	// Tests ValidateToken BUG(F02): accepts short tokens
	roles := []string{"admin", "dispatcher", "analyst", "field_operator", "observer", "unknown", "admin", "dispatcher"}
	perms := []string{"incident.create", "incident.read", "unit.dispatch", "report.generate", "incident.update", "admin.delete"}
	for ri := 0; ri < 8; ri++ {
		for pi := 0; pi < 6; pi++ {
			ri, pi := ri, pi
			t.Run(fmt.Sprintf("security_auth/r%d_p%d", ri, pi), func(t *testing.T) {
				auth := security.Authorize(roles[ri], perms[pi])
				
				shortValid := security.ValidateToken("x")
				if shortValid {
					t.Errorf("ValidateToken should reject single-char token")
				}
				
				if security.IPAllowed("10.0.0.1", []string{"192.168.1.1"}) {
					t.Errorf("IPAllowed should reject IP not in allowlist")
				}
				_ = auth
			})
		}
	}

	// Section 6: consensus_vote (10 x 8 = 80)
	// Tests VoteQuorum and DetectSplitBrain
	for nodes := 1; nodes <= 10; nodes++ {
		for votes := 0; votes < 8; votes++ {
			nodes, votes := nodes, votes
			t.Run(fmt.Sprintf("consensus_vote/n%d_v%d", nodes, votes), func(t *testing.T) {
				quorum := consensus.VoteQuorum(votes, nodes)
				// Quorum requires majority: votes > nodes/2
				expectedQuorum := votes > nodes/2
				if quorum != expectedQuorum {
					t.Errorf("VoteQuorum(%d, %d) = %v, want %v", votes, nodes, quorum, expectedQuorum)
				}
			})
		}
	}

	// Section 7: events_window (12 x 8 = 96)
	// Tests FilterByType and Deduplicate
	for start := int64(0); start < 12; start++ {
		for end := int64(1); end <= 8; end++ {
			start, end := start, end
			t.Run(fmt.Sprintf("events_window/s%d_e%d", start, end), func(t *testing.T) {
				evs := []events.Event{{Timestamp: start * 10}, {Timestamp: (start + end) * 10}}
				window := events.WindowEvents(evs, start*10, (start+end)*10+5)
				if len(window) < 1 {
					t.Errorf("WindowEvents should return events in range")
				}
				// Test dedup with duplicate IDs
				dupes := []events.Event{{ID: "e1"}, {ID: "e2"}, {ID: "e1"}}
				deduped := events.Deduplicate(dupes)
				if len(deduped) != 2 {
					t.Errorf("Deduplicate should return 2 unique events, got %d", len(deduped))
				}
			})
		}
	}

	// Section 8: escalation_level (10 x 8 = 80)
	// Tests EscalationLevel and TimeBasedEscalation
	for pri := 0; pri < 10; pri++ {
		for thresh := 1; thresh <= 8; thresh++ {
			pri, thresh := pri, thresh
			t.Run(fmt.Sprintf("escalation_level/p%d_t%d", pri, thresh), func(t *testing.T) {
				level := escalation.EscalationLevel(pri * 20)
				shouldEsc := escalation.ShouldEscalate(pri*20, thresh, thresh+1)
				
				if pri >= 5 {
					timeEsc := escalation.TimeBasedEscalation(120, pri)
					if !timeEsc {
						t.Errorf("TimeBasedEscalation(120, %d) should be true for high severity", pri)
					}
				}
				_, _ = level, shouldEsc
			})
		}
	}

	// Section 9: compliance_retention (10 x 8 = 80)
	// Tests RetentionDays BUG(D11): wrong value for tier 2
	for tier := 0; tier < 10; tier++ {
		for age := 0; age < 8; age++ {
			tier, age := tier, age
			t.Run(fmt.Sprintf("compliance_retention/t%d_a%d", tier, age), func(t *testing.T) {
				days := compliance.RetentionDays(tier)
				
				if tier == 2 && days != 180 {
					t.Errorf("RetentionDays(2) = %d, want 180", days)
				}
				
				if age > 0 {
					score := compliance.ComplianceScore(age, age*2)
					expected := 0.5
					if score < expected-0.1 || score > expected+0.1 {
						t.Errorf("ComplianceScore(%d, %d) = %.2f, want ~%.2f", age, age*2, score, expected)
					}
				}
			})
		}
	}

	// Section 10: comms_retry (8 x 8 = 64)
	// Tests RetryDelay BUG(G02): subtracts instead of multiplying
	for attempt := 0; attempt < 8; attempt++ {
		for base := 1; base <= 8; base++ {
			attempt, base := attempt, base
			t.Run(fmt.Sprintf("comms_retry/a%d_b%d", attempt, base), func(t *testing.T) {
				delay := communications.RetryDelay(attempt, base*100)
				
				if attempt > 0 && delay < base*100 {
					t.Errorf("RetryDelay(%d, %d) = %d, should increase with attempts", attempt, base*100, delay)
				}
				
				retries := communications.MaxRetries(attempt)
				if attempt >= 4 && retries == 0 {
					t.Errorf("MaxRetries(%d) = 0, high severity should get more retries", attempt)
				}
			})
		}
	}

	// Section 11: config_parse (10 x 8 = 80)
	// Tests LoadPort BUG(L01) and ParseTimeout BUG(L05)
	for port := 0; port < 10; port++ {
		for timeout := 1; timeout <= 8; timeout++ {
			port, timeout := port, timeout
			t.Run(fmt.Sprintf("config_parse/p%d_t%d", port, timeout), func(t *testing.T) {
				
				defaultPort := config.LoadPort("NONEXISTENT_VAR", 8080+port)
				if defaultPort != 8080+port {
					t.Errorf("LoadPort default = %d, want %d", defaultPort, 8080+port)
				}
				// Test ParseTimeout returns the parsed value
				parsed := config.ParseTimeout(fmt.Sprintf("%d", timeout*1000))
				if parsed != timeout*1000 {
					t.Errorf("ParseTimeout(%d) = %d, want %d", timeout*1000, parsed, timeout*1000)
				}
			})
		}
	}

	// Section 12: routing_filter (6 x 6 = 36)
	// Tests CapacityFilter BUG(R06) and DistanceScore BUG(R10)
	regions := []string{"north", "south", "east", "west", "central", "remote"}
	for ri := 0; ri < 6; ri++ {
		for cap := 0; cap < 6; cap++ {
			ri, cap := ri, cap
			t.Run(fmt.Sprintf("routing_filter/r%d_c%d", ri, cap), func(t *testing.T) {
				units := []models.Unit{
					{ID: "u1", Region: regions[ri], Capacity: cap * 5, ETAmins: 10},
					{ID: "u2", Region: regions[ri], Capacity: cap*5 + 10, ETAmins: 5},
				}
				
				filtered := routing.CapacityFilter(units, cap*5)
				if cap*5 > 0 && len(filtered) < 2 {
					t.Errorf("CapacityFilter should include exact match capacity=%d", cap*5)
				}
				
				negScore := routing.DistanceScore(-10.0)
				if negScore > 0 {
					t.Errorf("DistanceScore(-10) = %.1f, should be 0 or negative for negative distance", negScore)
				}
			})
		}
	}
}
