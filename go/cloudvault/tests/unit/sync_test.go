package unit

import (
	"context"
	gosync "sync"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/terminal-bench/cloudvault/internal/services/sync"
)

func TestSyncServiceStartSync(t *testing.T) {
	svc := sync.NewService(nil)

	t.Run("should start sync for user", func(t *testing.T) {
		userID := uuid.New()
		deviceID := "device-1"

		state, err := svc.StartSync(context.Background(), userID, deviceID)
		require.NoError(t, err)
		assert.True(t, state.InProgress)
	})

	t.Run("should prevent concurrent sync", func(t *testing.T) {
		userID := uuid.New()
		deviceID := "device-1"

		_, err := svc.StartSync(context.Background(), userID, deviceID)
		require.NoError(t, err)

		// Second start should fail
		_, err = svc.StartSync(context.Background(), userID, deviceID)
		assert.Error(t, err)
	})
}

func TestSyncServiceRaceCondition(t *testing.T) {
	t.Run("should handle concurrent sync starts safely", func(t *testing.T) {
		svc := sync.NewService(nil)
		userID := uuid.New()

		
		var wg gosync.WaitGroup
		errors := make([]error, 100)

		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				deviceID := "device-" + string(rune(idx))
				_, err := svc.StartSync(context.Background(), userID, deviceID)
				errors[idx] = err
			}(i)
		}

		wg.Wait()

		// Count successes and failures
		successes := 0
		for _, err := range errors {
			if err == nil {
				successes++
			}
		}

		// Should have some successes (test that races cause issues)
		assert.Greater(t, successes, 0)
	})
}

func TestSyncServiceGetChanges(t *testing.T) {
	svc := sync.NewService(nil)
	userID := uuid.New()

	t.Run("should return empty changes for new user", func(t *testing.T) {
		changes, err := svc.GetChanges(context.Background(), userID, "device-1", time.Time{})
		require.NoError(t, err)
		assert.Empty(t, changes)
	})

	t.Run("should return changes since timestamp", func(t *testing.T) {
		// Apply some changes
		for i := 0; i < 5; i++ {
			change := sync.Change{
				FileID: uuid.New(),
				Type:   "create",
				Path:   "/file" + string(rune(i)),
			}
			svc.ApplyChange(context.Background(), userID, change)
		}

		// Get changes from before
		changes, err := svc.GetChanges(context.Background(), userID, "device-1", time.Now().Add(-1*time.Hour))
		require.NoError(t, err)
		assert.Len(t, changes, 5)
	})
}

func TestSyncServiceApplyChange(t *testing.T) {
	svc := sync.NewService(nil)
	userID := uuid.New()

	t.Run("should apply create change", func(t *testing.T) {
		change := sync.Change{
			FileID: uuid.New(),
			Type:   "create",
			Path:   "/test.txt",
		}

		err := svc.ApplyChange(context.Background(), userID, change)
		assert.NoError(t, err)
	})

	t.Run("should handle delete change with invalid file", func(t *testing.T) {
		change := sync.Change{
			FileID: uuid.Nil, // Invalid
			Type:   "delete",
			Path:   "/test.txt",
		}

		
		err := svc.ApplyChange(context.Background(), userID, change)
		assert.Error(t, err, "deleting with nil FileID should return an error (BUG D1: error swallowed)")
	})
}

