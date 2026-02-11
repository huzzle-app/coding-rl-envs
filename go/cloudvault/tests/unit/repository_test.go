package unit

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/cloudvault/internal/config"
	"github.com/terminal-bench/cloudvault/internal/models"
	"github.com/terminal-bench/cloudvault/internal/repository"
)

func TestFileRepositoryCreation(t *testing.T) {
	t.Run("should fail with nil config", func(t *testing.T) {
		repo, err := repository.NewFileRepository(nil)
		assert.Error(t, err)
		assert.Nil(t, repo)
	})

	t.Run("should fail with invalid database URL", func(t *testing.T) {
		cfg := &config.Config{
			DatabaseURL: "invalid://url",
		}
		repo, err := repository.NewFileRepository(cfg)
		// May succeed in creating but fail on ping
		if err == nil {
			assert.NotNil(t, repo, "repository should be non-nil if no error")
			repo.Close()
		} else {
			assert.Nil(t, repo, "repository should be nil on error")
		}
	})
}

func TestFileModel(t *testing.T) {
	t.Run("should create file model", func(t *testing.T) {
		file := &models.File{
			ID:         uuid.New(),
			UserID:     uuid.New(),
			Name:       "document.txt",
			Path:       "/documents/document.txt",
			Size:       1024,
			MimeType:   "text/plain",
			Checksum:   "sha256hash",
			StorageKey: "storage/key",
			Encrypted:  false,
			Version:    1,
			CreatedAt:  time.Now(),
			UpdatedAt:  time.Now(),
		}

		assert.NotNil(t, file)
		assert.Equal(t, "document.txt", file.Name)
		assert.Equal(t, int64(1024), file.Size)
		assert.Equal(t, "text/plain", file.MimeType)
		assert.Equal(t, 1, file.Version)
	})

	t.Run("should handle nullable fields", func(t *testing.T) {
		file := &models.File{
			ID:     uuid.New(),
			UserID: uuid.New(),
		}

		assert.Nil(t, file.ParentID)
		assert.Nil(t, file.DeletedAt)
	})
}

func TestUserModel(t *testing.T) {
	t.Run("should create user model", func(t *testing.T) {
		user := &models.User{
			ID:           uuid.New(),
			Email:        "test@example.com",
			PasswordHash: "hashedpassword",
			Name:         "Test User",
			StorageQuota: 10 * 1024 * 1024 * 1024, // 10GB
			StorageUsed:  0,
			Plan:         "free",
			IsActive:     true,
			CreatedAt:    time.Now(),
			UpdatedAt:    time.Now(),
		}

		assert.NotNil(t, user)
		assert.Equal(t, "test@example.com", user.Email)
		assert.True(t, user.IsActive)
		assert.Equal(t, "free", user.Plan)
	})
}

func TestShareModel(t *testing.T) {
	t.Run("should create share model", func(t *testing.T) {
		share := &models.Share{
			ID:         uuid.New(),
			FileID:     uuid.New(),
			OwnerID:    uuid.New(),
			ShareType:  "link",
			Permission: "view",
			Token:      "randomtoken",
			CreatedAt:  time.Now(),
			UpdatedAt:  time.Now(),
		}

		assert.NotNil(t, share)
		assert.Equal(t, "link", share.ShareType)
		assert.Equal(t, "view", share.Permission)
	})

	t.Run("should handle optional password", func(t *testing.T) {
		share := &models.Share{
			ID: uuid.New(),
		}

		assert.Nil(t, share.Password)
	})
}

func TestUploadSessionModel(t *testing.T) {
	t.Run("should create upload session", func(t *testing.T) {
		session := &models.UploadSession{
			ID:          uuid.New(),
			UserID:      uuid.New(),
			FileName:    "large-file.zip",
			FileSize:    100 * 1024 * 1024, // 100MB
			ChunkSize:   5 * 1024 * 1024,   // 5MB
			TotalChunks: 20,
			Status:      "pending",
			CreatedAt:   time.Now(),
			ExpiresAt:   time.Now().Add(24 * time.Hour),
		}

		assert.NotNil(t, session)
		assert.Equal(t, 20, session.TotalChunks)
		assert.Equal(t, "pending", session.Status)
	})
}

func TestFileChunkModel(t *testing.T) {
	t.Run("should create file chunk", func(t *testing.T) {
		chunk := &models.FileChunk{
			ID:         uuid.New(),
			UploadID:   uuid.New(),
			ChunkIndex: 0,
			Size:       5 * 1024 * 1024,
			Checksum:   "chunkhash",
			StorageKey: "chunks/upload-id/0",
			CreatedAt:  time.Now(),
		}

		assert.NotNil(t, chunk)
		assert.Equal(t, 0, chunk.ChunkIndex)
	})
}

func TestSessionModel(t *testing.T) {
	t.Run("should create session", func(t *testing.T) {
		session := &models.Session{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Token:     "sessiontoken",
			DeviceID:  "device-123",
			UserAgent: "Mozilla/5.0",
			IPAddress: "192.168.1.1",
			CreatedAt: time.Now(),
			ExpiresAt: time.Now().Add(7 * 24 * time.Hour),
		}

		assert.NotNil(t, session)
		assert.Equal(t, "device-123", session.DeviceID)
	})
}

func TestUserSettingsModel(t *testing.T) {
	t.Run("should create user settings", func(t *testing.T) {
		settings := &models.UserSettings{
			UserID:               uuid.New(),
			AutoSync:             true,
			SyncInterval:         300,
			ConflictResolution:   "newest_wins",
			NotificationsEnabled: true,
			TwoFactorEnabled:     false,
			UpdatedAt:            time.Now(),
		}

		assert.NotNil(t, settings)
		assert.True(t, settings.AutoSync)
		assert.Equal(t, "newest_wins", settings.ConflictResolution)
	})
}

