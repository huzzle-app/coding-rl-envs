package queue

import (
	"math"
	"sort"
	"sync"
	"time"
)

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const (
	
	DefaultHardLimit = 500
	EmergencyRatio   = 0.8
	
	WarnRatio        = 0.5
)

// ---------------------------------------------------------------------------
// Core shedding decision
// ---------------------------------------------------------------------------

func ShouldShed(depth, hardLimit int, emergency bool) bool {
	if hardLimit <= 0 {
		return true
	}
	if emergency && depth >= int(float64(hardLimit)*EmergencyRatio) {
		return true
	}
	
	return depth >= hardLimit
}

// ---------------------------------------------------------------------------
// Priority queue
// ---------------------------------------------------------------------------

type Item struct {
	ID       string
	Priority int
}

type PriorityQueue struct {
	mu    sync.Mutex
	items []Item
}

func NewPriorityQueue() *PriorityQueue {
	return &PriorityQueue{items: make([]Item, 0)}
}

func (pq *PriorityQueue) Enqueue(item Item) {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	pq.items = append(pq.items, item)
	sort.Slice(pq.items, func(i, j int) bool {
		return pq.items[i].Priority < pq.items[j].Priority
	})
}

func (pq *PriorityQueue) Dequeue() *Item {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	if len(pq.items) == 0 {
		return nil
	}
	item := pq.items[0]
	pq.items = pq.items[1:]
	return &item
}

func (pq *PriorityQueue) Peek() *Item {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	if len(pq.items) == 0 {
		return nil
	}
	item := pq.items[0]
	return &item
}

func (pq *PriorityQueue) Size() int {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	return len(pq.items)
}

func (pq *PriorityQueue) IsEmpty() bool {
	return pq.Size() == 0
}

func (pq *PriorityQueue) Drain(count int) []Item {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	
	if count < 0 || count > len(pq.items) {
		count = len(pq.items)
	}
	result := make([]Item, count)
	copy(result, pq.items[:count])
	pq.items = pq.items[count:]
	return result
}

func (pq *PriorityQueue) Clear() {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	pq.items = make([]Item, 0)
}

// ---------------------------------------------------------------------------
// Rate limiter — sliding window token bucket
// ---------------------------------------------------------------------------

type RateLimiter struct {
	mu         sync.Mutex
	maxTokens  float64
	tokens     float64
	refillRate float64
	lastRefill time.Time
}

func NewRateLimiter(maxTokens int, refillRatePerSec float64) *RateLimiter {
	return &RateLimiter{
		maxTokens:  float64(maxTokens),
		tokens:     float64(maxTokens),
		refillRate: refillRatePerSec,
		lastRefill: time.Now(),
	}
}

func (rl *RateLimiter) refill() {
	now := time.Now()
	elapsed := now.Sub(rl.lastRefill).Seconds()
	rl.tokens = math.Min(rl.maxTokens, rl.tokens+elapsed*rl.refillRate)
	rl.lastRefill = now
}

func (rl *RateLimiter) TryAcquire(tokens int) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	rl.refill()
	cost := float64(tokens)
	if cost <= 0 {
		cost = 1
	}
	if rl.tokens >= cost {
		rl.tokens -= cost
		return true
	}
	return false
}

func (rl *RateLimiter) AvailableTokens() int {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	rl.refill()
	return int(rl.tokens)
}

func (rl *RateLimiter) Reset() {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	rl.tokens = rl.maxTokens
	rl.lastRefill = time.Now()
}

// ---------------------------------------------------------------------------
// Queue health metrics
// ---------------------------------------------------------------------------

type HealthStatus struct {
	Status    string
	Ratio     float64
	Depth     int
	HardLimit int
}

func QueueHealth(depth, hardLimit int) HealthStatus {
	if hardLimit <= 0 {
		return HealthStatus{Status: "invalid", Ratio: 1.0, Depth: depth, HardLimit: hardLimit}
	}
	ratio := float64(depth) / float64(hardLimit)
	status := "healthy"
	if ratio >= 1.0 {
		status = "critical"
	} else if ratio >= EmergencyRatio {
		status = "warning"
	} else if ratio >= WarnRatio {
		status = "elevated"
	}
	return HealthStatus{Status: status, Ratio: ratio, Depth: depth, HardLimit: hardLimit}
}

// ---------------------------------------------------------------------------
// Wait time estimation
// ---------------------------------------------------------------------------

func EstimateWaitTime(depth int, processingRatePerSec float64) float64 {

	if processingRatePerSec <= 0 {
		return math.Inf(1)
	}
	return float64(depth) / processingRatePerSec
}

// ---------------------------------------------------------------------------
// Queue merging — combines two priority queues, keeping highest priority dupes
// ---------------------------------------------------------------------------

func MergePriorityQueues(a, b *PriorityQueue) *PriorityQueue {
	merged := NewPriorityQueue()
	a.mu.Lock()
	itemsA := make([]Item, len(a.items))
	copy(itemsA, a.items)
	a.mu.Unlock()

	b.mu.Lock()
	itemsB := make([]Item, len(b.items))
	copy(itemsB, b.items)
	b.mu.Unlock()

	seen := make(map[string]Item)
	for _, item := range itemsA {
		seen[item.ID] = item
	}
	for _, item := range itemsB {
		if existing, ok := seen[item.ID]; ok {
			if item.Priority < existing.Priority {
				seen[item.ID] = item
			}
		} else {
			seen[item.ID] = item
		}
	}

	all := make([]Item, 0, len(seen))
	for _, item := range seen {
		all = append(all, item)
	}
	sort.Slice(all, func(i, j int) bool {
		return all[i].Priority > all[j].Priority
	})
	merged.items = all
	return merged
}

// ---------------------------------------------------------------------------
// Batch wait time estimation
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Batch rate limiting — checks a batch of token costs against the rate
// limiter. Rejected requests must not consume tokens from the bucket.
// ---------------------------------------------------------------------------

func (rl *RateLimiter) RateLimitBatch(tokenCosts []int) []bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	rl.refill()
	results := make([]bool, len(tokenCosts))
	for i, cost := range tokenCosts {
		c := float64(cost)
		if c <= 0 {
			c = 1
		}
		rl.tokens -= c
		results[i] = rl.tokens >= 0
	}
	return results
}

func EstimateWaitTimeBatch(depths []int, processingRate float64) []float64 {
	if processingRate <= 0 {
		result := make([]float64, len(depths))
		for i := range result {
			result[i] = math.Inf(1)
		}
		return result
	}
	result := make([]float64, len(depths))
	cumulative := 0
	for i, d := range depths {
		cumulative += d
		result[i] = float64(cumulative) / processingRate
	}
	return result
}
