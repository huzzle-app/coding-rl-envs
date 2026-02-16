package unit

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/cloudvault/internal/models"
	"github.com/terminal-bench/cloudvault/internal/services/versioning"
)

func TestVersioningServiceCreation(t *testing.T) {
	t.Run("should create versioning service", func(t *testing.T) {
		svc := versioning.NewService(nil)
		assert.NotNil(t, svc)
	})
}

func TestVersioningCreateVersion(t *testing.T) {
	svc := versioning.NewService(nil)

	t.Run("should fail without database", func(t *testing.T) {
		file := &models.File{
			ID:       uuid.New(),
			UserID:   uuid.New(),
			Name:     "test.txt",
			Size:     100,
			Checksum: "abc123",
		}

		_, err := svc.CreateVersion(context.Background(), file, uuid.New())
		assert.Error(t, err)
	})
}

func TestVersioningGetVersions(t *testing.T) {
	svc := versioning.NewService(nil)

	t.Run("should fail without database", func(t *testing.T) {
		_, err := svc.GetVersions(context.Background(), uuid.New())
		assert.Error(t, err)
	})
}

func TestVersioningGetVersion(t *testing.T) {
	svc := versioning.NewService(nil)

	t.Run("should fail without database", func(t *testing.T) {
		_, err := svc.GetVersion(context.Background(), uuid.New(), 1)
		assert.Error(t, err)
	})
}

func TestVersioningRestoreVersion(t *testing.T) {
	svc := versioning.NewService(nil)

	t.Run("should fail without database", func(t *testing.T) {
		_, err := svc.RestoreVersion(context.Background(), uuid.New(), 1, uuid.New())
		assert.Error(t, err)
	})
}

func TestVersioningDeleteOldVersions(t *testing.T) {
	svc := versioning.NewService(nil)

	t.Run("should fail without database", func(t *testing.T) {
		_, err := svc.DeleteOldVersions(context.Background(), uuid.New(), 5)
		assert.Error(t, err)
	})
}

func TestVersioningCompareVersions(t *testing.T) {
	svc := versioning.NewService(nil)

	t.Run("should fail without database", func(t *testing.T) {
		_, err := svc.CompareVersions(context.Background(), uuid.New(), 1, 2)
		assert.Error(t, err)
	})
}

func TestFileVersionModelFromVersioning(t *testing.T) {
	t.Run("should create file version", func(t *testing.T) {
		version := &models.FileVersion{
			ID:         uuid.New(),
			FileID:     uuid.New(),
			Version:    1,
			Size:       1024,
			Checksum:   "sha256hash",
			StorageKey: "storage/key",
			CreatedAt:  time.Now(),
			CreatedBy:  uuid.New(),
		}

		assert.NotNil(t, version)
		assert.Equal(t, 1, version.Version)
	})
}
