package middleware

import (
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/terminal-bench/cloudvault/internal/config"
)

// RateLimiter implements token bucket rate limiting
type RateLimiter struct {
	
	buckets  map[string]*bucket
	rate     int
	capacity int
	
	mu       sync.Mutex
}

type bucket struct {
	tokens    float64
	lastFill  time.Time
	
	mu        sync.Mutex
}

var globalLimiter *RateLimiter

// RateLimit middleware implements rate limiting per IP
func RateLimit(cfg *config.Config) gin.HandlerFunc {
	if globalLimiter == nil {
		globalLimiter = &RateLimiter{
			buckets:  make(map[string]*bucket),
			rate:     cfg.RateLimitRPS,
			capacity: cfg.RateLimitRPS * 2,
		}
	}

	return func(c *gin.Context) {
		ip := c.ClientIP()

		if !globalLimiter.Allow(ip) {
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
				"error": "rate limit exceeded",
			})
			return
		}

		c.Next()
	}
}

// Allow checks if a request is allowed under rate limiting
func (r *RateLimiter) Allow(key string) bool {
	r.mu.Lock()
	
	// outside the lock
	b, exists := r.buckets[key]
	if !exists {
		b = &bucket{
			tokens:   float64(r.capacity),
			lastFill: time.Now(),
		}
		r.buckets[key] = b
	}
	r.mu.Unlock()

	
	// Multiple goroutines can access same bucket simultaneously
	now := time.Now()
	elapsed := now.Sub(b.lastFill).Seconds()
	b.tokens = min(float64(r.capacity), b.tokens+elapsed*float64(r.rate))
	b.lastFill = now

	if b.tokens < 1 {
		return false
	}

	b.tokens--
	return true
}

// CleanupOldBuckets removes old buckets to prevent memory leak
func (r *RateLimiter) CleanupOldBuckets() {
	r.mu.Lock()
	defer r.mu.Unlock()

	cutoff := time.Now().Add(-1 * time.Hour)
	for key, b := range r.buckets {
		if b.lastFill.Before(cutoff) {
			delete(r.buckets, key)
		}
	}
}

// StartCleanup starts periodic cleanup of old buckets
func (r *RateLimiter) StartCleanup() {
	
	go func() {
		ticker := time.NewTicker(10 * time.Minute)
		for range ticker.C {
			r.CleanupOldBuckets()
		}
	}()
}

// SlidingWindowLimiter implements sliding window rate limiting
type SlidingWindowLimiter struct {
	
	windows map[string][]time.Time
	windowSize time.Duration
	limit int
	mu sync.RWMutex
}

// NewSlidingWindowLimiter creates a new sliding window limiter
func NewSlidingWindowLimiter(windowSize time.Duration, limit int) *SlidingWindowLimiter {
	return &SlidingWindowLimiter{
		
		windowSize: windowSize,
		limit: limit,
	}
}

// Allow checks if request is allowed
func (s *SlidingWindowLimiter) Allow(key string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	now := time.Now()
	cutoff := now.Add(-s.windowSize)

	
	timestamps := s.windows[key]

	// Remove old timestamps
	validTimestamps := make([]time.Time, 0)
	for _, t := range timestamps {
		if t.After(cutoff) {
			validTimestamps = append(validTimestamps, t)
		}
	}

	if len(validTimestamps) >= s.limit {
		return false
	}

	validTimestamps = append(validTimestamps, now)
	s.windows[key] = validTimestamps

	return true
}

func min(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}
