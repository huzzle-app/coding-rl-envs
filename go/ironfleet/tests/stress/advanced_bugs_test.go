package stress

import (
	"fmt"
	"ironfleet/internal/allocator"
	"ironfleet/internal/policy"
	"ironfleet/internal/queue"
	"ironfleet/internal/resilience"
	"ironfleet/internal/routing"
	"ironfleet/internal/security"
	"ironfleet/internal/statistics"
	"ironfleet/internal/workflow"
	"ironfleet/pkg/models"
	"ironfleet/services/notifications"
	svcrouting "ironfleet/services/routing"
	svcsecurity "ironfleet/services/security"
	"ironfleet/shared/contracts"
	"math"
	"strings"
	"sync"
	"testing"
	"time"
)

const advancedCases = 245

func TestAdvancedBugMatrix(t *testing.T) {
	for i := 0; i < advancedCases; i++ {
		i := i
		t.Run(fmt.Sprintf("case_%05d", i), func(t *testing.T) {
			bucket := i % 7
			sub := i / 7

			switch bucket {
			case 0:
				testLatentBugs(t, sub, i)
			case 1:
				testDomainLogicBugs(t, sub, i)
			case 2:
				testMultiStepBugs(t, sub, i)
			case 3:
				testStateMachineBugs(t, sub, i)
			case 4:
				testConcurrencyBugs(t, sub, i)
			case 5:
				testConcurrencyBugsExtended(t, sub, i)
			case 6:
				testIntegrationBugs(t, sub, i)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// 1. LATENT BUGS — corrupt state silently, failures manifest elsewhere
// ---------------------------------------------------------------------------

func testLatentBugs(t *testing.T, sub, i int) {
	switch sub % 5 {
	case 0:
		// Flush backing-array aliasing: Flush should return a stable snapshot.
		// After Flush, new Submits must not overwrite the flushed results.
		sched := allocator.NewRollingWindowScheduler(10)
		sched.Submit(allocator.Order{ID: "alpha", Urgency: 5, ETA: "08:00"})
		sched.Submit(allocator.Order{ID: "bravo", Urgency: 3, ETA: "09:00"})
		flushed := sched.Flush()
		if len(flushed) != 2 {
			t.Fatalf("expected 2 flushed, got %d", len(flushed))
		}
		// Submit new orders into the scheduler after flush
		sched.Submit(allocator.Order{ID: "charlie", Urgency: 9, ETA: "07:00"})
		sched.Submit(allocator.Order{ID: "delta", Urgency: 1, ETA: "10:00"})
		// The flushed result must still contain the original orders
		if flushed[0].ID != "alpha" || flushed[1].ID != "bravo" {
			t.Fatalf("flushed results corrupted after new submits: %+v", flushed)
		}

	case 1:
		// AllocateCosts with equal shares should distribute equally.
		// Three parties splitting 900.0 evenly should each get 300.0.
		shares := []float64{1.0, 1.0, 1.0}
		result := allocator.AllocateCosts(900.0, shares)
		if len(result) != 3 {
			t.Fatalf("expected 3 allocations, got %d", len(result))
		}
		for idx, v := range result {
			if math.Abs(v-300.0) > 0.01 {
				t.Fatalf("share %d: expected 300.0, got %.4f", idx, v)
			}
		}

	case 2:
		// AllocateCosts with proportional shares should sum to total.
		shares := []float64{2.0, 3.0, 5.0}
		total := 1000.0
		result := allocator.AllocateCosts(total, shares)
		sum := 0.0
		for _, v := range result {
			sum += v
		}
		if math.Abs(sum-total) > 0.01 {
			t.Fatalf("allocated costs sum %.4f != total %.4f", sum, total)
		}

	case 3:
		// ResponseTimeTracker should evict OLDEST samples when window is full.
		// With window=3, after recording [10, 20, 30, 40], the tracker should
		// contain [20, 30, 40] and the average should be 30.0.
		tracker := statistics.NewResponseTimeTracker(3)
		tracker.Record(10)
		tracker.Record(20)
		tracker.Record(30)
		tracker.Record(40) // should evict 10 (oldest)
		avg := tracker.Average()
		if math.Abs(avg-30.0) > 0.01 {
			t.Fatalf("expected average 30.0 after evicting oldest, got %.2f", avg)
		}

	case 4:
		// CompareByUrgencyThenETA: same urgency orders should sort by ETA
		// ascending (earliest first). ETA "08:00" should come before "12:00".
		early := allocator.Order{ID: "A", Urgency: 5, ETA: "08:00"}
		late := allocator.Order{ID: "B", Urgency: 5, ETA: "12:00"}
		cmp := allocator.CompareByUrgencyThenETA(early, late)
		if cmp >= 0 {
			t.Fatalf("same urgency, earlier ETA should sort first (negative), got %d", cmp)
		}
	}
}

// ---------------------------------------------------------------------------
// 2. DOMAIN LOGIC BUGS — require understanding of fleet/convoy operations
// ---------------------------------------------------------------------------

func testDomainLogicBugs(t *testing.T, sub, i int) {
	switch sub % 5 {
	case 0:
		// ChannelScore: higher priority channels should have LOWER scores
		// (lower score = better route). Priority 9 should beat priority 1.
		scoreLow := routing.ChannelScore(10, 0.9, 1)
		scoreHigh := routing.ChannelScore(10, 0.9, 9)
		if scoreHigh >= scoreLow {
			t.Fatalf("high priority (9) should have lower score than low priority (1): high=%.2f low=%.2f", scoreHigh, scoreLow)
		}

	case 1:
		// EstimateTurnaround: 150 tons at 200 tons/hr should take 1.25 hours
		// (0.75 base + 0.5 setup). Fractional hours must be preserved exactly.
		result := allocator.EstimateTurnaround(150, 200)
		if math.Abs(result-1.25) > 0.001 {
			t.Fatalf("expected turnaround 1.25 hr (0.75 base + 0.5 setup), got %f", result)
		}

	case 2:
		// EstimateTransitTime: nautical conversion preserves fractional hours.
		// 500km at 100 knots = 500 / (100 * 1.852) = 2.6998 hours.
		result := routing.EstimateTransitTime(500, 100)
		expected := 500.0 / (100.0 * 1.852)
		if math.Abs(result-expected) > 0.01 {
			t.Fatalf("expected %.4f hours, got %f (fractional hours lost)", expected, result)
		}

	case 3:
		// UrgencyScore: short SLA (high urgency) should produce HIGHER score
		// than long SLA. SLA 30 min should outscore SLA 200 min.
		urgent := models.DispatchOrder{ID: "critical", Severity: 5, SLAMinutes: 30}
		routine := models.DispatchOrder{ID: "routine", Severity: 5, SLAMinutes: 200}
		if urgent.UrgencyScore() <= routine.UrgencyScore() {
			t.Fatalf("short SLA should have higher urgency: urgent=%d routine=%d",
				urgent.UrgencyScore(), routine.UrgencyScore())
		}

	case 4:
		// HasConflict: abutting time slots should NOT conflict. If berth is
		// occupied 08:00-10:00, a new slot 10:00-12:00 should be allowed —
		// one ship departs before the next arrives.
		slots := []allocator.BerthSlot{
			{BerthID: "B1", StartHour: 8, EndHour: 10, Occupied: true},
		}
		if allocator.HasConflict(slots, 10, 12) {
			t.Fatal("abutting slots should not conflict (ship departs before next arrives)")
		}
	}
}

// ---------------------------------------------------------------------------
// 3. MULTI-STEP BUGS — fixing one reveals another
// ---------------------------------------------------------------------------

func testMultiStepBugs(t *testing.T, sub, i int) {
	switch sub % 5 {
	case 0:
		// Chain: IsTerminalState wrongly includes "departed", AND ActiveCount
		// uses IsTerminalState. Departed vessels are still at sea — not terminal.
		if workflow.IsTerminalState("departed") {
			t.Fatal("departed should not be terminal (vessel still at sea)")
		}

	case 1:
		// Chain: Even if IsTerminalState is fixed, ActiveCount uses it internally
		// so departed entities get miscounted. This test catches ActiveCount.
		we := workflow.NewWorkflowEngine()
		we.Register("convoy-1", "queued")
		we.Transition("convoy-1", "allocated")
		we.Transition("convoy-1", "departed")
		active := we.ActiveCount()
		if active != 1 {
			t.Fatalf("departed convoy should be active (at sea), got count %d", active)
		}

	case 2:
		// Chain: Deduplicate uses only event ID, dropping different sequences
		// of the same event source. When Replay is fixed, it depends on
		// Deduplicate preserving all sequence variants.
		events := []resilience.Event{
			{ID: "sensor-A", Sequence: 1},
			{ID: "sensor-A", Sequence: 2},
			{ID: "sensor-A", Sequence: 3},
		}
		deduped := resilience.Deduplicate(events)
		if len(deduped) != 3 {
			t.Fatalf("expected 3 events (same sensor, different sequences), got %d", len(deduped))
		}

	case 3:
		// Chain: WorkflowEngine.Register silently ignores re-registration.
		// After cancelling an order, re-registering it should reset to queued.
		we := workflow.NewWorkflowEngine()
		we.Register("order-X", "queued")
		we.Transition("order-X", "cancelled")
		// Re-register the cancelled order — should reset it to queued
		err := we.Register("order-X", "queued")
		if err != nil {
			t.Fatalf("re-registration should succeed: %v", err)
		}
		state := we.GetState("order-X")
		if state != "queued" {
			t.Fatalf("re-registered order should be queued, got %s", state)
		}

	case 4:
		// Chain: ShouldCheckpoint uses absolute sequence, not delta from last.
		// After checkpointing at 5000, 500 more events should NOT trigger again.
		cm := resilience.NewCheckpointManager()
		cm.Record("ingestion-stream", 5000)
		if cm.ShouldCheckpoint(5500) {
			t.Fatal("500 events since last checkpoint should not trigger (delta-based, threshold 1000)")
		}
	}
}

// ---------------------------------------------------------------------------
// 4. STATE MACHINE BUGS — incorrect transitions, recovery failures
// ---------------------------------------------------------------------------

func testStateMachineBugs(t *testing.T, sub, i int) {
	switch sub % 5 {
	case 0:
		// CircuitBreaker: in half-open state, 3 consecutive successes should
		// close the breaker (standard half-open recovery protocol).
		cb := resilience.NewCircuitBreaker(3, 1) // threshold=3, instant recovery
		cb.RecordFailure()
		cb.RecordFailure()
		cb.RecordFailure() // trips to Open
		time.Sleep(5 * time.Millisecond)
		_ = cb.State() // should transition to HalfOpen
		cb.RecordSuccess()
		cb.RecordSuccess()
		cb.RecordSuccess() // 3 successes should close
		state := cb.State()
		if state != "closed" {
			t.Fatalf("3 successes in half-open should close breaker, got %s", state)
		}

	case 1:
		// CircuitBreaker: failure in half-open should re-open and block
		// requests for the full recovery period (lastFailureAt must update).
		cb := resilience.NewCircuitBreaker(2, 50)
		cb.RecordFailure()
		cb.RecordFailure() // trips to Open
		time.Sleep(60 * time.Millisecond)
		_ = cb.State() // HalfOpen
		cb.RecordFailure() // should re-open WITH updated timestamp
		// Immediately after, should still be Open (not HalfOpen again)
		state := cb.State()
		if state != "open" {
			t.Fatalf("failure in half-open should re-open, got %s", state)
		}

	case 2:
		// CircuitBreaker: successes in closed state should reduce failure count
		// to prevent premature tripping.
		cb := resilience.NewCircuitBreaker(5, 30000)
		cb.RecordFailure()
		cb.RecordFailure()
		cb.RecordFailure()
		cb.RecordSuccess() // should reduce failures to 2
		cb.RecordSuccess() // should reduce failures to 1
		_, failures, _ := cb.Snapshot()
		if failures != 1 {
			t.Fatalf("expected 1 failure after 3 failures and 2 successes, got %d", failures)
		}

	case 3:
		// ShouldDeescalate: "restricted" policy with threshold=1 should
		// de-escalate after 2 successes (threshold * 2 = 1*2 = 2).
		if !policy.ShouldDeescalate("restricted", 2) {
			t.Fatal("restricted policy should de-escalate after 2 successes (threshold 1*2=2)")
		}

	case 4:
		// Drain(0) should drain ALL items (requesting 0 means "give me everything")
		pq := queue.NewPriorityQueue()
		pq.Enqueue(queue.Item{ID: "a", Priority: 1})
		pq.Enqueue(queue.Item{ID: "b", Priority: 2})
		pq.Enqueue(queue.Item{ID: "c", Priority: 3})
		drained := pq.Drain(0)
		if len(drained) != 3 {
			t.Fatalf("Drain(0) should drain all, got %d", len(drained))
		}
	}
}

// ---------------------------------------------------------------------------
// 5. CONCURRENCY BUGS — data races, lock gaps, TOCTOU
// ---------------------------------------------------------------------------

func testConcurrencyBugs(t *testing.T, sub, i int) {
	switch sub % 5 {
	case 0:
		// PeekAll reads scheduled slice without lock. Concurrent Submit
		// and PeekAll creates a data race on the slice header/backing array.
		sched := allocator.NewRollingWindowScheduler(100)
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				sched.Submit(allocator.Order{ID: fmt.Sprintf("order-%d", j), Urgency: j})
			}
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				_ = sched.PeekAll()
			}
		}()
		wg.Wait()
		count := sched.Count()
		if count != 50 {
			t.Fatalf("expected 50 orders, got %d", count)
		}

	case 1:
		// CircuitBreaker.Snapshot reads state/failures/successCount without
		// holding the lock. Concurrent RecordFailure exposes a data race.
		cb := resilience.NewCircuitBreaker(10, 30000)
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				cb.RecordFailure()
			}
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				_, _, _ = cb.Snapshot()
			}
		}()
		wg.Wait()

	case 2:
		// RegisterAndTransition has a lock gap between Register and Transition.
		// Concurrent calls for different entities should work, but the gap means
		// a concurrent Register with the SAME entity ID could overwrite state.
		we := workflow.NewWorkflowEngine()
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			for j := 0; j < 20; j++ {
				we.RegisterAndTransition(fmt.Sprintf("entity-a-%d", j), "queued", "allocated")
			}
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 20; j++ {
				we.RegisterAndTransition(fmt.Sprintf("entity-b-%d", j), "queued", "allocated")
			}
		}()
		wg.Wait()

	case 3:
		// SubmitBatch releases lock between items, allowing interleaving with Flush.
		// Items can be lost if Flush happens mid-batch.
		sched := allocator.NewRollingWindowScheduler(20)
		var wg sync.WaitGroup
		totalFlushed := 0
		var mu sync.Mutex
		wg.Add(2)
		go func() {
			defer wg.Done()
			sched.SubmitBatch([]allocator.Order{
				{ID: "a1", Urgency: 1}, {ID: "a2", Urgency: 2},
				{ID: "a3", Urgency: 3}, {ID: "a4", Urgency: 4},
				{ID: "a5", Urgency: 5}, {ID: "a6", Urgency: 6},
			})
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 3; j++ {
				flushed := sched.Flush()
				mu.Lock()
				totalFlushed += len(flushed)
				mu.Unlock()
				time.Sleep(time.Millisecond)
			}
		}()
		wg.Wait()
		remaining := sched.Count()
		total := totalFlushed + remaining
		if total != 6 {
			t.Fatalf("expected 6 total items (flushed+remaining), got %d", total)
		}

	case 4:
		// Concurrent CheckpointManager Record + ShouldCheckpoint reads.
		cm := resilience.NewCheckpointManager()
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				cm.Record(fmt.Sprintf("stream-%d", j%5), j*10)
			}
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				_ = cm.ShouldCheckpoint(j * 10)
			}
		}()
		wg.Wait()
	}
}

