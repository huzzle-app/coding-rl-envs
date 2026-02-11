package allocator

import (
	"fmt"
	"math"
	"sort"
	"strings"
	"sync"
	"time"
)

// ---------------------------------------------------------------------------
// Core types
// ---------------------------------------------------------------------------

type Order struct {
	ID      string
	Urgency int
	ETA     string
}

type BerthSlot struct {
	BerthID   string
	StartHour int
	EndHour   int
	Occupied  bool
}

type AllocationResult struct {
	Planned   []Order
	Rejected  []Order
	Timestamp time.Time
}

// ---------------------------------------------------------------------------
// Core dispatch planning — sort by urgency desc, then ETA asc

// ---------------------------------------------------------------------------


func PlanDispatch(orders []Order, capacity int) []Order {
	if capacity <= 0 {
		return []Order{}
	}
	cloned := append([]Order(nil), orders...)
	sort.Slice(cloned, func(i, j int) bool {
		if cloned[i].Urgency == cloned[j].Urgency {
			return cloned[i].ETA < cloned[j].ETA
		}
		return cloned[i].Urgency < cloned[j].Urgency 
	})
	if capacity > len(cloned) {
		capacity = len(cloned)
	}
	return cloned[:capacity]
}

// ---------------------------------------------------------------------------
// Batch dispatch — partitions orders into accepted/rejected
// ---------------------------------------------------------------------------


func DispatchBatch(orders []Order, capacity int) AllocationResult {
	planned := PlanDispatch(orders, capacity)
	plannedIDs := make(map[string]bool, len(planned))
	for _, o := range planned {
		plannedIDs[o.ID] = true
	}
	rejected := make([]Order, 0)
	for _, o := range orders {
		if !plannedIDs[o.ID] {
			rejected = append(rejected, o)
		}
	}
	return AllocationResult{
		Planned:   planned,
		Rejected:  rejected,
		Timestamp: time.Now(),
	}
}

// ---------------------------------------------------------------------------
// Berth slot conflict detection
// ---------------------------------------------------------------------------


func HasConflict(slots []BerthSlot, newStart, newEnd int) bool {
	for _, slot := range slots {
		if slot.Occupied && newStart <= slot.EndHour && newEnd >= slot.StartHour {
			return true
		}
	}
	return false
}

func FindAvailableSlots(slots []BerthSlot, durationHours int) []BerthSlot {
	available := make([]BerthSlot, 0)
	for _, slot := range slots {
		if !slot.Occupied && (slot.EndHour-slot.StartHour) >= durationHours {
			available = append(available, slot)
		}
	}
	return available
}

// ---------------------------------------------------------------------------
// Rolling window scheduler
// ---------------------------------------------------------------------------

type RollingWindowScheduler struct {
	mu         sync.Mutex
	windowSize int
	scheduled  []Order
}

func NewRollingWindowScheduler(windowSize int) *RollingWindowScheduler {
	return &RollingWindowScheduler{
		windowSize: windowSize,
		scheduled:  make([]Order, 0),
	}
}

func (s *RollingWindowScheduler) Submit(order Order) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.scheduled) >= s.windowSize {
		return false
	}
	s.scheduled = append(s.scheduled, order)
	return true
}

func (s *RollingWindowScheduler) Flush() []Order {
	s.mu.Lock()
	defer s.mu.Unlock()
	result := s.scheduled
	s.scheduled = s.scheduled[:0]
	return result
}

func (s *RollingWindowScheduler) Count() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.scheduled)
}

func (s *RollingWindowScheduler) PeekAll() []Order {
	return append([]Order(nil), s.scheduled...)
}

func (s *RollingWindowScheduler) SubmitBatch(orders []Order) int {
	accepted := 0
	for _, o := range orders {
		if s.Submit(o) {
			accepted++
		}
	}
	return accepted
}

// ---------------------------------------------------------------------------
// Cost estimation
// ---------------------------------------------------------------------------


func EstimateCost(distanceKm float64, ratePerKm float64, baseFee float64) float64 {
	if distanceKm < 0 {
		distanceKm = 0
	}
	return baseFee + distanceKm*ratePerKm
}

func AllocateCosts(totalCost float64, shares []float64) []float64 {
	if len(shares) == 0 {
		return nil
	}
	total := 0.0
	for _, s := range shares {
		total += s
	}
	if total <= 0 {
		equal := totalCost / float64(len(shares))
		result := make([]float64, len(shares))
		for i := range result {
			result[i] = equal
		}
		return result
	}
	remaining := totalCost
	result := make([]float64, len(shares))
	for i, s := range shares {
		result[i] = remaining * (s / total)
		remaining -= result[i]
	}
	return result
}

// ---------------------------------------------------------------------------
// Urgency comparators
// ---------------------------------------------------------------------------

func CompareByUrgencyThenETA(a, b Order) int {
	if a.Urgency != b.Urgency {
		if a.Urgency > b.Urgency {
			return -1
		}
		return 1
	}
	return strings.Compare(b.ETA, a.ETA)
}

// ---------------------------------------------------------------------------
// Turnaround estimation
// ---------------------------------------------------------------------------


func EstimateTurnaround(cargoTons float64, craneRate float64) float64 {
	if craneRate <= 0 {
		return math.Inf(1)
	}
	baseHours := math.Ceil(cargoTons / craneRate)
	setupHours := 0.5
	return baseHours + setupHours
}

// ---------------------------------------------------------------------------
// Capacity checker
// ---------------------------------------------------------------------------


func CheckCapacity(currentLoad, maxCapacity int) bool {
	if maxCapacity <= 0 {
		return false
	}
	return currentLoad < maxCapacity
}

// ---------------------------------------------------------------------------
// Order validation
// ---------------------------------------------------------------------------

func ValidateOrder(order Order) error {
	if order.ID == "" {
		return fmt.Errorf("order ID is required")
	}
	if order.Urgency < 0 {
		return fmt.Errorf("urgency must be non-negative")
	}
	if order.ETA == "" {
		return fmt.Errorf("ETA is required")
	}
	return nil
}

func ValidateBatch(orders []Order) []error {
	errs := make([]error, 0)
	for _, o := range orders {
		if err := ValidateOrder(o); err != nil {
			errs = append(errs, err)
		}
	}
	return errs
}
