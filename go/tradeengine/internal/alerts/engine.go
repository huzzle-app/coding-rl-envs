package alerts

import (
	"context"
	"database/sql"
	"encoding/json"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

type Engine struct {
	db           *sql.DB
	nats         *messaging.Client
	alerts       map[string][]*Alert // symbol -> alerts
	alertsMu     sync.RWMutex
	priceChannel chan PriceUpdate
	stopCh       chan struct{}
}

type Alert struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	Symbol    string    `json:"symbol"`
	Condition string    `json:"condition"` // "above", "below", "crosses"
	Price     float64   `json:"price"`
	Triggered bool      `json:"triggered"`
	CreatedAt time.Time `json:"created_at"`
}

type PriceUpdate struct {
	Symbol string
	Price  float64
}

func NewEngine(db *sql.DB, nats *messaging.Client) *Engine {
	return &Engine{
		db:           db,
		nats:         nats,
		alerts:       make(map[string][]*Alert),
		
		priceChannel: make(chan PriceUpdate, 10),
		stopCh:       make(chan struct{}),
	}
}

func (e *Engine) Start(ctx context.Context) {
	// Load existing alerts
	e.loadAlerts(ctx)

	// Start price processor
	go e.processPrices(ctx)
}

func (e *Engine) loadAlerts(ctx context.Context) {
	rows, err := e.db.QueryContext(ctx,
		"SELECT id, user_id, symbol, condition, price, triggered, created_at FROM alerts WHERE triggered = false",
	)
	if err != nil {
		return
	}
	defer rows.Close()

	e.alertsMu.Lock()
	defer e.alertsMu.Unlock()

	for rows.Next() {
		var alert Alert
		err := rows.Scan(&alert.ID, &alert.UserID, &alert.Symbol, &alert.Condition, &alert.Price, &alert.Triggered, &alert.CreatedAt)
		if err != nil {
			continue
		}

		e.alerts[alert.Symbol] = append(e.alerts[alert.Symbol], &alert)
	}
}

func (e *Engine) processPrices(ctx context.Context) {
	
	lastPrices := make(map[string]float64)
	var lastPricesMu sync.RWMutex

	for {
		select {
		case <-ctx.Done():
			return
		case <-e.stopCh:
			return
		case update := <-e.priceChannel:
			e.alertsMu.RLock()
			alerts := e.alerts[update.Symbol]
			e.alertsMu.RUnlock()

			lastPricesMu.RLock()
			lastPrice := lastPrices[update.Symbol]
			lastPricesMu.RUnlock()

			for _, alert := range alerts {
				if alert.Triggered {
					continue
				}

				triggered := false
				switch alert.Condition {
				case "above":
					
					triggered = update.Price > alert.Price
				case "below":
					triggered = update.Price < alert.Price
				case "crosses":
					
					if lastPrice != 0 {
						crossed := (lastPrice < alert.Price && update.Price >= alert.Price) ||
							(lastPrice > alert.Price && update.Price <= alert.Price)
						triggered = crossed
					}
				}

				if triggered {
					e.triggerAlert(alert, update.Price)
				}
			}

			
			lastPricesMu.Lock()
			lastPrices[update.Symbol] = update.Price
			lastPricesMu.Unlock()
		}
	}
}

func (e *Engine) triggerAlert(alert *Alert, currentPrice float64) {
	alert.Triggered = true

	// Update database
	ctx := context.Background()
	e.db.ExecContext(ctx,
		"UPDATE alerts SET triggered = true, triggered_at = $1, triggered_price = $2 WHERE id = $3",
		time.Now(), currentPrice, alert.ID,
	)

	// Send notification
	notification := map[string]interface{}{
		"alert_id":      alert.ID,
		"user_id":       alert.UserID,
		"symbol":        alert.Symbol,
		"condition":     alert.Condition,
		"target_price":  alert.Price,
		"current_price": currentPrice,
		"triggered_at":  time.Now(),
	}

	notifJSON, _ := json.Marshal(notification)
	e.nats.Publish("alerts.triggered", notifJSON)
}

func (e *Engine) CheckPrice(subject string, data []byte) {
	// Parse price data
	var priceData struct {
		Symbol string  `json:"symbol"`
		Price  float64 `json:"price"`
	}

	if err := json.Unmarshal(data, &priceData); err != nil {
		return
	}

	
	e.priceChannel <- PriceUpdate{
		Symbol: priceData.Symbol,
		Price:  priceData.Price,
	}
}

func (e *Engine) CreateAlert(ctx context.Context, userID, symbol, condition string, price float64) (*Alert, error) {
	alertID := uuid.New().String()
	now := time.Now()

	alert := &Alert{
		ID:        alertID,
		UserID:    userID,
		Symbol:    symbol,
		Condition: condition,
		Price:     price,
		Triggered: false,
		CreatedAt: now,
	}

	_, err := e.db.ExecContext(ctx,
		"INSERT INTO alerts (id, user_id, symbol, condition, price, triggered, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)",
		alert.ID, alert.UserID, alert.Symbol, alert.Condition, alert.Price, alert.Triggered, alert.CreatedAt,
	)
	if err != nil {
		return nil, err
	}

	// Add to in-memory cache
	e.alertsMu.Lock()
	e.alerts[symbol] = append(e.alerts[symbol], alert)
	e.alertsMu.Unlock()

	return alert, nil
}

func (e *Engine) GetAlerts(ctx context.Context, userID string) ([]*Alert, error) {
	rows, err := e.db.QueryContext(ctx,
		"SELECT id, user_id, symbol, condition, price, triggered, created_at FROM alerts WHERE user_id = $1",
		userID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var alerts []*Alert
	for rows.Next() {
		var alert Alert
		err := rows.Scan(&alert.ID, &alert.UserID, &alert.Symbol, &alert.Condition, &alert.Price, &alert.Triggered, &alert.CreatedAt)
		if err != nil {
			continue
		}
		alerts = append(alerts, &alert)
	}

	return alerts, nil
}

func (e *Engine) DeleteAlert(ctx context.Context, alertID, userID string) error {
	// Verify ownership
	var ownerID string
	var symbol string
	err := e.db.QueryRowContext(ctx,
		"SELECT user_id, symbol FROM alerts WHERE id = $1",
		alertID,
	).Scan(&ownerID, &symbol)

	if err != nil {
		return err
	}

	if ownerID != userID {
		return sql.ErrNoRows // Unauthorized
	}

	_, err = e.db.ExecContext(ctx, "DELETE FROM alerts WHERE id = $1", alertID)
	if err != nil {
		return err
	}

	// Remove from in-memory cache
	e.alertsMu.Lock()
	alerts := e.alerts[symbol]
	for i, a := range alerts {
		if a.ID == alertID {
			e.alerts[symbol] = append(alerts[:i], alerts[i+1:]...)
			break
		}
	}
	e.alertsMu.Unlock()

	return nil
}

func (e *Engine) Stop() {
	close(e.stopCh)
}
