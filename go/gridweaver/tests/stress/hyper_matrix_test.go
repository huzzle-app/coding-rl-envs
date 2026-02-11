package stress

import (
	"fmt"
	"testing"

	"gridweaver/internal/config"
	"gridweaver/internal/concurrency"
	"gridweaver/internal/consensus"
	"gridweaver/internal/demandresponse"
	"gridweaver/internal/dispatch"
	"gridweaver/internal/estimator"
	"gridweaver/internal/events"
	"gridweaver/internal/outage"
	"gridweaver/internal/resilience"
	"gridweaver/internal/security"
	"gridweaver/internal/topology"
	"gridweaver/internal/workflow"
	"gridweaver/pkg/models"
)

// TestHyperMatrix exercises every public function with varying inputs.
// Produces ~900 subtests via t.Run.
func TestHyperMatrix(t *testing.T) {
	regions := []string{"west", "east", "central"}
	temps := []float64{-10, 0, 22, 35, 45}
	winds := []float64{0, 10, 50, 80}
	reserves := []float64{0.05, 0.12, 0.25}
	outages := []int{0, 1, 3, 5}
	idx := 0

	// --- Estimator stress (5*4*4*3 = 240 subtests) ---
	for _, temp := range temps {
		for _, wind := range winds {
			for _, out := range outages {
				for _, res := range reserves {
					idx++
					name := fmt.Sprintf("estimator/%05d/t%.0f_w%.0f_o%d_r%.2f", idx, temp, wind, out, res)
					t.Run(name, func(t *testing.T) {
						state := models.RegionState{
							Region:        "west",
							BaseLoadMW:    800,
							TemperatureC:  temp,
							WindPct:       wind,
							ReservePct:    res,
							ActiveOutages: out,
						}
						load := estimator.EstimateLoad(state)
						if load < 0 {
							t.Fatalf("load must not be negative: %f", load)
						}
						margin := estimator.StabilityMargin(state)
						if margin < 0 {
							t.Fatalf("margin must not be negative: %f", margin)
						}
						_ = estimator.SafetyCheck(state)
					})
				}
			}
		}
	}

	// --- Dispatch stress (3*5*3 = 45 subtests) ---
	demands := []float64{100, 500, 1000, 2000, 5000}
	caps := []float64{800, 2000, 10000}
	for _, r := range regions {
		for _, d := range demands {
			for _, c := range caps {
				idx++
				name := fmt.Sprintf("dispatch/%05d/%s_d%.0f_c%.0f", idx, r, d, c)
				t.Run(name, func(t *testing.T) {
					plan := dispatch.BuildPlan(r, d, 0.12)
					plan = dispatch.ApplyConstraint(plan, c)
					if plan.GenerationMW < 0 {
						t.Fatalf("generation must not be negative")
					}
					if plan.ReserveMW < 0 {
						t.Fatalf("reserve must not be negative")
					}
				})
			}
		}
	}

	// --- Topology stress (5*5 = 25 subtests) ---
	capacities := []float64{10, 50, 100, 500, 1000}
	requestMWs := []float64{0, 25, 100, 500, 1001}
	for _, cap := range capacities {
		for _, req := range requestMWs {
			idx++
			name := fmt.Sprintf("topology/%05d/cap%.0f_req%.0f", idx, cap, req)
			t.Run(name, func(t *testing.T) {
				edge := topology.Edge{From: "a", To: "b", CapacityMW: cap}
				valid := topology.ValidateTransfer(edge, req)
				_ = valid
				rem := topology.RemainingCapacity(edge, req)
				if rem < 0 {
					t.Fatalf("remaining must not be negative")
				}
				_ = topology.ConstrainedTransfer(edge, req, 5)
			})
		}
	}

	// --- Security stress (3*7 = 21 subtests) ---
	roles := []string{"observer", "field_operator", "grid_admin"}
	actions := []string{"read.telemetry", "dispatch.plan", "control.substation", "outage.report", "demand.response", "settlement.calc", "audit.query"}
	for _, role := range roles {
		for _, action := range actions {
			idx++
			name := fmt.Sprintf("security/%05d/%s_%s", idx, role, action)
			t.Run(name, func(t *testing.T) {
				_ = security.Authorize(role, action)
				_ = security.CheckPermission(role, action)
				_ = security.HasAnyPermission(role, []string{action})
			})
		}
	}

	// --- Resilience stress (5*5*3 = 75 subtests) ---
	attempts := []int{1, 2, 3, 4, 5}
	baseBOs := []int{50, 100, 200, 500, 1000}
	failures := []int{0, 3, 6}
	for _, att := range attempts {
		for _, bo := range baseBOs {
			for _, f := range failures {
				idx++
				name := fmt.Sprintf("resilience/%05d/att%d_bo%d_f%d", idx, att, bo, f)
				t.Run(name, func(t *testing.T) {
					r := resilience.DecideRetry(att, 5, bo, f)
					if r.BackoffMs < 0 {
						t.Fatalf("backoff must not be negative")
					}
					_ = resilience.BackoffWithJitter(bo, att, 50)
				})
			}
		}
	}

	// --- Demand Response stress (5*5 = 25 subtests) ---
	committeds := []float64{0, 20, 50, 80, 100}
	maxMWs := []float64{50, 100, 200, 500, 1000}
	for _, committed := range committeds {
		for _, maxMW := range maxMWs {
			idx++
			name := fmt.Sprintf("dr/%05d/c%.0f_m%.0f", idx, committed, maxMW)
			t.Run(name, func(t *testing.T) {
				p := demandresponse.Program{CommittedMW: committed, MaxMW: maxMW}
				_ = demandresponse.CanDispatch(p, 10)
				_ = demandresponse.RemainingCapacity(p)
				_ = demandresponse.ProgramUtilization(p)
				_ = demandresponse.IsFullyCommitted(p)
			})
		}
	}

	// --- Outage stress (4*2*5 = 40 subtests) ---
	pops := []int{100, 5000, 25000, 100000}
	crits := []bool{true, false}
	hours := []int{0, 1, 4, 12, 48}
	for _, pop := range pops {
		for _, crit := range crits {
			for _, hr := range hours {
				idx++
				name := fmt.Sprintf("outage/%05d/p%d_c%v_h%d", idx, pop, crit, hr)
				t.Run(name, func(t *testing.T) {
					c := outage.OutageCase{Population: pop, Critical: crit, HoursDown: hr}
					score := outage.PriorityScore(c)
					if score < 0 {
						t.Fatalf("priority must not be negative")
					}
					_ = outage.IsResolved(c)
				})
			}
		}
	}

	// --- Config stress (4*3 = 12 subtests) ---
	services := []string{"nats", "postgres", "redis", "influx"}
	regionStrings := []string{"west", "west,east", "west,east,central"}
	for _, svc := range services {
		for _, rs := range regionStrings {
			idx++
			name := fmt.Sprintf("config/%05d/%s_%s", idx, svc, rs)
			t.Run(name, func(t *testing.T) {
				c := config.DefaultConfig()
				ep := config.ResolveEndpoint(svc, c)
				if ep == "" {
					t.Fatalf("expected endpoint for %s", svc)
				}
				regions := config.ParseRegions(rs)
				if len(regions) < 1 {
					t.Fatalf("expected at least 1 region")
				}
			})
		}
	}

	// --- Events stress (3*3*3 = 27 subtests) ---
	eventTypes := []string{"dispatch", "outage", "demand"}
	eventRegions := []string{"west", "east", "central"}
	seqs := []int64{10, 50, 100}
	for _, etype := range eventTypes {
		for _, er := range eventRegions {
			for _, seq := range seqs {
				idx++
				name := fmt.Sprintf("events/%05d/%s_%s_%d", idx, etype, er, seq)
				t.Run(name, func(t *testing.T) {
					evt := events.Event{ID: fmt.Sprintf("e%d", idx), Sequence: seq, Type: etype, Region: er}
					evts := []events.Event{evt, {ID: "e0", Sequence: seq + 10, Type: etype, Region: er}}
					sorted := events.SortBySequence(evts)
					if len(sorted) != 2 {
						t.Fatalf("expected 2 sorted events")
					}
					_ = events.MaxSequence(evts)
					groups := events.GroupByRegion(evts)
					if len(groups) < 1 {
						t.Fatalf("expected at least 1 group")
					}
				})
			}
		}
	}

	// --- Consensus stress (3*5*3 = 45 subtests) ---
	candidates := []string{"alice", "bob", "charlie"}
	terms := []int64{1, 2, 3, 5, 10}
	voterCounts := []int{3, 5, 7}
	for _, cand := range candidates {
		for _, term := range terms {
			for _, vc := range voterCounts {
				idx++
				name := fmt.Sprintf("consensus/%05d/%s_t%d_v%d", idx, cand, term, vc)
				t.Run(name, func(t *testing.T) {
					votes := make([]consensus.Vote, vc)
					for i := 0; i < vc; i++ {
						votes[i] = consensus.Vote{VoterID: fmt.Sprintf("n%d", i), CandidateID: cand, Term: term}
					}
					counts := consensus.CountVotes(votes, term)
					if len(counts) < 1 {
						t.Fatalf("expected vote counts")
					}
					_ = consensus.HasQuorum(vc, vc*2-1)
					_ = consensus.IsTermValid(term)
				})
			}
		}
	}

	// --- Concurrency types stress (3*3 = 9 subtests) ---
	poolSizes := []int{1, 4, 8}
	tokenCounts := []int{0, 5, 10}
	for _, ps := range poolSizes {
		for _, tc := range tokenCounts {
			idx++
			name := fmt.Sprintf("concurrency/%05d/pool%d_tok%d", idx, ps, tc)
			t.Run(name, func(t *testing.T) {
				p := concurrency.NewPool(ps)
				if p == nil {
					t.Fatalf("expected non-nil pool")
				}
				_ = concurrency.SemaphoreAcquire(tc, ps*2)
				_ = concurrency.RateLimiterPermit(tc, ps*2)
			})
		}
	}

	// --- Dispatch extended stress (5*3*4 = 60 subtests) ---
	precisions := []int{0, 1, 2}
	rampMinutes := []int{0, 5, 15, 30}
	for _, d := range demands {
		for _, prec := range precisions {
			for _, rm := range rampMinutes {
				idx++
				name := fmt.Sprintf("dispatch_ext/%05d/d%.0f_p%d_r%d", idx, d, prec, rm)
				t.Run(name, func(t *testing.T) {
					rounded := dispatch.RoundGeneration(d, prec)
					if rounded < 0 {
						t.Fatalf("rounded must not be negative")
					}
					_ = dispatch.CalculateRampRate(d, d*1.1, rm)
					_ = dispatch.CurtailmentNeeded(d, d*0.9, d*0.1)
					margin := dispatch.CapacityMargin(d*1.1, d)
					if margin < 0 {
						t.Fatalf("margin must not be negative")
					}
				})
			}
		}
	}

	// --- Estimator extended stress (5*4*3 = 60 subtests) ---
	mwValues := []float64{10, 50, 100, 500, 1000}
	qualities := []float64{0.1, 0.5, 0.8, 1.0}
	steps := []int{1, 5, 10}
	for _, mw := range mwValues {
		for _, q := range qualities {
			for _, step := range steps {
				idx++
				name := fmt.Sprintf("estimator_ext/%05d/mw%.0f_q%.1f_s%d", idx, mw, q, step)
				t.Run(name, func(t *testing.T) {
					readings := []models.MeterReading{
						{ValueMW: mw, Quality: q, Timestamp: 100},
						{ValueMW: mw * 1.1, Quality: q, Timestamp: 200},
					}
					_ = estimator.WeightedAvgLoad(readings)
					_ = estimator.ExponentialSmooth(mw, mw*1.05, 0.3)
					_ = estimator.PeakDemandEstimate(mw, 0.15)
					_ = estimator.LoadForecast(mw, 2, step)
					_ = estimator.VolatilityScore(readings)
					norm := estimator.NormalizeReadings(readings, mw*2)
					if len(norm) != 2 {
						t.Fatalf("expected 2 normalized values")
					}
				})
			}
		}
	}

	// --- Security extended stress (3*3*2 = 18 subtests) ---
	passwords := []string{"short", "mediumpassword", "longpassword12345678"}
	inputs := []string{"normal", "O'Brien", "<script>alert(1)</script>"}
	tokenLens := []int{0, 16}
	for _, pw := range passwords {
		for _, inp := range inputs {
			for _, tl := range tokenLens {
				idx++
				name := fmt.Sprintf("security_ext/%05d/pw%d_tl%d", idx, len(pw), tl)
				t.Run(name, func(t *testing.T) {
					_ = security.HashPassword(pw)
					_ = security.SanitizeInput(inp)
					_ = security.EscapeSQL(inp)
					token := ""
					if tl > 0 {
						token = "abcdefghijklmnop"
					}
					_ = security.ValidateToken(token)
					_ = security.GenerateSessionID(pw)
				})
			}
		}
	}

	// --- Outage extended stress (4*5 = 20 subtests) ---
	crews := []int{0, 1, 3, 5, 10}
	for _, pop := range pops {
		for _, crew := range crews {
			idx++
			name := fmt.Sprintf("outage_ext/%05d/p%d_crew%d", idx, pop, crew)
			t.Run(name, func(t *testing.T) {
				c := outage.OutageCase{Population: pop, Critical: pop > 10000, HoursDown: 5}
				_ = outage.EstimateRestorationHours(c, crew)
				_ = outage.RecordRestoration(c, 2)
				_ = outage.AveragePriority([]outage.OutageCase{c})
				_ = outage.EscalationLevel(pop / 10000)
			})
		}
	}

	// --- Replay stress (3*3*3 = 27 subtests) ---
	baseGens := []float64{300, 500, 1000}
	baseReserves := []float64{30, 70, 150}
	eventCounts := []int{1, 3, 5}
	for _, bg := range baseGens {
		for _, br := range baseReserves {
			for _, ec := range eventCounts {
				idx++
				name := fmt.Sprintf("replay/%05d/g%.0f_r%.0f_e%d", idx, bg, br, ec)
				t.Run(name, func(t *testing.T) {
					evts := make([]resilience.DispatchEvent, ec)
					for i := 0; i < ec; i++ {
						evts[i] = resilience.DispatchEvent{
							Version:         int64(11 + i),
							IdempotencyKey:  fmt.Sprintf("k%d", i),
							GenerationDelta: float64(10 * (i + 1)),
							ReserveDelta:    float64(i + 1),
						}
					}
					snap := resilience.ReplayDispatch(bg, br, 10, evts)
					if snap.Applied < 1 {
						t.Fatalf("expected at least 1 applied event")
					}
				})
			}
		}
	}

	// --- Topology graph stress (3*3*3 = 27 subtests) ---
	nodeCounts := []int{2, 5, 10}
	edgeCaps := []float64{50, 200, 1000}
	distances := []float64{10, 100, 500}
	for _, nc := range nodeCounts {
		for _, ec := range edgeCaps {
			for _, dist := range distances {
				idx++
				name := fmt.Sprintf("topo_graph/%05d/n%d_c%.0f_d%.0f", idx, nc, ec, dist)
				t.Run(name, func(t *testing.T) {
					g := topology.NewGraph()
					for i := 0; i < nc-1; i++ {
						g.AddEdge(topology.Edge{
							From:       fmt.Sprintf("n%d", i),
							To:         fmt.Sprintf("n%d", i+1),
							CapacityMW: ec,
						})
					}
					if g.NodeCount() < 2 {
						t.Fatalf("expected at least 2 nodes")
					}
					_ = topology.BalanceLoad(ec*float64(nc), nc)
					edge := topology.Edge{From: "a", To: "b", CapacityMW: ec}
					_ = topology.TransferCost(edge, dist, 0.01)
				})
			}
		}
	}

	// --- DR extended stress (5*5 = 25 subtests) ---
	requestAmounts := []float64{5, 10, 25, 50, 100}
	for _, committed := range committeds {
		for _, req := range requestAmounts {
			idx++
			name := fmt.Sprintf("dr_ext/%05d/c%.0f_r%.0f", idx, committed, req)
			t.Run(name, func(t *testing.T) {
				p := demandresponse.Program{CommittedMW: committed, MaxMW: 200}
				_ = demandresponse.EfficiencyRatio(req, req+10)
				_ = demandresponse.CostPerMW(req*100, req)
				_ = demandresponse.InterpolateLoad(committed, committed+req, 0.5)
				_ = demandresponse.MaxAvailable(p)
				scaled := demandresponse.ScaleProgram(p, 1.5)
				if scaled.MaxMW < p.MaxMW {
					t.Fatalf("scaled max should be larger")
				}
			})
		}
	}

	// --- Resilience extended stress (3*3*3 = 27 subtests) ---
	successCounts := []int{0, 5, 10}
	failureCounts := []int{0, 2, 8}
	loadPcts := []float64{0.5, 0.85, 0.98}
	for _, sc := range successCounts {
		for _, fc := range failureCounts {
			for _, lp := range loadPcts {
				idx++
				name := fmt.Sprintf("resilience_ext/%05d/s%d_f%d_l%.2f", idx, sc, fc, lp)
				t.Run(name, func(t *testing.T) {
					_ = resilience.HealthScore(sc, fc)
					_ = resilience.CircuitBreakerState(fc, 5)
					_ = resilience.GracefulDegradation(lp)
					_ = resilience.RecoveryDelay(fc, 100)
				})
			}
		}
	}

	// --- Dispatch total generation stress (3*5 = 15 subtests) ---
	for _, r := range regions {
		for _, d := range demands {
			idx++
			name := fmt.Sprintf("dispatch_total/%05d/%s_d%.0f", idx, r, d)
			t.Run(name, func(t *testing.T) {
				plans := dispatch.MultiRegionPlan(
					[]string{r, "central"},
					map[string]float64{r: d, "central": d * 0.5},
					0.12,
				)
				total := dispatch.TotalGeneration(plans)
				if total < 0 {
					t.Fatalf("total generation must not be negative")
				}
			})
		}
	}

	// --- Dispatch weighted stress (5*3 = 15 subtests) ---
	weightSets := [][]float64{{1, 1, 1}, {1, 2, 3}, {3, 2, 1}}
	for _, d := range demands {
		for _, ws := range weightSets {
			idx++
			name := fmt.Sprintf("dispatch_weighted/%05d/d%.0f_w%d", idx, d, len(ws))
			t.Run(name, func(t *testing.T) {
				alloc := dispatch.WeightedDispatch([]float64{d, d * 0.8, d * 0.6}, ws)
				if len(alloc) != 3 {
					t.Fatalf("expected 3 allocations")
				}
			})
		}
	}

	// --- Workflow metrics stress (3*4 = 12 subtests) ---
	stepCounts := []int{1, 3, 5, 10}
	for _, r := range regions {
		for _, sc := range stepCounts {
			idx++
			name := fmt.Sprintf("workflow/%05d/%s_s%d", idx, r, sc)
			t.Run(name, func(t *testing.T) {
				steps := make([]workflow.WorkflowStep, sc)
				for i := range steps {
					steps[i] = workflow.WorkflowStep{Name: fmt.Sprintf("step_%d", i)}
				}
				metrics := workflow.WorkflowMetrics(steps)
				if metrics["total_steps"] != sc {
					t.Fatalf("expected %d total steps", sc)
				}
				trail := workflow.AuditTrail(steps)
				if len(trail) != sc {
					t.Fatalf("expected %d trail entries", sc)
				}
			})
		}
	}

	// --- Events window stress (3*3*4 = 36 subtests) ---
	minSeqs := []int64{0, 10, 50}
	maxSeqs := []int64{20, 50, 100}
	regionSets := []string{"west", "east", "central", "south"}
	for _, minS := range minSeqs {
		for _, maxS := range maxSeqs {
			for _, rs := range regionSets {
				idx++
				name := fmt.Sprintf("events_window/%05d/%s_min%d_max%d", idx, rs, minS, maxS)
				t.Run(name, func(t *testing.T) {
					evts := []events.Event{
						{ID: "e1", Sequence: 5, Region: rs, Type: "dispatch"},
						{ID: "e2", Sequence: 15, Region: rs, Type: "outage"},
						{ID: "e3", Sequence: 25, Region: "other", Type: "dispatch"},
						{ID: "e4", Sequence: 55, Region: rs, Type: "demand"},
						{ID: "e5", Sequence: 75, Region: rs, Type: "dispatch"},
					}
					window := events.WindowEvents(evts, minS, maxS)
					_ = window
					filtered := events.FilterByRegion(evts, rs)
					_ = filtered
					deduped := events.DeduplicateEvents(evts)
					_ = deduped
				})
			}
		}
	}

	// --- Consensus quorum stress (5*5 = 25 subtests) ---
	voteCounts := []int{1, 3, 5, 7, 9}
	totalNodes := []int{3, 5, 7, 9, 11}
	for _, vc := range voteCounts {
		for _, tn := range totalNodes {
			idx++
			name := fmt.Sprintf("consensus_quorum/%05d/v%d_n%d", idx, vc, tn)
			t.Run(name, func(t *testing.T) {
				_ = consensus.HasQuorum(vc, tn)
				_ = consensus.MajorityVote(vc, tn)
				_ = consensus.IncrementTerm(int64(vc))
				_ = consensus.IsTermValid(int64(vc))
			})
		}
	}

	// --- Config resolution stress (4*5 = 20 subtests) ---
	configServices := []string{"nats", "postgres", "redis", "influx"}
	retryValues := []int{1, 3, 5, 7, 10}
	for _, svc := range configServices {
		for _, rv := range retryValues {
			idx++
			name := fmt.Sprintf("config_ext/%05d/%s_r%d", idx, svc, rv)
			t.Run(name, func(t *testing.T) {
				c := config.DefaultConfig()
				c.RetryMax = rv
				ep := config.ResolveEndpoint(svc, c)
				if ep == "" {
					t.Fatalf("expected endpoint for %s", svc)
				}
				bo := config.MaxRetryBackoff(c)
				if bo <= 0 {
					t.Fatalf("expected positive backoff")
				}
			})
		}
	}

	t.Logf("Total stress subtests launched: %d", idx)
}