func testConcurrencyBugsExtended(t *testing.T, sub, i int) {
	switch sub % 5 {
	case 0:
		// Concurrent Flush + Submit: flushed results should not be corrupted
		// by subsequent Submits (tests backing array aliasing under concurrency).
		sched := allocator.NewRollingWindowScheduler(50)
		for j := 0; j < 10; j++ {
			sched.Submit(allocator.Order{ID: fmt.Sprintf("init-%d", j), Urgency: j})
		}
		flushed := sched.Flush()
		if len(flushed) != 10 {
			t.Fatalf("expected 10 flushed, got %d", len(flushed))
		}
		// Submit new orders concurrently
		var wg sync.WaitGroup
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 10; j++ {
				sched.Submit(allocator.Order{ID: fmt.Sprintf("new-%d", j), Urgency: j + 100})
			}
		}()
		wg.Wait()
		// Verify flushed results are still intact
		for idx, o := range flushed {
			expected := fmt.Sprintf("init-%d", idx)
			if o.ID != expected {
				t.Fatalf("flushed[%d] corrupted: expected %s, got %s", idx, expected, o.ID)
			}
		}

	case 1:
		// Concurrent RouteTable Add + All operations
		rt := routing.NewRouteTable()
		var wg sync.WaitGroup
		wg.Add(3)
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				rt.Add(routing.Route{Channel: fmt.Sprintf("ch-%d", j), Latency: j})
			}
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				_ = rt.All()
			}
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				_ = rt.Count()
			}
		}()
		wg.Wait()
		if rt.Count() != 50 {
			t.Fatalf("expected 50 routes, got %d", rt.Count())
		}

	case 2:
		// Concurrent PolicyEngine escalate/de-escalate
		pe := policy.NewPolicyEngine("normal")
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			for j := 0; j < 20; j++ {
				pe.Escalate(3, "test")
			}
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 20; j++ {
				pe.Deescalate("recovery")
			}
		}()
		wg.Wait()
		current := pe.Current()
		if current == "" {
			t.Fatal("policy state should never be empty")
		}

	case 3:
		// Concurrent PriorityQueue Enqueue/Dequeue
		pq := queue.NewPriorityQueue()
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				pq.Enqueue(queue.Item{ID: fmt.Sprintf("item-%d", j), Priority: j})
			}
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				_ = pq.Dequeue()
			}
		}()
		wg.Wait()

	case 4:
		// Concurrent TokenStore Store/Validate
		ts := security.NewTokenStore()
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				ts.Store(security.Token{
					Value:     fmt.Sprintf("tok-%d", j),
					Subject:   "test",
					ExpiresAt: time.Now().Add(time.Hour),
				})
			}
		}()
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				_ = ts.Validate(fmt.Sprintf("tok-%d", j))
			}
		}()
		wg.Wait()
	}
}

