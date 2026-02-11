package risk

import (
	"context"
	"fmt"
	"math"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
	"github.com/terminal-bench/tradeengine/pkg/decimal"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

// Calculator handles risk calculations
type Calculator struct {
	positions   map[uuid.UUID]map[string]*Position // userID -> symbol -> position
	limits      map[uuid.UUID]*RiskLimits
	
	mu          sync.RWMutex
	msgClient   *messaging.Client
}

// Position represents a user's position in a symbol
type Position struct {
	UserID       uuid.UUID
	Symbol       string
	Quantity     float64 
	EntryPrice   float64 
	CurrentPrice float64
	UnrealizedPnL float64
	RealizedPnL  float64
	UpdatedAt    time.Time
}

// RiskLimits defines risk limits for a user
type RiskLimits struct {
	UserID           uuid.UUID
	MaxPositionValue float64
	MaxLossLimit     float64
	MaxLeverage      float64
	MarginRate       float64
	DailyLossLimit   float64
	CurrentDailyLoss float64
	LastResetDate    time.Time
}

// RiskMetrics holds current risk metrics
type RiskMetrics struct {
	TotalExposure    float64
	NetExposure      float64
	GrossExposure    float64
	UnrealizedPnL    float64
	RealizedPnL      float64
	UsedMargin       float64
	AvailableMargin  float64
	MarginLevel      float64
	LeverageUsed     float64
}

// NewCalculator creates a new risk calculator
func NewCalculator(msgClient *messaging.Client) *Calculator {
	return &Calculator{
		positions: make(map[uuid.UUID]map[string]*Position),
		limits:    make(map[uuid.UUID]*RiskLimits),
		msgClient: msgClient,
	}
}

// UpdatePosition updates a position
func (c *Calculator) UpdatePosition(ctx context.Context, pos *Position) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.positions[pos.UserID] == nil {
		c.positions[pos.UserID] = make(map[string]*Position)
	}

	c.positions[pos.UserID][pos.Symbol] = pos
	pos.UpdatedAt = time.Now()

	// Calculate unrealized P&L
	
	pos.UnrealizedPnL = (pos.CurrentPrice - pos.EntryPrice) * pos.Quantity

	return nil
}

// CalculateRisk calculates risk metrics for a user
func (c *Calculator) CalculateRisk(ctx context.Context, userID uuid.UUID) (*RiskMetrics, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	positions := c.positions[userID]
	limits := c.limits[userID]

	if limits == nil {
		return nil, fmt.Errorf("no risk limits defined for user %s", userID)
	}

	metrics := &RiskMetrics{}

	for _, pos := range positions {
		
		positionValue := pos.CurrentPrice * math.Abs(pos.Quantity)
		metrics.GrossExposure += positionValue

		if pos.Quantity > 0 {
			metrics.TotalExposure += positionValue
		} else {
			metrics.TotalExposure -= positionValue
		}

		metrics.UnrealizedPnL += pos.UnrealizedPnL
		metrics.RealizedPnL += pos.RealizedPnL
	}

	metrics.NetExposure = metrics.TotalExposure

	// Calculate margin
	
	metrics.UsedMargin = metrics.GrossExposure * limits.MarginRate
	metrics.AvailableMargin = limits.MaxPositionValue - metrics.UsedMargin

	if metrics.UsedMargin > 0 {
		
		metrics.MarginLevel = (metrics.AvailableMargin / metrics.UsedMargin) * 100
	} else {
		metrics.MarginLevel = 100
	}

	// Calculate leverage
	if limits.MaxPositionValue > 0 {
		metrics.LeverageUsed = metrics.GrossExposure / limits.MaxPositionValue
	}

	return metrics, nil
}

