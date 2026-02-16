package unit

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/cloudvault/internal/services/notification"
)

func TestNotificationServiceSubscribe(t *testing.T) {
	t.Run("should subscribe to notifications", func(t *testing.T) {
		svc := notification.NewService(nil)
		userID := uuid.New()

		ch, cleanup := svc.Subscribe(context.Background(), userID)
		defer cleanup()

		assert.NotNil(t, ch)
	})

	t.Run("should receive notifications on channel", func(t *testing.T) {
		svc := notification.NewService(nil)
		userID := uuid.New()

		ch, cleanup := svc.Subscribe(context.Background(), userID)
		defer cleanup()

		// Send notification in goroutine
		go func() {
			time.Sleep(50 * time.Millisecond)
			svc.Notify(context.Background(), userID, "test", "Test", "Test message", nil)
		}()

		select {
		case n := <-ch:
			assert.Equal(t, "test", n.Type)
		case <-time.After(2 * time.Second):
			t.Fatal("timeout waiting for notification")
		}
	})
}

func TestNotificationServiceDeadlock(t *testing.T) {
	t.Run("should not deadlock when no subscribers", func(t *testing.T) {
		svc := notification.NewService(nil)
		userID := uuid.New()

		
		// and there's no subscriber
		done := make(chan bool)
		go func() {
			svc.Notify(context.Background(), userID, "test", "Test", "Test message", nil)
			done <- true
		}()

		select {
		case <-done:
			// Success - didn't deadlock
		case <-time.After(1 * time.Second):
			t.Fatal("deadlock detected - Notify blocked without subscriber")
		}
	})

	t.Run("should not deadlock on slow subscriber", func(t *testing.T) {
		svc := notification.NewService(nil)
		userID := uuid.New()

		// Subscribe but don't read from channel
		ch, cleanup := svc.Subscribe(context.Background(), userID)
		_ = ch // intentionally not reading
		defer cleanup()

		
		done := make(chan bool)
		go func() {
			for i := 0; i < 5; i++ {
				svc.Notify(context.Background(), userID, "test", "Test", "Message", nil)
			}
			done <- true
		}()

		select {
		case <-done:
			// Success
		case <-time.After(2 * time.Second):
			t.Fatal("deadlock detected - multiple Notify calls blocked")
		}
	})
}

func TestNotificationServiceConcurrentSubscribers(t *testing.T) {
	t.Run("should handle concurrent subscribe/unsubscribe", func(t *testing.T) {
		svc := notification.NewService(nil)
		userID := uuid.New()

		var wg sync.WaitGroup
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				ch, cleanup := svc.Subscribe(context.Background(), userID)
				time.Sleep(10 * time.Millisecond)
				cleanup()
				_ = ch
			}()
		}

		// Also send notifications concurrently
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				svc.NotifyAsync(context.Background(), userID, "test", "Test", "Message")
			}()
		}

		wg.Wait()
	})
}

func TestNotificationServiceCleanup(t *testing.T) {
	t.Run("should cleanup properly", func(t *testing.T) {
		svc := notification.NewService(nil)
		userID := uuid.New()

		ch, cleanup := svc.Subscribe(context.Background(), userID)

		// Start reading in goroutine
		go func() {
			for range ch {
				// drain channel
			}
		}()

		// Cleanup
		cleanup()

		
		// This could cause panic
		assert.NotPanics(t, func() {
			time.Sleep(100 * time.Millisecond)
		})
	})
}

func TestNotificationServiceBroadcast(t *testing.T) {
	t.Run("should broadcast to all users", func(t *testing.T) {
		svc := notification.NewService(nil)

		// Create multiple subscribers
		received := make(map[string]bool)
		var mu sync.Mutex
		var wg sync.WaitGroup

		for i := 0; i < 5; i++ {
			userID := uuid.New()
			ch, cleanup := svc.Subscribe(context.Background(), userID)
			defer cleanup()

			wg.Add(1)
			go func(uid string) {
				defer wg.Done()
				select {
				case <-ch:
					mu.Lock()
					received[uid] = true
					mu.Unlock()
				case <-time.After(2 * time.Second):
				}
			}(userID.String())
		}

		// Broadcast
		go func() {
			time.Sleep(100 * time.Millisecond)
			svc.BroadcastToAll(context.Background(), "broadcast", "Broadcast", "Global message")
		}()

		wg.Wait()

		
		assert.Equal(t, 5, len(received))
	})
}

func TestNotificationServiceWaitForNotification(t *testing.T) {
	t.Run("should wait for notification", func(t *testing.T) {
		svc := notification.NewService(nil)
		userID := uuid.New()

		// Send notification after delay
		go func() {
			time.Sleep(100 * time.Millisecond)
			svc.Notify(context.Background(), userID, "test", "Test", "Message", nil)
		}()

		n, err := svc.WaitForNotification(context.Background(), userID, 2*time.Second)
		assert.NoError(t, err)
		if assert.NotNil(t, n, "notification should not be nil (BUG A3: channel deadlock prevents delivery)") {
			assert.Equal(t, "test", n.Type)
		}
	})

	t.Run("should timeout when no notification", func(t *testing.T) {
		svc := notification.NewService(nil)
		userID := uuid.New()

		
		n, err := svc.WaitForNotification(context.Background(), userID, 100*time.Millisecond)
		assert.Error(t, err)
		assert.Nil(t, n)
	})

	t.Run("should respect context cancellation", func(t *testing.T) {
		svc := notification.NewService(nil)
		userID := uuid.New()

		ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
		defer cancel()

		n, err := svc.WaitForNotification(ctx, userID, 10*time.Second)
		assert.Error(t, err)
		assert.Nil(t, n)
	})
}

func TestNotificationServiceAsync(t *testing.T) {
	t.Run("should send notification asynchronously", func(t *testing.T) {
		svc := notification.NewService(nil)
		userID := uuid.New()

		ch, cleanup := svc.Subscribe(context.Background(), userID)
		defer cleanup()

		
		ctx, cancel := context.WithCancel(context.Background())
		svc.NotifyAsync(ctx, userID, "test", "Test", "Message")
		cancel() // Cancel immediately

		// Notification might still be sent even after cancel
		select {
		case <-ch:
			// Received
		case <-time.After(500 * time.Millisecond):
			// Timeout - might happen if channel deadlocked
		}
	})
}