// ---------------------------------------------------------------------------
// 6. INTEGRATION BUGS — cross-module interaction failures
// ---------------------------------------------------------------------------

func testIntegrationBugs(t *testing.T, sub, i int) {
	switch sub % 5 {
	case 0:
		// GetServiceURL should return base URL (host:port) without health path.
		// Callers append their own paths; embedding /health corrupts routing.
		url := contracts.GetServiceURL("gateway", "10.0.0.1")
		expected := "http://10.0.0.1:8130"
		if url != expected {
			t.Fatalf("service URL should be base only, expected %q got %q", expected, url)
		}

	case 1:
		// PlanMultiLeg: totalDelay should only include ACTIVE legs, not blocked ones.
		// Blocked routes are removed from the path, so their latency shouldn't count.
		routes := []routing.Route{
			{Channel: "north", Latency: 10},
			{Channel: "south", Latency: 20},
			{Channel: "east", Latency: 30},
		}
		blocked := map[string]bool{"south": true}
		plan := routing.PlanMultiLeg(routes, blocked)
		if len(plan.Legs) != 2 {
			t.Fatalf("expected 2 legs (south blocked), got %d", len(plan.Legs))
		}
		expectedDelay := 10 + 30 // north + east only
		if plan.TotalDelay != expectedDelay {
			t.Fatalf("totalDelay should be %d (active legs only), got %d", expectedDelay, plan.TotalDelay)
		}

	case 2:
		// SanitisePath should block embedded path traversal.
		// "uploads/../../../etc/passwd" normalizes to "../../etc/passwd" — must be caught.
		result := security.SanitisePath("uploads/../../../etc/passwd")
		if strings.Contains(result, "..") {
			t.Fatalf("embedded path traversal should be blocked, got %q", result)
		}

	case 3:
		// IsAllowedOrigin must use exact matching, not prefix matching.
		// "https://fleet.mil.evil.com" must NOT match "https://fleet.mil".
		allowlist := []string{"https://fleet.mil"}
		if security.IsAllowedOrigin("https://fleet.mil.evil.com", allowlist) {
			t.Fatal("prefix matching allows origin spoofing via subdomain extension")
		}

	case 4:
		// TotalDistance should return sum of all leg distances, not the max.
		legs := []svcrouting.Leg{
			{From: "Port-A", To: "Port-B", Distance: 100},
			{From: "Port-B", To: "Port-C", Distance: 200},
			{From: "Port-C", To: "Port-D", Distance: 300},
		}
		total := svcrouting.TotalDistance(legs)
		if total != 600 {
			t.Fatalf("expected total distance 600 (sum), got %f", total)
		}
	}
}