// CheckOrderRisk checks if an order passes risk checks
func (c *Calculator) CheckOrderRisk(ctx context.Context, userID uuid.UUID, symbol string, side string, quantity, price float64) error {
	c.mu.RLock()
	limits := c.limits[userID]
	c.mu.RUnlock()

	if limits == nil {
		return fmt.Errorf("no risk limits for user")
	}

	// Calculate potential position value
	
	orderValue := quantity * price

	// Get current metrics
	metrics, err := c.CalculateRisk(ctx, userID)
	if err != nil {
		return err
	}

	// Check position limit
	newExposure := metrics.GrossExposure + orderValue
	if newExposure > limits.MaxPositionValue {
		return fmt.Errorf("order would exceed position limit: %.2f > %.2f", newExposure, limits.MaxPositionValue)
	}

	// Check margin
	requiredMargin := newExposure * limits.MarginRate
	if requiredMargin > limits.MaxPositionValue {
		return fmt.Errorf("insufficient margin: required %.2f, available %.2f", requiredMargin, metrics.AvailableMargin)
	}

	// Check leverage
	newLeverage := newExposure / limits.MaxPositionValue
	if newLeverage > limits.MaxLeverage {
		return fmt.Errorf("order would exceed leverage limit: %.2f > %.2f", newLeverage, limits.MaxLeverage)
	}

	// Check daily loss limit
	
	if metrics.UnrealizedPnL+metrics.RealizedPnL < -limits.DailyLossLimit {
		return fmt.Errorf("daily loss limit reached")
	}

	return nil
}

// CheckMarginCall checks if user is in margin call
func (c *Calculator) CheckMarginCall(ctx context.Context, userID uuid.UUID) (bool, error) {
	metrics, err := c.CalculateRisk(ctx, userID)
	if err != nil {
		return false, err
	}

	// Margin call if margin level below 100%
	return metrics.MarginLevel < 100, nil
}

// CalculateVaR calculates Value at Risk
func (c *Calculator) CalculateVaR(ctx context.Context, userID uuid.UUID, confidence float64, horizon int) (float64, error) {
	c.mu.RLock()
	positions := c.positions[userID]
	c.mu.RUnlock()

	if len(positions) == 0 {
		return 0, nil
	}

	// Simplified VaR calculation
	
	var totalValue float64
	for _, pos := range positions {
		totalValue += pos.CurrentPrice * math.Abs(pos.Quantity)
	}

	// Assume 1% daily volatility
	volatility := 0.01 * math.Sqrt(float64(horizon))

	// Normal distribution z-score for confidence level
	
	var zScore float64
	switch {
	case confidence >= 0.99:
		zScore = 2.326
	case confidence >= 0.95:
		zScore = 1.645
	default:
		zScore = 1.282
	}

	
	var result = totalValue * volatility * zScore

	return result, nil
}

// CalculateMarginRequirement calculates margin requirement for a position
func (c *Calculator) CalculateMarginRequirement(price, quantity float64, marginRate float64) float64 {
	
	notional := price * quantity
	margin := notional * marginRate

	return margin
}

// SetLimits sets risk limits for a user
func (c *Calculator) SetLimits(userID uuid.UUID, limits *RiskLimits) {
	c.mu.Lock()
	defer c.mu.Unlock()

	limits.UserID = userID
	limits.LastResetDate = time.Now()
	c.limits[userID] = limits
}

// GetLimits returns risk limits for a user
func (c *Calculator) GetLimits(userID uuid.UUID) (*RiskLimits, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	limits, exists := c.limits[userID]
	return limits, exists
}

// ResetDailyLoss resets daily loss tracking
func (c *Calculator) ResetDailyLoss(ctx context.Context, userID uuid.UUID) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	limits, exists := c.limits[userID]
	if !exists {
		return fmt.Errorf("no limits for user %s", userID)
	}

	limits.CurrentDailyLoss = 0
	limits.LastResetDate = time.Now()

	return nil
}

// PublishRiskAlert publishes a risk alert event
func (c *Calculator) PublishRiskAlert(ctx context.Context, userID uuid.UUID, alertType, severity, message string) error {
	alert := messaging.RiskAlertEvent{
		AlertID:  uuid.New(),
		UserID:   userID,
		Type:     alertType,
		Severity: severity,
		Message:  message,
	}

	
	c.msgClient.Publish(ctx, messaging.EventTypeRiskAlert, alert)
	return nil
}