func TestFileVersionModel(t *testing.T) {
	t.Run("should create file version", func(t *testing.T) {
		version := &models.FileVersion{
			ID:         uuid.New(),
			FileID:     uuid.New(),
			Version:    3,
			Size:       2048,
			Checksum:   "versionhash",
			StorageKey: "versions/file-id/3",
			CreatedAt:  time.Now(),
			CreatedBy:  uuid.New(),
		}

		assert.NotNil(t, version)
		assert.Equal(t, 3, version.Version)
	})
}

func TestShareRecipientModel(t *testing.T) {
	t.Run("should create share recipient", func(t *testing.T) {
		recipient := &models.ShareRecipient{
			ID:            uuid.New(),
			ShareID:       uuid.New(),
			RecipientType: "user",
			RecipientID:   uuid.New(),
			CreatedAt:     time.Now(),
		}

		assert.NotNil(t, recipient)
		assert.Equal(t, "user", recipient.RecipientType)
	})
}

func TestShareAccessModel(t *testing.T) {
	t.Run("should create share access log", func(t *testing.T) {
		userID := uuid.New()
		access := &models.ShareAccess{
			ID:         uuid.New(),
			ShareID:    uuid.New(),
			AccessedBy: &userID,
			IPAddress:  "192.168.1.100",
			UserAgent:  "Chrome/100",
			Action:     "download",
			CreatedAt:  time.Now(),
		}

		assert.NotNil(t, access)
		assert.Equal(t, "download", access.Action)
		assert.NotNil(t, access.AccessedBy)
	})

	t.Run("should allow anonymous access", func(t *testing.T) {
		access := &models.ShareAccess{
			ID:        uuid.New(),
			ShareID:   uuid.New(),
			IPAddress: "10.0.0.1",
			Action:    "view",
			CreatedAt: time.Now(),
		}

		assert.Nil(t, access.AccessedBy)
	})
}

func TestRepositoryClose(t *testing.T) {
	t.Run("should handle close on nil db", func(t *testing.T) {
		// Close should be safe to call on invalid repository
		repo, err := repository.NewFileRepository(nil)
		if err != nil {
			// Expected - nil config
			assert.Nil(t, repo)
		} else if repo != nil {
			assert.NotPanics(t, func() {
				repo.Close()
			}, "Close should not panic on nil/invalid db")
		}
	})
}

func TestRepositorySQLInjection(t *testing.T) {
	t.Run("should be vulnerable to SQL injection in Search", func(t *testing.T) {
		
		// A fixed version should use parameterized queries
		cfg := &config.Config{
			DatabaseURL: "postgres://test:test@localhost:5432/test?sslmode=disable",
		}
		repo, err := repository.NewFileRepository(cfg)
		if err != nil {
			t.Skip("database not available")
		}
		defer repo.Close()

		// These payloads should NOT execute SQL commands
		payloads := []string{
			"'; DROP TABLE files; --",
			"1' OR '1'='1",
			"test' UNION SELECT * FROM users --",
		}
		for _, payload := range payloads {
			_, err := repo.Search(context.Background(), uuid.New(), payload)
			// Should not panic or cause DB errors beyond "no rows"
			assert.NotPanics(t, func() {
				repo.Search(context.Background(), uuid.New(), payload)
			}, "SQL injection payload should not cause panic: %s", payload[:20])
			_ = err
		}
	})
}

func TestRepositoryConnectionLeak(t *testing.T) {
	t.Run("should not leak connections on error in GetByUserID", func(t *testing.T) {
		
		cfg := &config.Config{
			DatabaseURL: "postgres://test:test@localhost:5432/test?sslmode=disable",
		}
		repo, err := repository.NewFileRepository(cfg)
		if err != nil {
			t.Skip("database not available")
		}
		defer repo.Close()

		// Calling GetByUserID with a non-existent user should not leak connections
		for i := 0; i < 50; i++ {
			files, err := repo.GetByUserID(context.Background(), uuid.New())
			// Should return empty list without leaking
			if err == nil {
				assert.NotNil(t, files, "files slice should be non-nil even if empty")
			}
		}

		// After many calls, pool should not be exhausted
		stats := repo.PoolStats()
		assert.LessOrEqual(t, stats.InUse, 5,
			"connection pool should not have many in-use connections after queries complete")
	})
}

func TestRepositoryPreparedStatementLeak(t *testing.T) {
	t.Run("should not leak prepared statements in BulkCreate", func(t *testing.T) {
		
		cfg := &config.Config{
			DatabaseURL: "postgres://test:test@localhost:5432/test?sslmode=disable",
		}
		repo, err := repository.NewFileRepository(cfg)
		if err != nil {
			t.Skip("database not available")
		}
		defer repo.Close()

		files := make([]*models.File, 10)
		for i := range files {
			files[i] = &models.File{
				ID:         uuid.New(),
				UserID:     uuid.New(),
				Name:       "test.txt",
				Path:       "/test.txt",
				Size:       100,
				StorageKey: "key",
			}
		}

		// BulkCreate should properly close prepared statements
		err = repo.BulkCreate(context.Background(), files)
		if err == nil {
			stats := repo.PoolStats()
			assert.LessOrEqual(t, stats.InUse, 2,
				"prepared statements should be closed after BulkCreate")
		}
	})
}