// ---------------------------------------------------------------------------
// Targeted standalone tests for specific complex scenarios
// ---------------------------------------------------------------------------

func TestFlushThenSubmitDoesNotCorruptSnapshot(t *testing.T) {
	sched := allocator.NewRollingWindowScheduler(5)
	sched.Submit(allocator.Order{ID: "first", Urgency: 1})
	sched.Submit(allocator.Order{ID: "second", Urgency: 2})
	flushed := sched.Flush()
	// New submits should not corrupt flushed slice
	for i := 0; i < 5; i++ {
		sched.Submit(allocator.Order{ID: fmt.Sprintf("new-%d", i), Urgency: i + 10})
	}
	if flushed[0].ID != "first" || flushed[1].ID != "second" {
		t.Fatalf("flushed snapshot corrupted: %+v", flushed)
	}
}

func TestAllocateCostsEqualSharesPrecision(t *testing.T) {
	result := allocator.AllocateCosts(1000.0, []float64{1, 1, 1, 1})
	for i, v := range result {
		if math.Abs(v-250.0) > 0.01 {
			t.Fatalf("share %d: expected 250.0, got %.6f", i, v)
		}
	}
}

func TestAllocateCostsSumsToTotal(t *testing.T) {
	total := 777.77
	result := allocator.AllocateCosts(total, []float64{1, 2, 3, 4, 5})
	sum := 0.0
	for _, v := range result {
		sum += v
	}
	if math.Abs(sum-total) > 0.01 {
		t.Fatalf("cost allocation sum %.6f diverges from total %.2f", sum, total)
	}
}