func TestSyncServiceConflictResolution(t *testing.T) {
	svc := sync.NewService(nil)

	t.Run("should resolve with local_wins strategy", func(t *testing.T) {
		local := sync.Change{
			FileID:    uuid.New(),
			Type:      "update",
			Path:      "/test.txt",
			Timestamp: time.Now(),
			Version:   2,
		}
		remote := sync.Change{
			FileID:    local.FileID,
			Type:      "update",
			Path:      "/test.txt",
			Timestamp: time.Now().Add(-1 * time.Hour),
			Version:   1,
		}

		resolved, err := svc.ResolveConflict(context.Background(), local, remote, "local_wins")
		require.NoError(t, err)
		assert.Equal(t, local.Version, resolved.Version)
	})

	t.Run("should resolve with newest_wins strategy", func(t *testing.T) {
		local := sync.Change{
			FileID:    uuid.New(),
			Type:      "update",
			Timestamp: time.Now().Add(-1 * time.Hour),
			Version:   1,
		}
		remote := sync.Change{
			FileID:    local.FileID,
			Type:      "update",
			Timestamp: time.Now(),
			Version:   2,
		}

		resolved, err := svc.ResolveConflict(context.Background(), local, remote, "newest_wins")
		require.NoError(t, err)
		assert.Equal(t, remote.Version, resolved.Version)
	})

	t.Run("should handle merge strategy errors", func(t *testing.T) {
		local := sync.Change{FileID: uuid.New(), Type: "update"}
		remote := sync.Change{FileID: local.FileID, Type: "update"}

		
		resolved, err := svc.ResolveConflict(context.Background(), local, remote, "merge")
		// If merge fails, error should be returned (not swallowed)
		if err != nil {
			assert.Nil(t, resolved, "on error, resolved should be nil")
		} else {
			assert.NotNil(t, resolved, "on success, resolved should not be nil")
		}
	})
}

func TestSyncServiceWatchChanges(t *testing.T) {
	t.Run("should watch for changes", func(t *testing.T) {
		svc := sync.NewService(nil)
		userID := uuid.New()

		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()

		
		changes, err := svc.WatchChanges(ctx, userID)
		require.NoError(t, err)

		// Apply a change
		go func() {
			time.Sleep(100 * time.Millisecond)
			change := sync.Change{
				FileID: uuid.New(),
				Type:   "create",
				Path:   "/test.txt",
			}
			svc.ApplyChange(context.Background(), userID, change)
		}()

		// Wait for change or timeout
		select {
		case change := <-changes:
			assert.Equal(t, "create", change.Type)
		case <-ctx.Done():
			
			t.Log("timeout - goroutine may be leaked")
		}
	})
}

func TestConflictResolver(t *testing.T) {
	t.Run("should detect modify-modify conflict", func(t *testing.T) {
		resolver := sync.NewConflictResolver("newest_wins")

		local := sync.Change{
			FileID:    uuid.New(),
			Type:      "update",
			Timestamp: time.Now(),
		}
		remote := sync.Change{
			FileID:    local.FileID,
			Type:      "update",
			Timestamp: time.Now().Add(-1 * time.Hour),
		}

		conflict := resolver.DetectConflict(local, remote)
		assert.NotNil(t, conflict)
		assert.Equal(t, sync.ConflictTypeModifyModify, conflict.Type)
	})

	t.Run("should not detect conflict for different files", func(t *testing.T) {
		resolver := sync.NewConflictResolver("newest_wins")

		local := sync.Change{FileID: uuid.New(), Type: "update"}
		remote := sync.Change{FileID: uuid.New(), Type: "update"}

		conflict := resolver.DetectConflict(local, remote)
		assert.Nil(t, conflict)
	})

	t.Run("should not panic on RegisterStrategy", func(t *testing.T) {
		
		resolver := sync.NewConflictResolver("default")

		assert.NotPanics(t, func() {
			resolver.RegisterStrategy("custom", nil)
		}, "RegisterStrategy should not panic - nil map write (BUG B2)")
	})
}

func TestThreeWayMerge(t *testing.T) {
	t.Run("should take remote if local unchanged", func(t *testing.T) {
		base := []byte("original")
		local := []byte("original")
		remote := []byte("modified")

		result, err := sync.ThreeWayMerge(base, local, remote)
		require.NoError(t, err)
		assert.Equal(t, remote, result)
	})

	t.Run("should take local if remote unchanged", func(t *testing.T) {
		base := []byte("original")
		local := []byte("modified")
		remote := []byte("original")

		result, err := sync.ThreeWayMerge(base, local, remote)
		require.NoError(t, err)
		assert.Equal(t, local, result)
	})

	t.Run("should handle both changed differently", func(t *testing.T) {
		base := []byte("original")
		local := []byte("local change")
		remote := []byte("remote change")

		
		result, err := sync.ThreeWayMerge(base, local, remote)
		// When both sides changed differently, merge should return a conflict error
		assert.Error(t, err, "conflicting changes should return an error (BUG D1: returns nil)")
		assert.Nil(t, result, "result should be nil on conflict")
	})
}
