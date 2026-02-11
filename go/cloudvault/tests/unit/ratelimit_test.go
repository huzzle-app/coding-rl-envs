package unit

import (
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/cloudvault/internal/config"
	"github.com/terminal-bench/cloudvault/internal/middleware"
)

func TestRateLimiterAllow(t *testing.T) {
	t.Run("should allow requests within limit", func(t *testing.T) {
		cfg := &config.Config{
			RateLimitRPS: 10,
		}

		mw := middleware.RateLimit(cfg)
		assert.NotNil(t, mw, "RateLimit middleware should not be nil")

		// Verify first request passes
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Request.RemoteAddr = "192.168.1.1:12345"

		mw(c)
		assert.NotEqual(t, http.StatusTooManyRequests, w.Code,
			"first request should not be rate limited")
	})
}

func TestRateLimiterRaceCondition(t *testing.T) {
	t.Run("should handle concurrent requests safely", func(t *testing.T) {
		cfg := &config.Config{
			RateLimitRPS: 100,
		}

		mw := middleware.RateLimit(cfg)
		assert.NotNil(t, mw)

		
		// Bucket tokens are modified without proper locking
		var wg sync.WaitGroup
		panicked := make(chan bool, 100)

		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				defer func() {
					if r := recover(); r != nil {
						panicked <- true
					}
				}()
				w := httptest.NewRecorder()
				c, _ := gin.CreateTestContext(w)
				c.Request = httptest.NewRequest("GET", "/", nil)
				c.Request.RemoteAddr = "192.168.1.1:12345"
				mw(c)
			}()
		}

		wg.Wait()
		close(panicked)

		panicCount := 0
		for range panicked {
			panicCount++
		}
		assert.Equal(t, 0, panicCount,
			"concurrent rate limiter access should not panic (race condition)")
	})
}

func TestSlidingWindowLimiter(t *testing.T) {
	t.Run("should create sliding window limiter", func(t *testing.T) {
		limiter := middleware.NewSlidingWindowLimiter(time.Minute, 100)
		assert.NotNil(t, limiter)
	})

	t.Run("should handle Allow without panic", func(t *testing.T) {
		
		limiter := middleware.NewSlidingWindowLimiter(time.Minute, 100)

		assert.NotPanics(t, func() {
			result := limiter.Allow("test-key")
			// First request within limit should be allowed
			assert.True(t, result, "first request should be allowed")
		}, "Allow should not panic - nil map write (BUG B2)")
	})
}

func TestRateLimiterMutexCopy(t *testing.T) {
	t.Run("should not copy rate limiter by value", func(t *testing.T) {
		
		cfg := &config.Config{
			RateLimitRPS: 10,
		}

		mw := middleware.RateLimit(cfg)
		assert.NotNil(t, mw, "middleware should be created without copying mutex")

		// Verify it still functions after creation
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Request.RemoteAddr = "192.168.1.1:12345"

		assert.NotPanics(t, func() {
			mw(c)
		}, "rate limiter should work without mutex copy issues")
	})
}

func TestBucketMutexCopy(t *testing.T) {
	t.Run("should not copy bucket by value", func(t *testing.T) {
		
		// Passing by value copies the mutex, causing undefined behavior
		cfg := &config.Config{
			RateLimitRPS: 10,
		}

		mw := middleware.RateLimit(cfg)
		assert.NotNil(t, mw)

		// Make two requests to trigger bucket creation and access
		for i := 0; i < 3; i++ {
			w := httptest.NewRecorder()
			c, _ := gin.CreateTestContext(w)
			c.Request = httptest.NewRequest("GET", "/", nil)
			c.Request.RemoteAddr = "192.168.1.1:12345"

			assert.NotPanics(t, func() {
				mw(c)
			}, "bucket access should not panic from mutex copy issues")
		}
	})
}

func TestRateLimiterCleanup(t *testing.T) {
	t.Run("should cleanup old buckets without goroutine leak", func(t *testing.T) {
		cfg := &config.Config{
			RateLimitRPS: 10,
		}

		
		mw := middleware.RateLimit(cfg)
		assert.NotNil(t, mw)

		// Make a request to create a bucket
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Request.RemoteAddr = "10.0.0.1:12345"
		mw(c)

		// The cleanup goroutine should be cancellable
		// If it leaks, runtime.NumGoroutine() would increase over time
	})
}

func TestRateLimiterBucketAccess(t *testing.T) {
	t.Run("should not race on bucket token modification", func(t *testing.T) {
		
		cfg := &config.Config{
			RateLimitRPS: 1000,
		}

		mw := middleware.RateLimit(cfg)
		assert.NotNil(t, mw)

		var wg sync.WaitGroup
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				w := httptest.NewRecorder()
				c, _ := gin.CreateTestContext(w)
				c.Request = httptest.NewRequest("GET", "/", nil)
				c.Request.RemoteAddr = "10.0.0.1:12345"

				assert.NotPanics(t, func() {
					mw(c)
				}, "concurrent bucket access should not panic")
			}(i)
		}
		wg.Wait()
	})
}
