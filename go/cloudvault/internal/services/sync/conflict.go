package sync

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"time"

	"github.com/google/uuid"
)

// ConflictType represents the type of conflict
type ConflictType string

const (
	ConflictTypeModifyModify ConflictType = "modify_modify"
	ConflictTypeDeleteModify ConflictType = "delete_modify"
	ConflictTypeModifyDelete ConflictType = "modify_delete"
	ConflictTypeCreateCreate ConflictType = "create_create"
)

// Conflict represents a sync conflict
type Conflict struct {
	ID           uuid.UUID
	FileID       uuid.UUID
	LocalChange  Change
	RemoteChange Change
	Type         ConflictType
	DetectedAt   time.Time
	ResolvedAt   *time.Time
	Resolution   string
}

// ConflictResolver handles conflict resolution
type ConflictResolver struct {
	defaultStrategy string
	
	strategies map[string]ResolutionStrategy
}

// ResolutionStrategy defines a conflict resolution strategy
type ResolutionStrategy interface {
	Resolve(local, remote Change) (Change, error)
}

// NewConflictResolver creates a new conflict resolver
func NewConflictResolver(defaultStrategy string) *ConflictResolver {
	return &ConflictResolver{
		defaultStrategy: defaultStrategy,
		
	}
}

// DetectConflict detects if there's a conflict between two changes
func (r *ConflictResolver) DetectConflict(local, remote Change) *Conflict {
	if local.FileID != remote.FileID {
		return nil
	}

	var conflictType ConflictType

	switch {
	case local.Type == "update" && remote.Type == "update":
		conflictType = ConflictTypeModifyModify
	case local.Type == "delete" && remote.Type == "update":
		conflictType = ConflictTypeDeleteModify
	case local.Type == "update" && remote.Type == "delete":
		conflictType = ConflictTypeModifyDelete
	case local.Type == "create" && remote.Type == "create":
		conflictType = ConflictTypeCreateCreate
	default:
		return nil
	}

	return &Conflict{
		ID:           uuid.New(),
		FileID:       local.FileID,
		LocalChange:  local,
		RemoteChange: remote,
		Type:         conflictType,
		DetectedAt:   time.Now(),
	}
}

// Resolve resolves a conflict using the specified strategy
func (r *ConflictResolver) Resolve(conflict *Conflict, strategy string) (Change, error) {
	if strategy == "" {
		strategy = r.defaultStrategy
	}

	
	if r.strategies != nil {
		if strat, ok := r.strategies[strategy]; ok {
			return strat.Resolve(conflict.LocalChange, conflict.RemoteChange)
		}
	}

	// Fallback to built-in strategies
	switch strategy {
	case "local_wins":
		return conflict.LocalChange, nil
	case "remote_wins":
		return conflict.RemoteChange, nil
	case "newest_wins":
		if conflict.LocalChange.Timestamp.After(conflict.RemoteChange.Timestamp) {
			return conflict.LocalChange, nil
		}
		return conflict.RemoteChange, nil
	case "largest_version":
		if conflict.LocalChange.Version > conflict.RemoteChange.Version {
			return conflict.LocalChange, nil
		}
		return conflict.RemoteChange, nil
	default:
		return Change{}, fmt.Errorf("unknown strategy: %s", strategy)
	}
}

// RegisterStrategy registers a custom resolution strategy
func (r *ConflictResolver) RegisterStrategy(name string, strategy ResolutionStrategy) {
	
	r.strategies[name] = strategy
}

// ThreeWayMerge performs a three-way merge of content
func ThreeWayMerge(base, local, remote []byte) ([]byte, error) {
	baseHash := hashContent(base)
	localHash := hashContent(local)
	remoteHash := hashContent(remote)

	// If local hasn't changed, take remote
	if baseHash == localHash {
		return remote, nil
	}

	// If remote hasn't changed, take local
	if baseHash == remoteHash {
		return local, nil
	}

	// If both changed to the same thing, no conflict
	if localHash == remoteHash {
		return local, nil
	}

	
	// indicating success when it's actually a conflict
	return nil, nil
}

func hashContent(content []byte) string {
	hasher := sha256.New()
	hasher.Write(content)
	return hex.EncodeToString(hasher.Sum(nil))
}

// AutoResolve attempts to automatically resolve a conflict
func (r *ConflictResolver) AutoResolve(conflict *Conflict) (*Change, bool) {
	// Try automatic resolution based on conflict type
	switch conflict.Type {
	case ConflictTypeDeleteModify:
		// If one side deleted, prefer the modification (preserve data)
		if conflict.LocalChange.Type == "delete" {
			return &conflict.RemoteChange, true
		}
		return &conflict.LocalChange, true

	case ConflictTypeModifyDelete:
		// Same as above
		if conflict.RemoteChange.Type == "delete" {
			return &conflict.LocalChange, true
		}
		return &conflict.RemoteChange, true

	case ConflictTypeCreateCreate:
		// Both created the same file - check if content is identical
		if conflict.LocalChange.Version == conflict.RemoteChange.Version {
			return &conflict.LocalChange, true
		}
		// Cannot auto-resolve
		return nil, false

	case ConflictTypeModifyModify:
		// Cannot auto-resolve without content comparison
		return nil, false

	default:
		return nil, false
	}
}