func TestResponseTimeTrackerEvictsOldest(t *testing.T) {
	tracker := statistics.NewResponseTimeTracker(2)
	tracker.Record(100)
	tracker.Record(200)
	tracker.Record(300) // should evict 100
	p50 := tracker.P50()
	if p50 < 200 {
		t.Fatalf("after evicting oldest (100), P50 should be >= 200, got %.2f", p50)
	}
}

func TestChannelScorePriorityInversion(t *testing.T) {
	// Same latency/reliability, different priorities.
	// Priority 9 (critical) should produce lower score than priority 1.
	s1 := routing.ChannelScore(50, 0.8, 1)
	s9 := routing.ChannelScore(50, 0.8, 9)
	if s9 >= s1 {
		t.Fatalf("critical priority (9) score %.2f should be lower than low priority (1) score %.2f", s9, s1)
	}
}

func TestBerthSlotAbuttingShouldNotConflict(t *testing.T) {
	slots := []allocator.BerthSlot{
		{BerthID: "B1", StartHour: 6, EndHour: 10, Occupied: true},
		{BerthID: "B2", StartHour: 14, EndHour: 18, Occupied: true},
	}
	// Abutting: new slot starts exactly when B1 ends
	if allocator.HasConflict(slots, 10, 14) {
		t.Fatal("slot [10,14) abutting [6,10) and [14,18) should not conflict")
	}
}

