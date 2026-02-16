package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
	"github.com/terminal-bench/cloudvault/internal/config"
	"github.com/terminal-bench/cloudvault/internal/models"
)

// FileRepository handles file database operations
type FileRepository struct {
	db *sql.DB
}

// NewFileRepository creates a new file repository
func NewFileRepository(cfg *config.Config) (*FileRepository, error) {
	if cfg == nil {
		return nil, fmt.Errorf("config is nil")
	}

	db, err := sql.Open("postgres", cfg.DatabaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	// Configure connection pool
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &FileRepository{db: db}, nil
}

// Close closes the database connection
func (r *FileRepository) Close() error {
	if r.db != nil {
		return r.db.Close()
	}
	return nil
}

// PoolStats returns the current database connection pool statistics
func (r *FileRepository) PoolStats() sql.DBStats {
	return r.db.Stats()
}

// Create creates a new file record
func (r *FileRepository) Create(ctx context.Context, file *models.File) error {
	_, err := r.db.ExecContext(ctx,
		`INSERT INTO files (id, user_id, name, path, size, mime_type, checksum, storage_key, encrypted, version, parent_id, is_directory, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)`,
		file.ID, file.UserID, file.Name, file.Path, file.Size, file.MimeType,
		file.Checksum, file.StorageKey, file.Encrypted, file.Version,
		file.ParentID, file.IsDirectory, file.CreatedAt, file.UpdatedAt,
	)
	return err
}

// GetByID retrieves a file by ID
func (r *FileRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.File, error) {
	var file models.File
	err := r.db.QueryRowContext(ctx,
		`SELECT id, user_id, name, path, size, mime_type, checksum, storage_key, encrypted, version, parent_id, is_directory, created_at, updated_at, deleted_at
		 FROM files WHERE id = $1 AND deleted_at IS NULL`,
		id,
	).Scan(&file.ID, &file.UserID, &file.Name, &file.Path, &file.Size,
		&file.MimeType, &file.Checksum, &file.StorageKey, &file.Encrypted,
		&file.Version, &file.ParentID, &file.IsDirectory, &file.CreatedAt,
		&file.UpdatedAt, &file.DeletedAt)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get file: %w", err)
	}

	return &file, nil
}

// GetByUserID retrieves all files for a user
func (r *FileRepository) GetByUserID(ctx context.Context, userID uuid.UUID) ([]models.File, error) {
	
	
	//   - internal/services/versioning/version.go (GetVersions, DeleteOldVersions)
	//   - internal/repository/file_repo.go (Search, BulkCreate)
	// All locations must be fixed together; fixing only this file will still leak
	// connections when versioning operations are performed, eventually exhausting
	// the connection pool (max 25 connections) and causing deadlocks.
	rows, err := r.db.QueryContext(ctx,
		`SELECT id, user_id, name, path, size, mime_type, checksum, storage_key, encrypted, version, parent_id, is_directory, created_at, updated_at, deleted_at
		 FROM files WHERE user_id = $1 AND deleted_at IS NULL ORDER BY name`,
		userID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to query files: %w", err)
	}
	

	var files []models.File
	for rows.Next() {
		var file models.File
		err := rows.Scan(&file.ID, &file.UserID, &file.Name, &file.Path, &file.Size,
			&file.MimeType, &file.Checksum, &file.StorageKey, &file.Encrypted,
			&file.Version, &file.ParentID, &file.IsDirectory, &file.CreatedAt,
			&file.UpdatedAt, &file.DeletedAt)
		if err != nil {
			
			return nil, fmt.Errorf("failed to scan file: %w", err)
		}
		files = append(files, file)
	}

	
	rows.Close()

	return files, nil
}

// GetByPath retrieves a file by path
func (r *FileRepository) GetByPath(ctx context.Context, userID uuid.UUID, path string) (*models.File, error) {
	var file models.File
	err := r.db.QueryRowContext(ctx,
		`SELECT id, user_id, name, path, size, mime_type, checksum, storage_key, encrypted, version, parent_id, is_directory, created_at, updated_at, deleted_at
		 FROM files WHERE user_id = $1 AND path = $2 AND deleted_at IS NULL`,
		userID, path,
	).Scan(&file.ID, &file.UserID, &file.Name, &file.Path, &file.Size,
		&file.MimeType, &file.Checksum, &file.StorageKey, &file.Encrypted,
		&file.Version, &file.ParentID, &file.IsDirectory, &file.CreatedAt,
		&file.UpdatedAt, &file.DeletedAt)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get file by path: %w", err)
	}

	return &file, nil
}

// Update updates a file record
func (r *FileRepository) Update(ctx context.Context, file *models.File) error {
	file.UpdatedAt = time.Now()
	_, err := r.db.ExecContext(ctx,
		`UPDATE files SET name = $1, path = $2, size = $3, mime_type = $4, checksum = $5, storage_key = $6, version = $7, updated_at = $8
		 WHERE id = $9`,
		file.Name, file.Path, file.Size, file.MimeType, file.Checksum,
		file.StorageKey, file.Version, file.UpdatedAt, file.ID,
	)
	return err
}

