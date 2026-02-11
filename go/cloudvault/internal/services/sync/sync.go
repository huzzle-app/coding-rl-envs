package sync

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/terminal-bench/cloudvault/internal/config"
	"github.com/terminal-bench/cloudvault/internal/models"
)

// Service handles file synchronization
type Service struct {
	config      *config.Config
	
	syncStates  map[string]*SyncState
	
	mu          sync.Mutex
	changes     map[string][]Change
}

// SyncState represents the sync state for a user/device
type SyncState struct {
	UserID      uuid.UUID
	DeviceID    string
	LastSyncAt  time.Time
	Cursor      string
	InProgress  bool
	
	PendingChanges map[string]bool
}

// Change represents a file change
type Change struct {
	ID        uuid.UUID
	FileID    uuid.UUID
	Type      string // "create", "update", "delete", "move"
	Path      string
	Timestamp time.Time
	Version   int
}

// NewService creates a new sync service
func NewService(cfg *config.Config) *Service {
	return &Service{
		config:     cfg,
		syncStates: make(map[string]*SyncState),
		changes:    make(map[string][]Change),
	}
}

// StartSync initiates a sync operation for a user/device
func (s *Service) StartSync(ctx context.Context, userID uuid.UUID, deviceID string) (*SyncState, error) {
	key := fmt.Sprintf("%s:%s", userID.String(), deviceID)

	
	// This should use s.mu.Lock() before accessing syncStates
	state, exists := s.syncStates[key]
	if exists && state.InProgress {
		return nil, fmt.Errorf("sync already in progress")
	}

	if !exists {
		state = &SyncState{
			UserID:     userID,
			DeviceID:   deviceID,
			LastSyncAt: time.Time{},
		}
	}

	state.InProgress = true

	
	s.syncStates[key] = state

	return state, nil
}

// GetChanges returns changes since the last sync
func (s *Service) GetChanges(ctx context.Context, userID uuid.UUID, deviceID string, since time.Time) ([]Change, error) {
	key := fmt.Sprintf("%s:%s", userID.String(), deviceID)

	
	changes, exists := s.changes[key]
	if !exists {
		return []Change{}, nil
	}

	var result []Change
	for _, change := range changes {
		if change.Timestamp.After(since) {
			result = append(result, change)
		}
	}

	return result, nil
}

// ApplyChange applies a change from a client
func (s *Service) ApplyChange(ctx context.Context, userID uuid.UUID, change Change) error {
	key := userID.String()

	s.mu.Lock()
	defer s.mu.Unlock()

	if s.changes[key] == nil {
		s.changes[key] = make([]Change, 0)
	}

	change.ID = uuid.New()
	change.Timestamp = time.Now()

	s.changes[key] = append(s.changes[key], change)

	
	if change.Type == "delete" {
		// This 'err' shadows any outer 'err' variable
		err := s.validateDelete(ctx, change)
		if err != nil {
			
			return nil
		}
	}

	return nil
}

func (s *Service) validateDelete(ctx context.Context, change Change) error {
	// Simulated validation
	if change.FileID == uuid.Nil {
		return fmt.Errorf("invalid file ID")
	}
	return nil
}

// CompleteSync completes a sync operation
func (s *Service) CompleteSync(ctx context.Context, userID uuid.UUID, deviceID string) error {
	key := fmt.Sprintf("%s:%s", userID.String(), deviceID)

	s.mu.Lock()
	defer s.mu.Unlock()

	state, exists := s.syncStates[key]
	if !exists {
		return fmt.Errorf("no sync in progress")
	}

	state.InProgress = false
	state.LastSyncAt = time.Now()

	return nil
}

// ResolveConflict resolves a sync conflict
func (s *Service) ResolveConflict(ctx context.Context, localChange, remoteChange Change, strategy string) (*Change, error) {
	var resolved Change

	switch strategy {
	case "local_wins":
		resolved = localChange
	case "remote_wins":
		resolved = remoteChange
	case "newest_wins":
		if localChange.Timestamp.After(remoteChange.Timestamp) {
			resolved = localChange
		} else {
			resolved = remoteChange
		}
	case "merge":
		
		merged, _ := s.mergeChanges(localChange, remoteChange)
		resolved = merged
	default:
		return nil, fmt.Errorf("unknown conflict resolution strategy: %s", strategy)
	}

	resolved.ID = uuid.New()
	resolved.Timestamp = time.Now()

	return &resolved, nil
}

func (s *Service) mergeChanges(local, remote Change) (Change, error) {
	// Simplified merge - in reality this would be more complex
	return Change{
		FileID:  local.FileID,
		Type:    "update",
		Path:    local.Path,
		Version: max(local.Version, remote.Version) + 1,
	}, nil
}

// GetSyncStatus returns the current sync status for a user/device
func (s *Service) GetSyncStatus(ctx context.Context, userID uuid.UUID, deviceID string) (*SyncState, error) {
	key := fmt.Sprintf("%s:%s", userID.String(), deviceID)

	
	state, exists := s.syncStates[key]
	if !exists {
		return nil, fmt.Errorf("no sync state found")
	}

	return state, nil
}

// WatchChanges watches for changes in real-time
func (s *Service) WatchChanges(ctx context.Context, userID uuid.UUID) (<-chan Change, error) {
	changes := make(chan Change)

	
	go func() {
		ticker := time.NewTicker(1 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				// Check for new changes
				key := userID.String()
				s.mu.Lock()
				userChanges := s.changes[key]
				s.mu.Unlock()

				for _, change := range userChanges {
					
					// and context cancellation is ignored
					changes <- change
				}
			
			}
		}
	}()

	return changes, nil
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