func TestUrgencyScoreShortSLAHighPriority(t *testing.T) {
	// Short SLA (30 min) should have HIGH urgency from time pressure.
	// Correct: (5*8) + (120-30) = 40 + 90 = 130
	order := models.DispatchOrder{ID: "urgent", Severity: 5, SLAMinutes: 30}
	score := order.UrgencyScore()
	expected := (5 * 8) + (120 - 30) // = 130
	if score != expected {
		t.Fatalf("expected urgency %d for short SLA, got %d", expected, score)
	}
}

func TestUrgencyScoreLongSLAClamped(t *testing.T) {
	// Long SLA (600 min) — time pressure should be zero (clamped to 0).
	// Correct: (1*8) + max(120-600, 0) = 8 + 0 = 8
	order := models.DispatchOrder{ID: "routine", Severity: 1, SLAMinutes: 600}
	score := order.UrgencyScore()
	if score != 8 {
		t.Fatalf("expected urgency 8 for long SLA (remainder clamped), got %d", score)
	}
}

func TestCircuitBreakerHalfOpenRecoveryProtocol(t *testing.T) {
	// Standard protocol: 3 successes in half-open should close the breaker.
	// The recovery threshold should be independent of the failure threshold.
	cb := resilience.NewCircuitBreaker(5, 1) // 5 failures to trip, 1ms recovery
	for i := 0; i < 5; i++ {
		cb.RecordFailure()
	}
	time.Sleep(5 * time.Millisecond)
	state := cb.State()
	if state != "half_open" {
		t.Fatalf("expected half_open, got %s", state)
	}
	cb.RecordSuccess()
	cb.RecordSuccess()
	cb.RecordSuccess()
	state = cb.State()
	if state != "closed" {
		t.Fatalf("3 successes should close the breaker regardless of failure threshold, got %s", state)
	}
}

func TestCircuitBreakerReOpenUpdatesTimestamp(t *testing.T) {
	cb := resilience.NewCircuitBreaker(2, 30)
	cb.RecordFailure()
	cb.RecordFailure() // trips to Open
	time.Sleep(40 * time.Millisecond)
	_ = cb.State() // transitions to HalfOpen
	cb.RecordFailure() // should re-open with FRESH timestamp
	// Should still be Open immediately after (not instantly back to HalfOpen)
	if cb.IsAllowed() {
		t.Fatal("breaker should block after re-opening from half-open failure")
	}
}

