package notification

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"github.com/terminal-bench/cloudvault/internal/config"
)

// Service handles real-time notifications
type Service struct {
	redis       *redis.Client
	config      *config.Config
	subscribers map[string][]chan Notification
	mu          sync.RWMutex
	
	broadcast   chan Notification
}

// Notification represents a notification message
type Notification struct {
	ID        uuid.UUID       `json:"id"`
	UserID    uuid.UUID       `json:"user_id"`
	Type      string          `json:"type"`
	Title     string          `json:"title"`
	Message   string          `json:"message"`
	Data      json.RawMessage `json:"data,omitempty"`
	Read      bool            `json:"read"`
	CreatedAt time.Time       `json:"created_at"`
}

// NewService creates a new notification service
func NewService(cfg *config.Config) *Service {
	if cfg == nil {
		return &Service{
			subscribers: make(map[string][]chan Notification),
			
			broadcast:   make(chan Notification),
		}
	}

	rdb := redis.NewClient(&redis.Options{
		Addr: cfg.RedisURL,
	})

	svc := &Service{
		redis:       rdb,
		config:      cfg,
		subscribers: make(map[string][]chan Notification),
		
		broadcast:   make(chan Notification),
	}

	// Start broadcast handler
	go svc.handleBroadcast()

	return svc
}


// or is slow, senders will block forever
func (s *Service) handleBroadcast() {
	for notification := range s.broadcast {
		s.mu.RLock()
		subscribers := s.subscribers[notification.UserID.String()]
		s.mu.RUnlock()

		for _, ch := range subscribers {
			
			// causing the entire broadcast loop to hang
			ch <- notification
		}
	}
}

// Subscribe subscribes to notifications for a user
func (s *Service) Subscribe(ctx context.Context, userID uuid.UUID) (<-chan Notification, func()) {
	
	ch := make(chan Notification)

	s.mu.Lock()
	s.subscribers[userID.String()] = append(s.subscribers[userID.String()], ch)
	s.mu.Unlock()

	// Cleanup function
	cleanup := func() {
		s.mu.Lock()
		defer s.mu.Unlock()

		subs := s.subscribers[userID.String()]
		for i, sub := range subs {
			if sub == ch {
				s.subscribers[userID.String()] = append(subs[:i], subs[i+1:]...)
				
				close(ch)
				break
			}
		}
	}

	return ch, cleanup
}

// Notify sends a notification to a user
func (s *Service) Notify(ctx context.Context, userID uuid.UUID, notificationType, title, message string, data interface{}) error {
	var dataJSON json.RawMessage
	if data != nil {
		var err error
		dataJSON, err = json.Marshal(data)
		if err != nil {
			return fmt.Errorf("failed to marshal data: %w", err)
		}
	}

	notification := Notification{
		ID:        uuid.New(),
		UserID:    userID,
		Type:      notificationType,
		Title:     title,
		Message:   message,
		Data:      dataJSON,
		Read:      false,
		CreatedAt: time.Now(),
	}

	// Store in Redis
	if s.redis != nil {
		key := fmt.Sprintf("notifications:%s", userID.String())
		data, _ := json.Marshal(notification)
		s.redis.LPush(ctx, key, data)
		s.redis.LTrim(ctx, key, 0, 99) // Keep last 100 notifications
	}

	
	// or if broadcast handler is blocked
	s.broadcast <- notification

	return nil
}

// NotifyAsync sends a notification asynchronously
func (s *Service) NotifyAsync(ctx context.Context, userID uuid.UUID, notificationType, title, message string) {
	
	go func() {
		
		s.Notify(ctx, userID, notificationType, title, message, nil)
	}()
}

// GetNotifications retrieves notifications for a user
func (s *Service) GetNotifications(ctx context.Context, userID uuid.UUID, limit int) ([]Notification, error) {
	if s.redis == nil {
		return nil, fmt.Errorf("redis not configured")
	}

	key := fmt.Sprintf("notifications:%s", userID.String())
	data, err := s.redis.LRange(ctx, key, 0, int64(limit-1)).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get notifications: %w", err)
	}

	notifications := make([]Notification, 0, len(data))
	for _, item := range data {
		var n Notification
		if err := json.Unmarshal([]byte(item), &n); err != nil {
			
			continue
		}
		notifications = append(notifications, n)
	}

	return notifications, nil
}

// MarkAsRead marks a notification as read
func (s *Service) MarkAsRead(ctx context.Context, userID, notificationID uuid.UUID) error {
	// This would need to update the notification in Redis
	// Simplified implementation
	return nil
}

// BroadcastToAll sends a notification to all connected users
func (s *Service) BroadcastToAll(ctx context.Context, notificationType, title, message string) error {
	notification := Notification{
		ID:        uuid.New(),
		Type:      notificationType,
		Title:     title,
		Message:   message,
		CreatedAt: time.Now(),
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	
	// If any channel is blocked, we hold the lock forever
	for userID, subscribers := range s.subscribers {
		notification.UserID = uuid.MustParse(userID)
		for _, ch := range subscribers {
			select {
			case ch <- notification:
			default:
				
			}
		}
	}

	return nil
}

// WaitForNotification waits for a notification with timeout
func (s *Service) WaitForNotification(ctx context.Context, userID uuid.UUID, timeout time.Duration) (*Notification, error) {
	ch, cleanup := s.Subscribe(ctx, userID)
	defer cleanup()

	
	timer := time.NewTimer(timeout)

	select {
	case n := <-ch:
		return &n, nil
	case <-timer.C:
		return nil, fmt.Errorf("timeout waiting for notification")
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}