// Delete soft deletes a file
func (r *FileRepository) Delete(ctx context.Context, id uuid.UUID) error {
	now := time.Now()
	_, err := r.db.ExecContext(ctx,
		"UPDATE files SET deleted_at = $1 WHERE id = $2",
		now, id,
	)
	return err
}

// ListDirectory lists files in a directory
func (r *FileRepository) ListDirectory(ctx context.Context, userID uuid.UUID, parentID *uuid.UUID) ([]models.File, error) {
	var rows *sql.Rows
	var err error

	if parentID == nil {
		rows, err = r.db.QueryContext(ctx,
			`SELECT id, user_id, name, path, size, mime_type, checksum, storage_key, encrypted, version, parent_id, is_directory, created_at, updated_at, deleted_at
			 FROM files WHERE user_id = $1 AND parent_id IS NULL AND deleted_at IS NULL ORDER BY is_directory DESC, name`,
			userID,
		)
	} else {
		rows, err = r.db.QueryContext(ctx,
			`SELECT id, user_id, name, path, size, mime_type, checksum, storage_key, encrypted, version, parent_id, is_directory, created_at, updated_at, deleted_at
			 FROM files WHERE user_id = $1 AND parent_id = $2 AND deleted_at IS NULL ORDER BY is_directory DESC, name`,
			userID, parentID,
		)
	}

	if err != nil {
		return nil, fmt.Errorf("failed to list directory: %w", err)
	}
	defer rows.Close()

	var files []models.File
	for rows.Next() {
		var file models.File
		err := rows.Scan(&file.ID, &file.UserID, &file.Name, &file.Path, &file.Size,
			&file.MimeType, &file.Checksum, &file.StorageKey, &file.Encrypted,
			&file.Version, &file.ParentID, &file.IsDirectory, &file.CreatedAt,
			&file.UpdatedAt, &file.DeletedAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan file: %w", err)
		}
		files = append(files, file)
	}

	return files, rows.Err()
}

// Search searches for files by name
func (r *FileRepository) Search(ctx context.Context, userID uuid.UUID, query string, limit int) ([]models.File, error) {
	
	// for LIKE pattern matching
	rows, err := r.db.QueryContext(ctx,
		fmt.Sprintf(`SELECT id, user_id, name, path, size, mime_type, checksum, storage_key, encrypted, version, parent_id, is_directory, created_at, updated_at, deleted_at
		 FROM files WHERE user_id = $1 AND name ILIKE '%%%s%%' AND deleted_at IS NULL ORDER BY name LIMIT $2`, query),
		userID, limit,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to search files: %w", err)
	}
	defer rows.Close()

	var files []models.File
	for rows.Next() {
		var file models.File
		err := rows.Scan(&file.ID, &file.UserID, &file.Name, &file.Path, &file.Size,
			&file.MimeType, &file.Checksum, &file.StorageKey, &file.Encrypted,
			&file.Version, &file.ParentID, &file.IsDirectory, &file.CreatedAt,
			&file.UpdatedAt, &file.DeletedAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan file: %w", err)
		}
		files = append(files, file)
	}

	return files, rows.Err()
}

// GetStorageUsed calculates total storage used by a user
func (r *FileRepository) GetStorageUsed(ctx context.Context, userID uuid.UUID) (int64, error) {
	var total sql.NullInt64
	err := r.db.QueryRowContext(ctx,
		"SELECT SUM(size) FROM files WHERE user_id = $1 AND deleted_at IS NULL",
		userID,
	).Scan(&total)

	if err != nil {
		return 0, fmt.Errorf("failed to get storage used: %w", err)
	}

	if !total.Valid {
		return 0, nil
	}

	return total.Int64, nil
}

// BulkCreate creates multiple files in a single transaction
func (r *FileRepository) BulkCreate(ctx context.Context, files []models.File) error {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	
	for _, file := range files {
		stmt, err := tx.PrepareContext(ctx,
			`INSERT INTO files (id, user_id, name, path, size, mime_type, checksum, storage_key, encrypted, version, parent_id, is_directory, created_at, updated_at)
			 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)`)
		if err != nil {
			return fmt.Errorf("failed to prepare statement: %w", err)
		}
		

		_, err = stmt.ExecContext(ctx,
			file.ID, file.UserID, file.Name, file.Path, file.Size, file.MimeType,
			file.Checksum, file.StorageKey, file.Encrypted, file.Version,
			file.ParentID, file.IsDirectory, file.CreatedAt, file.UpdatedAt,
		)
		if err != nil {
			return fmt.Errorf("failed to insert file: %w", err)
		}
	}

	return tx.Commit()
}