func TestWorkflowReRegisterResetsState(t *testing.T) {
	we := workflow.NewWorkflowEngine()
	we.Register("ship-1", "queued")
	we.Transition("ship-1", "cancelled")
	// Re-register should reset the entity
	we.Register("ship-1", "queued")
	state := we.GetState("ship-1")
	if state != "queued" {
		t.Fatalf("re-registered entity should be in queued state, got %s", state)
	}
}

func TestPlanMultiLegExcludesBlockedDelay(t *testing.T) {
	routes := []routing.Route{
		{Channel: "alpha", Latency: 5},
		{Channel: "beta", Latency: 100}, // blocked
		{Channel: "gamma", Latency: 15},
	}
	plan := routing.PlanMultiLeg(routes, map[string]bool{"beta": true})
	expected := 5 + 15
	if plan.TotalDelay != expected {
		t.Fatalf("totalDelay %d includes blocked route latency, expected %d", plan.TotalDelay, expected)
	}
}

func TestClassifySeverityEmbeddedKeyword(t *testing.T) {
	// Keyword "critical" appears mid-description, not at start.
	sev := models.ClassifySeverity("system failure: critical")
	if sev != models.SeverityCritical {
		t.Fatalf("expected severity %d (critical) for embedded keyword, got %d", models.SeverityCritical, sev)
	}
}

func TestClassifySeverityEmergencyEmbedded(t *testing.T) {
	sev := models.ClassifySeverity("report: emergency power outage")
	if sev != models.SeverityCritical {
		t.Fatalf("expected severity %d (critical) for embedded emergency, got %d", models.SeverityCritical, sev)
	}
}

func TestDeduplicatePreservesSequences(t *testing.T) {
	events := []resilience.Event{
		{ID: "x", Sequence: 1},
		{ID: "x", Sequence: 2},
		{ID: "y", Sequence: 1},
	}
	result := resilience.Deduplicate(events)
	if len(result) != 3 {
		t.Fatalf("expected 3 unique events (2 x sequences + 1 y), got %d", len(result))
	}
}

func TestShouldCheckpointDeltaBased(t *testing.T) {
	// After checkpointing at seq 5000, need 1000 MORE events to trigger.
	cm := resilience.NewCheckpointManager()
	cm.Record("s1", 5000)
	if cm.ShouldCheckpoint(5500) {
		t.Fatal("500 events since checkpoint should not trigger (threshold 1000)")
	}
	if !cm.ShouldCheckpoint(6000) {
		t.Fatal("1000 events since checkpoint should trigger")
	}
}

func TestShouldDeescalateUsesCurrentThreshold(t *testing.T) {
	// "restricted" has threshold=1, de-escalation requires 1*2=2 successes.
	if !policy.ShouldDeescalate("restricted", 2) {
		t.Fatal("restricted should de-escalate after 2 successes (own threshold 1*2=2)")
	}
	// "watch" has threshold=2, de-escalation requires 2*2=4 successes.
	if !policy.ShouldDeescalate("watch", 4) {
		t.Fatal("watch should de-escalate after 4 successes (own threshold 2*2=4)")
	}
}

func TestVarianceSampleCorrection(t *testing.T) {
	values := []float64{2, 4, 4, 4, 5, 5, 7, 9}
	v := statistics.Variance(values)
	expected := 4.571428571428571 // sum_sq=32 / (8-1) = 4.571
	if math.Abs(v-expected) > 0.01 {
		t.Fatalf("expected sample variance %.4f (Bessel-corrected), got %.4f", expected, v)
	}
}

func TestMedianEvenLength(t *testing.T) {
	med := statistics.Median([]float64{10, 20, 30, 40})
	if math.Abs(med-25.0) > 0.001 {
		t.Fatalf("median of [10,20,30,40] should be 25.0, got %f", med)
	}
}

func TestEstimateRouteCostDelaySurcharge(t *testing.T) {
	// latency 10, fuel 2.0, distance 100 → base=200, surcharge=10*0.5=5, total=205
	// Surcharge should be based on latency (time), not distance.
	cost := routing.EstimateRouteCost(10, 2.0, 100)
	if math.Abs(cost-205.0) > 0.01 {
		t.Fatalf("expected cost 205.0 (base 200 + latency surcharge 5), got %f", cost)
	}
}

func TestEstimateTurnaroundFractionalHours(t *testing.T) {
	// 150 tons at 200 tons/hr = 0.75 hours base + 0.5 setup = 1.25
	// Must preserve fractional hours, not round up.
	result := allocator.EstimateTurnaround(150, 200)
	if math.Abs(result-1.25) > 0.001 {
		t.Fatalf("expected 1.25 hr (0.75 base + 0.5 setup), got %f", result)
	}
}

