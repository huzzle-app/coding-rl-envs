package models

import (
	"time"

	"github.com/google/uuid"
)

// Share represents a file share
type Share struct {
	ID         uuid.UUID  `json:"id" db:"id"`
	FileID     uuid.UUID  `json:"file_id" db:"file_id"`
	OwnerID    uuid.UUID  `json:"owner_id" db:"owner_id"`
	ShareType  string     `json:"share_type" db:"share_type"` // "link", "user", "group"
	Permission string     `json:"permission" db:"permission"` // "view", "edit", "admin"
	Token      string     `json:"token,omitempty" db:"token"`
	Password   *string    `json:"-" db:"password"`
	MaxUses    *int       `json:"max_uses,omitempty" db:"max_uses"`
	UseCount   int        `json:"use_count" db:"use_count"`
	ExpiresAt  *time.Time `json:"expires_at,omitempty" db:"expires_at"`
	CreatedAt  time.Time  `json:"created_at" db:"created_at"`
	UpdatedAt  time.Time  `json:"updated_at" db:"updated_at"`
}

// ShareRecipient represents a user or group that a file is shared with
type ShareRecipient struct {
	ID            uuid.UUID `json:"id" db:"id"`
	ShareID       uuid.UUID `json:"share_id" db:"share_id"`
	RecipientType string    `json:"recipient_type" db:"recipient_type"` // "user", "group"
	RecipientID   uuid.UUID `json:"recipient_id" db:"recipient_id"`
	CreatedAt     time.Time `json:"created_at" db:"created_at"`
}

// ShareAccess represents an access log entry for a share
type ShareAccess struct {
	ID        uuid.UUID `json:"id" db:"id"`
	ShareID   uuid.UUID `json:"share_id" db:"share_id"`
	AccessedBy *uuid.UUID `json:"accessed_by,omitempty" db:"accessed_by"`
	IPAddress string    `json:"ip_address" db:"ip_address"`
	UserAgent string    `json:"user_agent" db:"user_agent"`
	Action    string    `json:"action" db:"action"` // "view", "download", "edit"
	CreatedAt time.Time `json:"created_at" db:"created_at"`
}
