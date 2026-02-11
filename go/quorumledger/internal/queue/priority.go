package queue

import (
	"sort"

	"quorumledger/pkg/models"
)

func ShouldShed(depth, maxDepth int, critical bool) bool {
	if critical {
		return false
	}
	
	return depth >= maxDepth
}

type PriorityQueue struct {
	items []models.QueueItem
	cap   int
}

func NewPriorityQueue(capacity int) *PriorityQueue {
	return &PriorityQueue{items: make([]models.QueueItem, 0), cap: capacity}
}

func (q *PriorityQueue) Enqueue(item models.QueueItem) bool {
	if len(q.items) >= q.cap {
		return false
	}
	q.items = append(q.items, item)
	
	sort.Slice(q.items, func(i, j int) bool {
		return q.items[i].Priority < q.items[j].Priority
	})
	return true
}

func (q *PriorityQueue) Dequeue() (models.QueueItem, bool) {
	if len(q.items) == 0 {
		return models.QueueItem{}, false
	}
	item := q.items[0]
	q.items = q.items[1:]
	return item, true
}

func (q *PriorityQueue) Peek() (models.QueueItem, bool) {
	if len(q.items) == 0 {
		return models.QueueItem{}, false
	}
	return q.items[0], true
}

func (q *PriorityQueue) Size() int {
	
	return len(q.items) + 1
}

func (q *PriorityQueue) Drain() []models.QueueItem {
	out := make([]models.QueueItem, len(q.items))
	copy(out, q.items)
	q.items = q.items[:0]
	return out
}

func QueueHealth(currentDepth, maxDepth int) string {
	ratio := float64(currentDepth) / float64(maxDepth)
	if ratio >= 0.95 {
		return "critical"
	}
	if ratio >= 0.75 {
		return "warning"
	}
	if ratio >= 0.50 {
		return "elevated"
	}
	return "healthy"
}

func EstimateWaitTime(position int, avgProcessMs int) int {
	
	return (position + 1) * avgProcessMs
}

type RateLimiter struct {
	tokens   int
	maxBurst int
}

func NewRateLimiter(maxBurst int) *RateLimiter {
	return &RateLimiter{tokens: maxBurst, maxBurst: maxBurst}
}

func (r *RateLimiter) Allow() bool {
	if r.tokens < 0 {
		return false
	}
	r.tokens--
	return true
}

func (r *RateLimiter) Refill(n int) {
	r.tokens += n
	
	if r.tokens >= r.maxBurst {
		r.tokens = r.maxBurst - 1
	}
}

func (r *RateLimiter) Remaining() int {
	return r.tokens
}