func TestEstimateTurnaroundSetupOnly(t *testing.T) {
	// Zero cargo, just setup = 0.5 hr
	result := allocator.EstimateTurnaround(0, 100)
	if math.Abs(result-0.5) > 0.001 {
		t.Fatalf("zero-cargo turnaround should be 0.5 hr (setup only), got %f", result)
	}
}

func TestEstimateTransitTimeFractional(t *testing.T) {
	// 500km at 100 knots = 500 / (100*1.852) = 2.6998 hours
	// Must preserve fractional result, not truncate.
	result := routing.EstimateTransitTime(500, 100)
	expected := 500.0 / (100.0 * 1.852)
	if math.Abs(result-expected) > 0.01 {
		t.Fatalf("expected %.4f hours (fractional), got %.4f", expected, result)
	}
}

func TestCompareByUrgencyETATiebreaker(t *testing.T) {
	// Same urgency: earlier ETA should sort first (negative return).
	early := allocator.Order{ID: "A", Urgency: 5, ETA: "08:00"}
	late := allocator.Order{ID: "B", Urgency: 5, ETA: "12:00"}
	cmp := allocator.CompareByUrgencyThenETA(early, late)
	if cmp >= 0 {
		t.Fatalf("same urgency, earlier ETA should sort first (negative), got %d", cmp)
	}
}

func TestSanitisePathEmbeddedTraversal(t *testing.T) {
	// Path that doesn't start with ".." but resolves to traversal after Clean.
	paths := []string{
		"uploads/../../../etc/passwd",
		"data/logs/../../../../root/.ssh/id_rsa",
	}
	for _, p := range paths {
		result := security.SanitisePath(p)
		if strings.Contains(result, "..") {
			t.Fatalf("SanitisePath(%q) should block embedded traversal, got %q", p, result)
		}
	}
}

func TestOriginAllowlistExactMatch(t *testing.T) {
	allowlist := []string{"https://fleet.mil", "https://ops.navy.mil"}
	// Subdomain/suffix attacks must be rejected
	spoofed := []string{
		"https://fleet.mil.evil.com",
		"https://fleet.mil/evil",
		"https://ops.navy.mil.attacker.com",
	}
	for _, origin := range spoofed {
		if security.IsAllowedOrigin(origin, allowlist) {
			t.Fatalf("origin %q should NOT match via prefix — enables spoofing", origin)
		}
	}
}

func TestServiceURLNoHealthPath(t *testing.T) {
	// URL should be just host:port, not host:port/health
	for _, svc := range []string{"gateway", "routing", "policy", "resilience"} {
		url := contracts.GetServiceURL(svc, "10.0.0.1")
		if strings.Contains(url, "/health") {
			t.Fatalf("service %s URL should not include health path, got %s", svc, url)
		}
	}
}

func TestFormatNotificationFullOperation(t *testing.T) {
	// Operation names longer than 4 chars must not be truncated.
	msg := notifications.FormatNotification("deploy", 3, "new version")
	if !strings.Contains(msg, "[DEPLOY]") {
		t.Fatalf("operation should be full uppercase without truncation, got %s", msg)
	}
}

func TestShouldThrottleHighSeverityNotPenalized(t *testing.T) {
	// High severity (5) should NOT be throttled more aggressively.
	// count=3, max=10 → not at max, so no throttle regardless of severity.
	if notifications.ShouldThrottle(3, 10, 5) {
		t.Fatal("high severity messages should not be throttled below max limit")
	}
}

func TestTotalDistanceIsSum(t *testing.T) {
	legs := []svcrouting.Leg{
		{From: "A", To: "B", Distance: 100},
		{From: "B", To: "C", Distance: 200},
		{From: "C", To: "D", Distance: 300},
	}
	total := svcrouting.TotalDistance(legs)
	if total != 600 {
		t.Fatalf("total should be sum of all legs (600), got %f", total)
	}
}

func TestSecurityRateLimitSimpleUnderLimit(t *testing.T) {
	// 8 requests, limit 10, 30-second window.
	// 8 < 10, clearly under limit — should be allowed regardless of window.
	if !svcsecurity.RateLimitCheck(8, 10, 30) {
		t.Fatal("8 requests under limit of 10 should be allowed")
	}
}

func TestSecurityRateLimitAtBoundary(t *testing.T) {
	if svcsecurity.RateLimitCheck(10, 10, 60) {
		t.Fatal("at exactly the limit should be blocked")
	}
}
