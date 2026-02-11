package models

import (
	"time"

	"github.com/google/uuid"
)

// File represents a file in the system
type File struct {
	ID          uuid.UUID  `json:"id" db:"id"`
	UserID      uuid.UUID  `json:"user_id" db:"user_id"`
	Name        string     `json:"name" db:"name"`
	Path        string     `json:"path" db:"path"`
	Size        int64      `json:"size" db:"size"`
	MimeType    string     `json:"mime_type" db:"mime_type"`
	Checksum    string     `json:"checksum" db:"checksum"`
	StorageKey  string     `json:"storage_key" db:"storage_key"`
	Encrypted   bool       `json:"encrypted" db:"encrypted"`
	Version     int        `json:"version" db:"version"`
	ParentID    *uuid.UUID `json:"parent_id,omitempty" db:"parent_id"`
	IsDirectory bool       `json:"is_directory" db:"is_directory"`
	CreatedAt   time.Time  `json:"created_at" db:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at" db:"updated_at"`
	DeletedAt   *time.Time `json:"deleted_at,omitempty" db:"deleted_at"`
}

// FileVersion represents a version of a file
type FileVersion struct {
	ID        uuid.UUID `json:"id" db:"id"`
	FileID    uuid.UUID `json:"file_id" db:"file_id"`
	Version   int       `json:"version" db:"version"`
	Size      int64     `json:"size" db:"size"`
	Checksum  string    `json:"checksum" db:"checksum"`
	StorageKey string   `json:"storage_key" db:"storage_key"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
	CreatedBy uuid.UUID `json:"created_by" db:"created_by"`
}

// FileChunk represents a chunk of a file for chunked uploads
type FileChunk struct {
	ID         uuid.UUID `json:"id" db:"id"`
	UploadID   uuid.UUID `json:"upload_id" db:"upload_id"`
	ChunkIndex int       `json:"chunk_index" db:"chunk_index"`
	Size       int64     `json:"size" db:"size"`
	Checksum   string    `json:"checksum" db:"checksum"`
	StorageKey string    `json:"storage_key" db:"storage_key"`
	CreatedAt  time.Time `json:"created_at" db:"created_at"`
}

// UploadSession represents an in-progress chunked upload
type UploadSession struct {
	ID           uuid.UUID `json:"id" db:"id"`
	UserID       uuid.UUID `json:"user_id" db:"user_id"`
	FileName     string    `json:"file_name" db:"file_name"`
	FileSize     int64     `json:"file_size" db:"file_size"`
	ChunkSize    int       `json:"chunk_size" db:"chunk_size"`
	TotalChunks  int       `json:"total_chunks" db:"total_chunks"`
	UploadedChunks []int   `json:"uploaded_chunks" db:"-"`
	Status       string    `json:"status" db:"status"`
	CreatedAt    time.Time `json:"created_at" db:"created_at"`
	ExpiresAt    time.Time `json:"expires_at" db:"expires_at"`
}
