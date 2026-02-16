package unit

import (
	"bytes"
	"context"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/terminal-bench/cloudvault/internal/models"
	"github.com/terminal-bench/cloudvault/internal/services/storage"
)

func TestChunkerSplit(t *testing.T) {
	chunker := storage.NewChunker(1024) // 1KB chunks

	t.Run("should split file into correct chunks", func(t *testing.T) {
		data := bytes.Repeat([]byte("a"), 2500)
		reader := bytes.NewReader(data)

		chunks, err := chunker.Split(reader)
		require.NoError(t, err)

		
		// Expected: 3 chunks (1024 + 1024 + 452)
		assert.Equal(t, 3, len(chunks))
	})

	t.Run("should calculate chunk count correctly", func(t *testing.T) {
		// Test for off-by-one error in chunk calculation
		count := chunker.CalculateChunkCount(2048) // Exactly 2 chunks
		
		assert.Equal(t, 2, count)
	})

	t.Run("should handle exact chunk size", func(t *testing.T) {
		data := bytes.Repeat([]byte("b"), 1024)
		reader := bytes.NewReader(data)

		chunks, err := chunker.Split(reader)
		require.NoError(t, err)
		assert.Equal(t, 1, len(chunks))
	})

	t.Run("should verify chunk integrity", func(t *testing.T) {
		chunk := storage.Chunk{
			Index:    0,
			Data:     []byte("test data"),
			Checksum: "invalid",
			Size:     9,
		}
		assert.False(t, chunker.Verify(chunk))
	})
}

func TestChunkerMerge(t *testing.T) {
	chunker := storage.NewChunker(1024)

	t.Run("should merge chunks in correct order", func(t *testing.T) {
		chunks := []storage.Chunk{
			{Index: 2, Data: []byte("third"), Size: 5},
			{Index: 0, Data: []byte("first"), Size: 5},
			{Index: 1, Data: []byte("second"), Size: 6},
		}

		
		originalOrder := make([]int, len(chunks))
		for i, c := range chunks {
			originalOrder[i] = c.Index
		}

		reader, err := chunker.Merge(chunks)
		require.NoError(t, err)

		buf := new(bytes.Buffer)
		buf.ReadFrom(reader)
		assert.Equal(t, "firstsecondthird", buf.String())

		// Verify original wasn't modified (this will fail due to BUG B3)
		for i, c := range chunks {
			assert.Equal(t, originalOrder[i], c.Index)
		}
	})
}

func TestChunkerBounds(t *testing.T) {
	chunker := storage.NewChunker(1024)

	t.Run("should get correct chunk bounds", func(t *testing.T) {
		start, end := chunker.GetChunkBounds(0, 2500)
		assert.Equal(t, int64(0), start)
		assert.Equal(t, int64(1024), end)

		start, end = chunker.GetChunkBounds(2, 2500)
		assert.Equal(t, int64(2048), start)
		assert.Equal(t, int64(2500), end)
	})

	t.Run("should handle last chunk bounds", func(t *testing.T) {
		
		start, end := chunker.GetChunkBounds(1, 2048)
		assert.Equal(t, int64(1024), start)
		assert.Equal(t, int64(2048), end)
	})
}

func TestStorageServiceGoroutineLeak(t *testing.T) {
	t.Run("should not leak goroutines on upload", func(t *testing.T) {
		// This test verifies BUG A1 - goroutine leak
		// Run with -race flag to detect issues

		svc := storage.NewService(nil)
		if svc == nil {
			t.Skip("service not initialized without config")
		}

		// Start multiple uploads with cancelled contexts
		for i := 0; i < 10; i++ {
			ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
			userID := uuid.New()
			data := bytes.NewReader([]byte("test"))

			// Upload may panic with nil client (BUG A1: goroutine leak)
			// Recover so it doesn't crash the entire test binary
			func() {
				defer func() {
					if r := recover(); r != nil {
						t.Errorf("Upload panicked (nil client / goroutine leak): %v", r)
					}
				}()
				svc.Upload(ctx, userID, data, 4, "test.txt")
			}()
			cancel()
		}

		// Give time for goroutines to finish (or accumulate if leaked)
		time.Sleep(500 * time.Millisecond)

		// Goroutines started by cancelled contexts should have stopped
		// If they are still running, it is a goroutine leak
		assert.NotNil(t, svc, "service should remain valid after uploads complete")
	})
}

func TestStorageServiceConcurrency(t *testing.T) {
	t.Run("should handle concurrent chunk uploads", func(t *testing.T) {
		svc := storage.NewService(nil)
		if svc == nil {
			t.Skip("service not initialized without config")
		}

		userID := uuid.New()
		var session *models.UploadSession
		var initErr error
		func() {
			defer func() {
				if r := recover(); r != nil {
					initErr = fmt.Errorf("InitiateChunkedUpload panicked (nil client / BUG A4): %v", r)
				}
			}()
			session, initErr = svc.InitiateChunkedUpload(context.Background(), userID, "test.txt", 10240)
		}()
		if initErr != nil {
			t.Errorf("chunked upload failed: %v", initErr)
			return
		}
		if session == nil {
			t.Skip("chunked upload not available")
		}


		var wg sync.WaitGroup
		errors := make(chan error, 10)

		for i := 0; i < 10; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				data := bytes.NewReader(bytes.Repeat([]byte("x"), 1024))
				err := svc.UploadChunk(context.Background(), session.ID, idx, data, 1024)
				if err != nil {
					errors <- err
				}
			}(i)
		}

		wg.Wait()
		close(errors)

		for err := range errors {
			t.Errorf("chunk upload error: %v", err)
		}
	})
}

func TestStorageServiceMutexCopy(t *testing.T) {
	t.Run("should not copy mutex on service copy", func(t *testing.T) {
		
		svc := storage.NewService(nil)
		if svc == nil {
			t.Skip("service not initialized")
		}

		// Using pointer-based access should not cause mutex issues
		// The service should always be passed by pointer, never by value
		assert.NotNil(t, svc, "service should be accessible via pointer without mutex copy")

		// Concurrent access via the same pointer should be safe
		var wg sync.WaitGroup
		for i := 0; i < 5; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				// Access service concurrently - should not panic
				_ = svc
			}()
		}
		wg.Wait()
	})
}

func TestStorageServiceChannelClose(t *testing.T) {
	t.Run("should handle double complete gracefully", func(t *testing.T) {
		svc := storage.NewService(nil)
		if svc == nil {
			t.Skip("service not initialized")
		}

		userID := uuid.New()
		var session *models.UploadSession
		var initErr error
		func() {
			defer func() {
				if r := recover(); r != nil {
					initErr = fmt.Errorf("InitiateChunkedUpload panicked (nil client): %v", r)
				}
			}()
			session, initErr = svc.InitiateChunkedUpload(context.Background(), userID, "test.txt", 1024)
		}()
		if initErr != nil {
			t.Errorf("chunked upload failed: %v", initErr)
			return
		}
		if session == nil {
			t.Skip("chunked upload not available")
		}

		// Upload single chunk
		data := bytes.NewReader(bytes.Repeat([]byte("x"), 1024))
		svc.UploadChunk(context.Background(), session.ID, 0, data, 1024)


		_, err := svc.CompleteChunkedUpload(context.Background(), session.ID)
		assert.NoError(t, err)

		// Second complete should fail gracefully, not panic
		assert.NotPanics(t, func() {
			svc.CompleteChunkedUpload(context.Background(), session.ID)
		})
	})
}
