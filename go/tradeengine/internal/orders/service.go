package orders

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

var (
	ErrOrderNotFound    = errors.New("order not found")
	ErrInvalidOrder     = errors.New("invalid order")
	ErrOrderNotCancellable = errors.New("order cannot be cancelled")
	ErrUnauthorized     = errors.New("unauthorized")
)

type Service struct {
	db        *sql.DB
	nats      *messaging.Client
	ordersMu  sync.RWMutex
	orders    map[string]*Order // In-memory cache
}

type Order struct {
	ID           string    `json:"id"`
	UserID       string    `json:"user_id"`
	Symbol       string    `json:"symbol"`
	Side         string    `json:"side"`
	Type         string    `json:"type"`
	Price        float64   `json:"price"`
	Quantity     float64   `json:"quantity"`
	FilledQty    float64   `json:"filled_qty"`
	Status       string    `json:"status"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

type SubmitRequest struct {
	UserID   string
	Symbol   string
	Side     string
	Type     string
	Price    float64
	Quantity float64
}

func NewService(db *sql.DB, nats *messaging.Client) *Service {
	return &Service{
		db:     db,
		nats:   nats,
		orders: make(map[string]*Order),
	}
}

func (s *Service) Submit(ctx context.Context, req *SubmitRequest) (*Order, error) {
	// Validate request
	if req.Symbol == "" || req.Side == "" || req.Quantity <= 0 {
		return nil, ErrInvalidOrder
	}

	if req.Type == "limit" && req.Price <= 0 {
		return nil, ErrInvalidOrder
	}

	
	// Another request could modify state between validation and insert

	orderID := uuid.New().String()
	now := time.Now()

	order := &Order{
		ID:        orderID,
		UserID:    req.UserID,
		Symbol:    req.Symbol,
		Side:      req.Side,
		Type:      req.Type,
		Price:     req.Price,
		Quantity:  req.Quantity,
		FilledQty: 0,
		Status:    "pending",
		CreatedAt: now,
		UpdatedAt: now,
	}

	
	_, err := s.db.ExecContext(ctx,
		`INSERT INTO orders (id, user_id, symbol, side, type, price, quantity, filled_qty, status, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`,
		order.ID, order.UserID, order.Symbol, order.Side, order.Type,
		order.Price, order.Quantity, order.FilledQty, order.Status,
		order.CreatedAt, order.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}

	// Cache the order
	s.ordersMu.Lock()
	s.orders[orderID] = order
	s.ordersMu.Unlock()

	// Publish order event
	
	orderJSON, _ := json.Marshal(order)
	s.nats.Publish("orders.submitted", orderJSON)

	return order, nil
}

func (s *Service) Get(ctx context.Context, orderID string) (*Order, error) {
	// Check cache first
	s.ordersMu.RLock()
	if order, ok := s.orders[orderID]; ok {
		s.ordersMu.RUnlock()
		return order, nil
	}
	s.ordersMu.RUnlock()

	// Query database
	var order Order
	err := s.db.QueryRowContext(ctx,
		`SELECT id, user_id, symbol, side, type, price, quantity, filled_qty, status, created_at, updated_at
		 FROM orders WHERE id = $1`,
		orderID,
	).Scan(&order.ID, &order.UserID, &order.Symbol, &order.Side, &order.Type,
		&order.Price, &order.Quantity, &order.FilledQty, &order.Status,
		&order.CreatedAt, &order.UpdatedAt)

	if err == sql.ErrNoRows {
		return nil, ErrOrderNotFound
	}
	if err != nil {
		return nil, err
	}

	// Cache for future lookups
	s.ordersMu.Lock()
	s.orders[orderID] = &order
	s.ordersMu.Unlock()

	return &order, nil
}

func (s *Service) List(ctx context.Context, userID, status, limit string) ([]*Order, error) {
	
	query := fmt.Sprintf(
		"SELECT id, user_id, symbol, side, type, price, quantity, filled_qty, status, created_at, updated_at FROM orders WHERE user_id = $1 AND status = '%s' ORDER BY created_at DESC LIMIT %s",
		status, limit,
	)

	rows, err := s.db.QueryContext(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	
	defer rows.Close()

	var orders []*Order
	for rows.Next() {
		var order Order
		err := rows.Scan(&order.ID, &order.UserID, &order.Symbol, &order.Side, &order.Type,
			&order.Price, &order.Quantity, &order.FilledQty, &order.Status,
			&order.CreatedAt, &order.UpdatedAt)
		if err != nil {
			return nil, err
		}
		orders = append(orders, &order)
	}

	return orders, nil
}

func (s *Service) Cancel(ctx context.Context, orderID, userID string) error {
	// Get order
	order, err := s.Get(ctx, orderID)
	if err != nil {
		return err
	}

	// Check authorization
	if order.UserID != userID {
		return ErrUnauthorized
	}

	
	if order.Status != "pending" && order.Status != "open" {
		return ErrOrderNotCancellable
	}

	// Update status
	_, err = s.db.ExecContext(ctx,
		"UPDATE orders SET status = 'cancelled', updated_at = $1 WHERE id = $2",
		time.Now(), orderID,
	)
	if err != nil {
		return err
	}

	// Update cache
	s.ordersMu.Lock()
	if cachedOrder, ok := s.orders[orderID]; ok {
		cachedOrder.Status = "cancelled"
		cachedOrder.UpdatedAt = time.Now()
	}
	s.ordersMu.Unlock()

	// Publish cancellation event
	cancelEvent, _ := json.Marshal(map[string]string{
		"order_id": orderID,
		"user_id":  userID,
	})
	s.nats.Publish("orders.cancelled", cancelEvent)

	return nil
}

func (s *Service) UpdateFill(ctx context.Context, orderID string, filledQty float64) error {
	s.ordersMu.Lock()
	defer s.ordersMu.Unlock()

	order, ok := s.orders[orderID]
	if !ok {
		return ErrOrderNotFound
	}

	
	order.FilledQty += filledQty
	if order.FilledQty >= order.Quantity {
		order.Status = "filled"
	} else {
		order.Status = "partial"
	}
	order.UpdatedAt = time.Now()

	// Update database
	_, err := s.db.ExecContext(ctx,
		"UPDATE orders SET filled_qty = $1, status = $2, updated_at = $3 WHERE id = $4",
		order.FilledQty, order.Status, order.UpdatedAt, orderID,
	)

	return err
}
