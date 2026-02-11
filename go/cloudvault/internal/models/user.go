package models

import (
	"time"

	"github.com/google/uuid"
)

// User represents a user in the system
type User struct {
	ID           uuid.UUID  `json:"id" db:"id"`
	Email        string     `json:"email" db:"email"`
	PasswordHash string     `json:"-" db:"password_hash"`
	Name         string     `json:"name" db:"name"`
	StorageQuota int64      `json:"storage_quota" db:"storage_quota"`
	StorageUsed  int64      `json:"storage_used" db:"storage_used"`
	Plan         string     `json:"plan" db:"plan"`
	IsActive     bool       `json:"is_active" db:"is_active"`
	CreatedAt    time.Time  `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time  `json:"updated_at" db:"updated_at"`
	LastLoginAt  *time.Time `json:"last_login_at,omitempty" db:"last_login_at"`
}

// UserSettings represents user preferences
type UserSettings struct {
	UserID              uuid.UUID `json:"user_id" db:"user_id"`
	AutoSync            bool      `json:"auto_sync" db:"auto_sync"`
	SyncInterval        int       `json:"sync_interval" db:"sync_interval"` // seconds
	ConflictResolution  string    `json:"conflict_resolution" db:"conflict_resolution"`
	NotificationsEnabled bool     `json:"notifications_enabled" db:"notifications_enabled"`
	TwoFactorEnabled    bool      `json:"two_factor_enabled" db:"two_factor_enabled"`
	UpdatedAt           time.Time `json:"updated_at" db:"updated_at"`
}

// Session represents an active user session
type Session struct {
	ID        uuid.UUID `json:"id" db:"id"`
	UserID    uuid.UUID `json:"user_id" db:"user_id"`
	Token     string    `json:"-" db:"token"`
	DeviceID  string    `json:"device_id" db:"device_id"`
	UserAgent string    `json:"user_agent" db:"user_agent"`
	IPAddress string    `json:"ip_address" db:"ip_address"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
	ExpiresAt time.Time `json:"expires_at" db:"expires_at"`
}
