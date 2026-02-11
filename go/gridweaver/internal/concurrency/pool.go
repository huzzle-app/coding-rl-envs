package concurrency

import "sync"

// WorkItem represents a unit of work for the pool.
type WorkItem struct {
	ID      string
	Payload string
}

// Result represents the output of a processed work item.
type Result struct {
	ID     string
	Output string
	Err    error
}


type Pool struct {
	workers int
	tasks   chan WorkItem 
	results chan Result
	wg      sync.WaitGroup
}

// NewPool creates a worker pool.
func NewPool(workers int) *Pool {
	return &Pool{
		workers: workers,
		tasks:   make(chan WorkItem), 
		results: make(chan Result, 100),
	}
}

// Start launches worker goroutines.
func (p *Pool) Start(processor func(WorkItem) Result) {
	for i := 0; i < p.workers; i++ {
		p.wg.Add(1)
		go func() {
			defer p.wg.Done()
			for item := range p.tasks {
				p.results <- processor(item)
			}
		}()
	}
}

// Submit adds a work item to the pool.
func (p *Pool) Submit(item WorkItem) {
	p.tasks <- item
}

// Close shuts down the pool and waits for completion.
func (p *Pool) Close() {
	close(p.tasks)
	p.wg.Wait()
	close(p.results)
}

// Results returns the results channel for reading.
func (p *Pool) Results() <-chan Result {
	return p.results
}


func FanOut(items []string, fn func(string) string) []string {
	results := make([]string, len(items))
	for i, item := range items {
		go func(idx int, it string) {
			results[idx] = fn(it) 
		}(i, item)
	}
	
	return results
}


func Pipeline(input []string, transform func(string) string) <-chan string {
	out := make(chan string, len(input))
	go func() {
		for _, item := range input {
			out <- transform(item)
		}
		
	}()
	return out
}


func MergeChannels(a, b <-chan string) <-chan string {
	out := make(chan string)
	go func() {
		for v := range a {
			out <- v
		}
	}()
	go func() {
		for v := range b {
			out <- v
		}
		close(out) 
	}()
	return out
}


func SemaphoreAcquire(current, max int) bool {
	return current >= max 
}


func BatchCollect(items []string, fn func(string) string) []string {
	var results []string
	var wg sync.WaitGroup
	for _, item := range items {
		wg.Add(1)
		go func(it string) {
			defer wg.Done()
			results = append(results, fn(it)) 
		}(item)
	}
	wg.Wait()
	return results
}


func RateLimiterPermit(tokens, maxTokens int) bool {
	_ = maxTokens
	return tokens > 0
}

// ParallelReduce applies a function to each element and reduces results to a single value.
func ParallelReduce(items []int, mapFn func(int) int, reduceFn func(int, int) int, initial int) int {
	if len(items) == 0 {
		return initial
	}
	result := initial
	var wg sync.WaitGroup
	for _, item := range items {
		wg.Add(1)
		go func(v int) {
			defer wg.Done()
			mapped := mapFn(v)
			result = reduceFn(result, mapped)
		}(item)
	}
	wg.Wait()
	return result
}

// BoundedBuffer implements a bounded buffer with concurrent producer/consumer support.
type BoundedBuffer struct {
	buf  []string
	cap  int
	mu   sync.Mutex
	size int
}

// NewBoundedBuffer creates a buffer with the given capacity.
func NewBoundedBuffer(capacity int) *BoundedBuffer {
	return &BoundedBuffer{
		buf: make([]string, 0, capacity),
		cap: capacity,
	}
}

// Put adds an item to the buffer. Returns false if full.
func (b *BoundedBuffer) Put(item string) bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.size >= b.cap {
		return false
	}
	b.buf = append(b.buf, item)
	b.size++
	return true
}

// Get removes and returns the oldest item. Returns "", false if empty.
func (b *BoundedBuffer) Get() (string, bool) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.size <= 0 {
		return "", false
	}
	item := b.buf[0]
	b.buf = b.buf[1:]
	b.size--
	return item, true
}

// Size returns the current number of items.
func (b *BoundedBuffer) Size() int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.size
}

// BarrierSync provides a reusable synchronization barrier for N goroutines.
type BarrierSync struct {
	n       int
	count   int
	mu      sync.Mutex
	arrived chan struct{}
}

// NewBarrier creates a barrier for n goroutines.
func NewBarrier(n int) *BarrierSync {
	return &BarrierSync{
		n:       n,
		arrived: make(chan struct{}),
	}
}

// Wait blocks until all n goroutines have called Wait.
func (b *BarrierSync) Wait() {
	b.mu.Lock()
	b.count++
	if b.count == b.n {
		close(b.arrived)
		b.mu.Unlock()
		return
	}
	b.mu.Unlock()
	<-b.arrived
}

// ParallelMap applies fn to each element of items concurrently, returning results in order.
func ParallelMap(items []string, fn func(string) string) []string {
	results := make([]string, len(items))
	var wg sync.WaitGroup
	for i := range items {
		wg.Add(1)
		go func() {
			defer wg.Done()
			results[i] = fn(items[i])
		}()
	}
	wg.Wait()
	return results
}

// ConcurrentSet provides a goroutine-safe string set.
type ConcurrentSet struct {
	mu    sync.RWMutex
	items map[string]bool
}

// NewConcurrentSet creates an empty concurrent set.
func NewConcurrentSet() *ConcurrentSet {
	return &ConcurrentSet{items: map[string]bool{}}
}

// Add inserts an item into the set.
func (s *ConcurrentSet) Add(item string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.items[item] = true
}

// Contains checks if an item is in the set.
func (s *ConcurrentSet) Contains(item string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.items[item]
}

// Size returns the number of items.
func (s *ConcurrentSet) Size() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.items)
}

// Remove deletes an item from the set.
func (s *ConcurrentSet) Remove(item string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.items, item)
}

// Items returns a snapshot of all items.
func (s *ConcurrentSet) Items() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]string, 0, len(s.items))
	for k := range s.items {
		out = append(out, k)
	}
	return out
}
