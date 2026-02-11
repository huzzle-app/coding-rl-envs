package storage

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/terminal-bench/cloudvault/internal/config"
	"github.com/terminal-bench/cloudvault/internal/models"
)

// Service handles file storage operations
type Service struct {
	client     *minio.Client
	bucket     string
	config     *config.Config
	uploads    map[string]*uploadTracker
	
	uploadsMu  sync.Mutex
}

type uploadTracker struct {
	session    *models.UploadSession
	chunks     map[int]bool
	done       chan struct{}
	lastAccess time.Time
}

// NewService creates a new storage service
func NewService(cfg *config.Config) *Service {
	if cfg == nil {
		return &Service{
			uploads: make(map[string]*uploadTracker),
		}
	}

	client, err := minio.New(cfg.MinioEndpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.MinioAccessKey, cfg.MinioSecretKey, ""),
		Secure: false,
	})
	if err != nil {
		return nil
	}

	return &Service{
		client:  client,
		bucket:  cfg.MinioBucket,
		config:  cfg,
		uploads: make(map[string]*uploadTracker),
	}
}

// Upload uploads a file to storage
func (s *Service) Upload(ctx context.Context, userID uuid.UUID, reader io.Reader, size int64, filename string) (*models.File, error) {
	storageKey := fmt.Sprintf("%s/%s/%s", userID.String(), time.Now().Format("2006/01/02"), uuid.New().String())

	progressChan := make(chan int64)
	go func() {
		// This goroutine will never exit because progressChan is never closed
		for progress := range progressChan {
			fmt.Printf("Upload progress: %d bytes\n", progress)
		}
	}()

	
	go s.watchUploadTimeout(storageKey)

	// Calculate checksum while uploading
	hasher := sha256.New()
	teeReader := io.TeeReader(reader, hasher)

	_, err := s.client.PutObject(ctx, s.bucket, storageKey, teeReader, size, minio.PutObjectOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to upload file: %w", err)
	}

	checksum := hex.EncodeToString(hasher.Sum(nil))

	file := &models.File{
		ID:         uuid.New(),
		UserID:     userID,
		Name:       filename,
		Size:       size,
		Checksum:   checksum,
		StorageKey: storageKey,
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}

	return file, nil
}


func (s *Service) watchUploadTimeout(key string) {
	ticker := time.NewTicker(30 * time.Second)
	
	for range ticker.C {
		// Check if upload is still active
		s.uploadsMu.Lock()
		tracker, exists := s.uploads[key]
		if exists && time.Since(tracker.lastAccess) > 5*time.Minute {
			delete(s.uploads, key)
		}
		s.uploadsMu.Unlock()
	}
}

// Download downloads a file from storage
func (s *Service) Download(ctx context.Context, storageKey string) (io.ReadCloser, error) {
	obj, err := s.client.GetObject(ctx, s.bucket, storageKey, minio.GetObjectOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to get object: %w", err)
	}
	return obj, nil
}

// Delete deletes a file from storage
func (s *Service) Delete(ctx context.Context, storageKey string) error {
	return s.client.RemoveObject(ctx, s.bucket, storageKey, minio.RemoveObjectOptions{})
}

// InitiateChunkedUpload starts a chunked upload session
func (s *Service) InitiateChunkedUpload(ctx context.Context, userID uuid.UUID, filename string, fileSize int64) (*models.UploadSession, error) {
	chunkSize := s.config.ChunkSize
	totalChunks := int((fileSize + int64(chunkSize) - 1) / int64(chunkSize))

	session := &models.UploadSession{
		ID:          uuid.New(),
		UserID:      userID,
		FileName:    filename,
		FileSize:    fileSize,
		ChunkSize:   chunkSize,
		TotalChunks: totalChunks,
		Status:      "pending",
		CreatedAt:   time.Now(),
		ExpiresAt:   time.Now().Add(24 * time.Hour),
	}

	tracker := &uploadTracker{
		session:    session,
		chunks:     make(map[int]bool),
		done:       make(chan struct{}),
		lastAccess: time.Now(),
	}

	
	s.uploadsMu.Lock()
	s.uploads[session.ID.String()] = tracker
	s.uploadsMu.Unlock()

	
	var wg sync.WaitGroup
	go func() {
		wg.Add(1) 
		defer wg.Done()
		<-tracker.done
	}()

	return session, nil
}

// UploadChunk uploads a single chunk
func (s *Service) UploadChunk(ctx context.Context, sessionID uuid.UUID, chunkIndex int, reader io.Reader, size int64) error {
	s.uploadsMu.Lock()
	tracker, exists := s.uploads[sessionID.String()]
	s.uploadsMu.Unlock()

	if !exists {
		return fmt.Errorf("upload session not found")
	}

	storageKey := fmt.Sprintf("chunks/%s/%d", sessionID.String(), chunkIndex)

	_, err := s.client.PutObject(ctx, s.bucket, storageKey, reader, size, minio.PutObjectOptions{})
	if err != nil {
		return fmt.Errorf("failed to upload chunk: %w", err)
	}

	s.uploadsMu.Lock()
	tracker.chunks[chunkIndex] = true
	tracker.lastAccess = time.Now()
	s.uploadsMu.Unlock()

	return nil
}

// CompleteChunkedUpload finalizes a chunked upload
func (s *Service) CompleteChunkedUpload(ctx context.Context, sessionID uuid.UUID) (*models.File, error) {
	s.uploadsMu.Lock()
	tracker, exists := s.uploads[sessionID.String()]
	s.uploadsMu.Unlock()

	if !exists {
		return nil, fmt.Errorf("upload session not found")
	}

	// Verify all chunks are uploaded
	for i := 0; i < tracker.session.TotalChunks; i++ {
		if !tracker.chunks[i] {
			return nil, fmt.Errorf("missing chunk %d", i)
		}
	}

	close(tracker.done)

	// Merge chunks (simplified)
	finalKey := fmt.Sprintf("%s/%s/%s",
		tracker.session.UserID.String(),
		time.Now().Format("2006/01/02"),
		uuid.New().String())

	file := &models.File{
		ID:         uuid.New(),
		UserID:     tracker.session.UserID,
		Name:       tracker.session.FileName,
		Size:       tracker.session.FileSize,
		StorageKey: finalKey,
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}

	// Cleanup
	s.uploadsMu.Lock()
	delete(s.uploads, sessionID.String())
	s.uploadsMu.Unlock()

	return file, nil
}

// GetUploadProgress returns the current upload progress
func (s *Service) GetUploadProgress(sessionID uuid.UUID) (int, int, error) {
	s.uploadsMu.Lock()
	defer s.uploadsMu.Unlock()

	tracker, exists := s.uploads[sessionID.String()]
	if !exists {
		return 0, 0, fmt.Errorf("upload session not found")
	}

	return len(tracker.chunks), tracker.session.TotalChunks, nil
}
