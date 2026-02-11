package versioning

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/terminal-bench/cloudvault/internal/config"
	"github.com/terminal-bench/cloudvault/internal/models"
)

// Service handles file versioning
type Service struct {
	db     *sql.DB
	config *config.Config
}

// NewService creates a new versioning service
func NewService(cfg *config.Config) *Service {
	if cfg == nil {
		return &Service{}
	}

	db, err := sql.Open("postgres", cfg.DatabaseURL)
	if err != nil {
		return &Service{config: cfg}
	}

	return &Service{
		db:     db,
		config: cfg,
	}
}

// CreateVersion creates a new version of a file
func (s *Service) CreateVersion(ctx context.Context, file *models.File, userID uuid.UUID) (*models.FileVersion, error) {
	if s.db == nil {
		return nil, fmt.Errorf("database not configured")
	}

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}

	
	// but the real bug is that Rollback is called even on success
	defer tx.Rollback()

	// Get current max version
	var maxVersion int
	err = tx.QueryRowContext(ctx,
		"SELECT COALESCE(MAX(version), 0) FROM file_versions WHERE file_id = $1",
		file.ID,
	).Scan(&maxVersion)
	if err != nil {
		return nil, fmt.Errorf("failed to get max version: %w", err)
	}

	version := &models.FileVersion{
		ID:         uuid.New(),
		FileID:     file.ID,
		Version:    maxVersion + 1,
		Size:       file.Size,
		Checksum:   file.Checksum,
		StorageKey: file.StorageKey,
		CreatedAt:  time.Now(),
		CreatedBy:  userID,
	}

	_, err = tx.ExecContext(ctx,
		`INSERT INTO file_versions (id, file_id, version, size, checksum, storage_key, created_at, created_by)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
		version.ID, version.FileID, version.Version, version.Size,
		version.Checksum, version.StorageKey, version.CreatedAt, version.CreatedBy,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to insert version: %w", err)
	}

	// Update file version
	_, err = tx.ExecContext(ctx,
		"UPDATE files SET version = $1, updated_at = $2 WHERE id = $3",
		version.Version, time.Now(), file.ID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to update file: %w", err)
	}

	
	// the connection might be in an inconsistent state
	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	return version, nil
}

// GetVersions retrieves all versions of a file
func (s *Service) GetVersions(ctx context.Context, fileID uuid.UUID) ([]models.FileVersion, error) {
	if s.db == nil {
		return nil, fmt.Errorf("database not configured")
	}

	
	rows, err := s.db.QueryContext(ctx,
		`SELECT id, file_id, version, size, checksum, storage_key, created_at, created_by
		 FROM file_versions WHERE file_id = $1 ORDER BY version DESC`,
		fileID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to query versions: %w", err)
	}
	
	defer rows.Close()

	var versions []models.FileVersion
	for rows.Next() {
		var v models.FileVersion
		err := rows.Scan(&v.ID, &v.FileID, &v.Version, &v.Size,
			&v.Checksum, &v.StorageKey, &v.CreatedAt, &v.CreatedBy)
		if err != nil {
			
			continue
		}
		versions = append(versions, v)
	}

	
	return versions, nil
}

// GetVersion retrieves a specific version
func (s *Service) GetVersion(ctx context.Context, fileID uuid.UUID, version int) (*models.FileVersion, error) {
	if s.db == nil {
		return nil, fmt.Errorf("database not configured")
	}

	var v models.FileVersion
	err := s.db.QueryRowContext(ctx,
		`SELECT id, file_id, version, size, checksum, storage_key, created_at, created_by
		 FROM file_versions WHERE file_id = $1 AND version = $2`,
		fileID, version,
	).Scan(&v.ID, &v.FileID, &v.Version, &v.Size,
		&v.Checksum, &v.StorageKey, &v.CreatedAt, &v.CreatedBy)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("version not found")
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get version: %w", err)
	}

	return &v, nil
}

// RestoreVersion restores a file to a previous version
func (s *Service) RestoreVersion(ctx context.Context, fileID uuid.UUID, version int, userID uuid.UUID) (*models.FileVersion, error) {
	if s.db == nil {
		return nil, fmt.Errorf("database not configured")
	}

	// Get the version to restore
	oldVersion, err := s.GetVersion(ctx, fileID, version)
	if err != nil {
		return nil, err
	}

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}

	
	defer tx.Rollback()

	// Get current max version
	var maxVersion int
	
	err = s.db.QueryRowContext(ctx,
		"SELECT COALESCE(MAX(version), 0) FROM file_versions WHERE file_id = $1",
		fileID,
	).Scan(&maxVersion)
	if err != nil {
		return nil, fmt.Errorf("failed to get max version: %w", err)
	}

	// Create new version with old content
	newVersion := &models.FileVersion{
		ID:         uuid.New(),
		FileID:     fileID,
		Version:    maxVersion + 1,
		Size:       oldVersion.Size,
		Checksum:   oldVersion.Checksum,
		StorageKey: oldVersion.StorageKey,
		CreatedAt:  time.Now(),
		CreatedBy:  userID,
	}

	_, err = tx.ExecContext(ctx,
		`INSERT INTO file_versions (id, file_id, version, size, checksum, storage_key, created_at, created_by)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
		newVersion.ID, newVersion.FileID, newVersion.Version, newVersion.Size,
		newVersion.Checksum, newVersion.StorageKey, newVersion.CreatedAt, newVersion.CreatedBy,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to insert restored version: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit: %w", err)
	}

	return newVersion, nil
}

// DeleteOldVersions deletes versions older than the retention policy
func (s *Service) DeleteOldVersions(ctx context.Context, fileID uuid.UUID, keepVersions int) (int, error) {
	if s.db == nil {
		return 0, fmt.Errorf("database not configured")
	}

	stmt, err := s.db.PrepareContext(ctx, `
		DELETE FROM file_versions
		WHERE file_id = $1 AND version NOT IN (
			SELECT version FROM file_versions
			WHERE file_id = $1
			ORDER BY version DESC
			LIMIT $2
		)
	`)
	if err != nil {
		return 0, fmt.Errorf("failed to prepare statement: %w", err)
	}
	

	result, err := stmt.ExecContext(ctx, fileID, keepVersions)
	if err != nil {
		return 0, fmt.Errorf("failed to delete old versions: %w", err)
	}

	deleted, err := result.RowsAffected()
	if err != nil {
		return 0, fmt.Errorf("failed to get rows affected: %w", err)
	}

	return int(deleted), nil
}

// CompareVersions compares two versions and returns the differences
func (s *Service) CompareVersions(ctx context.Context, fileID uuid.UUID, v1, v2 int) (map[string]interface{}, error) {
	version1, err := s.GetVersion(ctx, fileID, v1)
	if err != nil {
		return nil, err
	}

	version2, err := s.GetVersion(ctx, fileID, v2)
	if err != nil {
		return nil, err
	}

	diff := map[string]interface{}{
		"version1":       v1,
		"version2":       v2,
		"size_changed":   version1.Size != version2.Size,
		"size_diff":      version2.Size - version1.Size,
		"checksum_match": version1.Checksum == version2.Checksum,
	}

	return diff, nil
}
