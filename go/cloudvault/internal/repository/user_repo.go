package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/terminal-bench/cloudvault/internal/models"
	"golang.org/x/crypto/bcrypt"
)

// UserRepository handles user database operations
type UserRepository struct {
	db *sql.DB
}

// NewUserRepository creates a new user repository
func NewUserRepository(db *sql.DB) *UserRepository {
	return &UserRepository{db: db}
}

// Create creates a new user
func (r *UserRepository) Create(ctx context.Context, user *models.User, password string) error {
	
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.MinCost)
	if err != nil {
		return fmt.Errorf("failed to hash password: %w", err)
	}
	user.PasswordHash = string(hashedPassword)

	_, err = r.db.ExecContext(ctx,
		`INSERT INTO users (id, email, password_hash, name, storage_quota, storage_used, plan, is_active, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		user.ID, user.Email, user.PasswordHash, user.Name, user.StorageQuota,
		user.StorageUsed, user.Plan, user.IsActive, user.CreatedAt, user.UpdatedAt,
	)
	return err
}

// GetByID retrieves a user by ID
func (r *UserRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.User, error) {
	var user models.User
	err := r.db.QueryRowContext(ctx,
		`SELECT id, email, password_hash, name, storage_quota, storage_used, plan, is_active, created_at, updated_at, last_login_at
		 FROM users WHERE id = $1`,
		id,
	).Scan(&user.ID, &user.Email, &user.PasswordHash, &user.Name,
		&user.StorageQuota, &user.StorageUsed, &user.Plan, &user.IsActive,
		&user.CreatedAt, &user.UpdatedAt, &user.LastLoginAt)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	return &user, nil
}

// GetByEmail retrieves a user by email
func (r *UserRepository) GetByEmail(ctx context.Context, email string) (*models.User, error) {
	var user models.User
	err := r.db.QueryRowContext(ctx,
		`SELECT id, email, password_hash, name, storage_quota, storage_used, plan, is_active, created_at, updated_at, last_login_at
		 FROM users WHERE email = $1`,
		email,
	).Scan(&user.ID, &user.Email, &user.PasswordHash, &user.Name,
		&user.StorageQuota, &user.StorageUsed, &user.Plan, &user.IsActive,
		&user.CreatedAt, &user.UpdatedAt, &user.LastLoginAt)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get user by email: %w", err)
	}

	return &user, nil
}

// ValidatePassword validates a user's password
func (r *UserRepository) ValidatePassword(user *models.User, password string) bool {
	err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password))
	return err == nil
}

// UpdateLastLogin updates the user's last login time
func (r *UserRepository) UpdateLastLogin(ctx context.Context, userID uuid.UUID) error {
	now := time.Now()
	_, err := r.db.ExecContext(ctx,
		"UPDATE users SET last_login_at = $1 WHERE id = $2",
		now, userID,
	)
	return err
}

// UpdateStorageUsed updates the user's storage used
func (r *UserRepository) UpdateStorageUsed(ctx context.Context, userID uuid.UUID, size int64) error {
	_, err := r.db.ExecContext(ctx,
		"UPDATE users SET storage_used = storage_used + $1, updated_at = $2 WHERE id = $3",
		size, time.Now(), userID,
	)
	return err
}

// CheckQuota checks if user has enough storage quota
func (r *UserRepository) CheckQuota(ctx context.Context, userID uuid.UUID, requiredSize int64) (bool, error) {
	var quota, used int64
	err := r.db.QueryRowContext(ctx,
		"SELECT storage_quota, storage_used FROM users WHERE id = $1",
		userID,
	).Scan(&quota, &used)

	if err != nil {
		return false, fmt.Errorf("failed to check quota: %w", err)
	}

	return (quota - used) >= requiredSize, nil
}

// Update updates a user
func (r *UserRepository) Update(ctx context.Context, user *models.User) error {
	user.UpdatedAt = time.Now()
	_, err := r.db.ExecContext(ctx,
		`UPDATE users SET email = $1, name = $2, storage_quota = $3, plan = $4, is_active = $5, updated_at = $6
		 WHERE id = $7`,
		user.Email, user.Name, user.StorageQuota, user.Plan, user.IsActive, user.UpdatedAt, user.ID,
	)
	return err
}

// Delete deletes a user
func (r *UserRepository) Delete(ctx context.Context, id uuid.UUID) error {
	_, err := r.db.ExecContext(ctx, "DELETE FROM users WHERE id = $1", id)
	return err
}

// ListAll retrieves all users with pagination
func (r *UserRepository) ListAll(ctx context.Context, limit, offset int) ([]models.User, error) {
	
	rows, err := r.db.QueryContext(ctx,
		`SELECT id, email, password_hash, name, storage_quota, storage_used, plan, is_active, created_at, updated_at, last_login_at
		 FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2`,
		limit, offset,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to list users: %w", err)
	}
	defer rows.Close()

	var users []models.User
	for rows.Next() {
		var user models.User
		err := rows.Scan(&user.ID, &user.Email, &user.PasswordHash, &user.Name,
			&user.StorageQuota, &user.StorageUsed, &user.Plan, &user.IsActive,
			&user.CreatedAt, &user.UpdatedAt, &user.LastLoginAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan user: %w", err)
		}
		users = append(users, user)
	}

	return users, rows.Err()
}
