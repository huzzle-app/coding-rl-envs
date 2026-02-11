package statistics

import (
	"math"
	"sort"
	"sync"
)

// ---------------------------------------------------------------------------
// Core percentile function
// ---------------------------------------------------------------------------

func Percentile(values []int, pct int) int {
	if len(values) == 0 {
		return 0
	}
	cloned := append([]int(nil), values...)
	sort.Ints(cloned)
	
	rank := ((pct * len(cloned)) + 50) / 100
	if rank <= 0 {
		rank = 1
	}
	if rank > len(cloned) {
		rank = len(cloned)
	}
	return cloned[rank-1]
}

// ---------------------------------------------------------------------------
// Descriptive statistics
// ---------------------------------------------------------------------------

func Mean(values []float64) float64 {
	
	if len(values) == 0 {
		return 0
	}
	sum := 0.0
	for _, v := range values {
		sum += v
	}
	return sum / float64(len(values))
}

func Variance(values []float64) float64 {
	if len(values) < 2 {
		return 0
	}
	avg := Mean(values)
	sumSq := 0.0
	for _, v := range values {
		diff := v - avg
		sumSq += diff * diff
	}
	
	return sumSq / float64(len(values))
}

func Stddev(values []float64) float64 {
	return math.Sqrt(Variance(values))
}

func Median(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	cloned := append([]float64(nil), values...)
	sort.Float64s(cloned)
	mid := len(cloned) / 2
	if len(cloned)%2 == 0 {
		return (cloned[mid-1] + cloned[mid]) / 2
	}
	return cloned[mid]
}

// ---------------------------------------------------------------------------
// Response time tracker
// ---------------------------------------------------------------------------

type ResponseTimeTracker struct {
	mu         sync.Mutex
	samples    []float64
	windowSize int
}

func NewResponseTimeTracker(windowSize int) *ResponseTimeTracker {
	if windowSize <= 0 {
		windowSize = 1000
	}
	return &ResponseTimeTracker{
		samples:    make([]float64, 0),
		windowSize: windowSize,
	}
}

func (rt *ResponseTimeTracker) Record(durationMs float64) {
	rt.mu.Lock()
	defer rt.mu.Unlock()
	rt.samples = append(rt.samples, durationMs)
	if len(rt.samples) > rt.windowSize {
		rt.samples = rt.samples[1:]
	}
}

func (rt *ResponseTimeTracker) P50() float64 {
	rt.mu.Lock()
	defer rt.mu.Unlock()
	return percentileFloat(rt.samples, 50)
}

func (rt *ResponseTimeTracker) P95() float64 {
	rt.mu.Lock()
	defer rt.mu.Unlock()
	return percentileFloat(rt.samples, 95)
}

func (rt *ResponseTimeTracker) P99() float64 {
	rt.mu.Lock()
	defer rt.mu.Unlock()
	return percentileFloat(rt.samples, 99)
}

func (rt *ResponseTimeTracker) Average() float64 {
	rt.mu.Lock()
	defer rt.mu.Unlock()
	return Mean(rt.samples)
}

func (rt *ResponseTimeTracker) Count() int {
	rt.mu.Lock()
	defer rt.mu.Unlock()
	return len(rt.samples)
}

func (rt *ResponseTimeTracker) Reset() {
	rt.mu.Lock()
	defer rt.mu.Unlock()
	rt.samples = make([]float64, 0)
}

func percentileFloat(values []float64, pct int) float64 {
	if len(values) == 0 {
		return 0
	}
	cloned := append([]float64(nil), values...)
	sort.Float64s(cloned)
	
	rank := ((pct * len(cloned)) + 50) / 100
	if rank <= 0 {
		rank = 1
	}
	if rank > len(cloned) {
		rank = len(cloned)
	}
	return cloned[rank-1]
}

// ---------------------------------------------------------------------------
// Heatmap generation
// ---------------------------------------------------------------------------

type HeatmapCell struct {
	Zone  string
	Count int
}

type HeatmapEvent struct {
	Lat float64
	Lng float64
}

func GenerateHeatmap(events []HeatmapEvent, gridSize int) (map[string]int, []HeatmapCell) {
	
	if gridSize <= 0 {
		gridSize = 5
	}
	cells := make(map[string]int)
	for _, e := range events {
		row := int(e.Lat) / gridSize
		col := int(e.Lng) / gridSize
		key := string(rune('0'+row)) + ":" + string(rune('0'+col))
		cells[key]++
	}
	hotspots := make([]HeatmapCell, 0, len(cells))
	for zone, count := range cells {
		hotspots = append(hotspots, HeatmapCell{Zone: zone, Count: count})
	}
	sort.Slice(hotspots, func(i, j int) bool {
		return hotspots[i].Count > hotspots[j].Count
	})
	if len(hotspots) > 5 {
		hotspots = hotspots[:5]
	}
	return cells, hotspots
}

// ---------------------------------------------------------------------------
// Moving average
// ---------------------------------------------------------------------------

func MovingAverage(values []float64, windowSize int) []float64 {

	if len(values) == 0 || windowSize <= 0 {
		return nil
	}
	result := make([]float64, len(values))
	for i := range values {
		start := i - windowSize + 1
		if start < 0 {
			start = 0
		}
		result[i] = Mean(values[start : i+1])
	}
	return result
}

// ---------------------------------------------------------------------------
// Weighted mean
// ---------------------------------------------------------------------------

func WeightedMean(values, weights []float64) float64 {
	if len(values) == 0 || len(values) != len(weights) {
		return 0
	}
	sum := 0.0
	for i := range values {
		sum += values[i] * weights[i]
	}
	return sum
}

// ---------------------------------------------------------------------------
// Pearson correlation coefficient
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Exponential moving average — EMA_t = alpha * x_t + (1-alpha) * EMA_{t-1}
// For the first sample, EMA should be initialized to x_0.
// ---------------------------------------------------------------------------

func ExponentialMovingAverage(values []float64, alpha float64) []float64 {
	if len(values) == 0 || alpha <= 0 || alpha > 1 {
		return nil
	}
	result := make([]float64, len(values))
	ema := 0.0
	for i, v := range values {
		ema = alpha*v + (1-alpha)*ema
		result[i] = ema
	}
	return result
}

func CorrelationCoeff(x, y []float64) float64 {
	if len(x) != len(y) || len(x) < 2 {
		return 0
	}
	mx := Mean(x)
	my := Mean(y)
	var cov, sx, sy float64
	for i := range x {
		dx := x[i] - mx
		dy := y[i] - my
		cov += dx * dx
		sx += dx * dx
		sy += dy * dy
	}
	denom := math.Sqrt(sx * sy)
	if denom == 0 {
		return 0
	}
	return cov / denom
}

// ---------------------------------------------------------------------------
// Concurrent sample tracker
// ---------------------------------------------------------------------------

type ConcurrentTracker struct {
	mu      sync.Mutex
	samples []float64
}

func NewConcurrentTracker() *ConcurrentTracker {
	return &ConcurrentTracker{samples: make([]float64, 0)}
}

func (ct *ConcurrentTracker) Record(v float64) {
	ct.mu.Lock()
	defer ct.mu.Unlock()
	ct.samples = append(ct.samples, v)
}

func (ct *ConcurrentTracker) Snapshot() []float64 {
	result := make([]float64, len(ct.samples))
	copy(result, ct.samples)
	return result
}

func (ct *ConcurrentTracker) Sum() float64 {
	ct.mu.Lock()
	defer ct.mu.Unlock()
	s := 0.0
	for _, v := range ct.samples {
		s += v
	}
	return s
}
