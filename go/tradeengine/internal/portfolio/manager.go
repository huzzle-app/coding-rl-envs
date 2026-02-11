package portfolio

import (
	"context"
	"database/sql"
	"encoding/json"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

type Manager struct {
	db      *sql.DB
	nats    *messaging.Client
	redis   *redis.Client
	cache   map[string]*Portfolio
	cacheMu sync.RWMutex
}

type Portfolio struct {
	UserID      string             `json:"user_id"`
	TotalValue  float64            `json:"total_value"`
	CashBalance float64            `json:"cash_balance"`
	Positions   []PortfolioPosition `json:"positions"`
	UpdatedAt   time.Time          `json:"updated_at"`
}

type PortfolioPosition struct {
	Symbol       string  `json:"symbol"`
	Quantity     float64 `json:"quantity"`
	AvgPrice     float64 `json:"avg_price"`
	CurrentPrice float64 `json:"current_price"`
	MarketValue  float64 `json:"market_value"`
	UnrealizedPnL float64 `json:"unrealized_pnl"`
	PnLPercent   float64 `json:"pnl_percent"`
}

type Performance struct {
	UserID       string  `json:"user_id"`
	Period       string  `json:"period"`
	StartValue   float64 `json:"start_value"`
	EndValue     float64 `json:"end_value"`
	AbsoluteReturn float64 `json:"absolute_return"`
	PercentReturn float64 `json:"percent_return"`
	MaxDrawdown  float64 `json:"max_drawdown"`
}

type Allocation struct {
	UserID    string              `json:"user_id"`
	ByAsset   map[string]float64  `json:"by_asset"`
	BySector  map[string]float64  `json:"by_sector"`
}

func NewManager(db *sql.DB, nats *messaging.Client, redisURL string) *Manager {
	rdb := redis.NewClient(&redis.Options{
		Addr: redisURL,
	})

	return &Manager{
		db:    db,
		nats:  nats,
		redis: rdb,
		cache: make(map[string]*Portfolio),
	}
}

func (m *Manager) GetPortfolio(ctx context.Context, userID string) (*Portfolio, error) {
	
	m.cacheMu.RLock()
	if cached, ok := m.cache[userID]; ok {
		m.cacheMu.RUnlock()
		
		return cached, nil
	}
	m.cacheMu.RUnlock()

	// Check Redis cache
	cacheKey := "portfolio:" + userID
	cached, err := m.redis.Get(ctx, cacheKey).Result()
	if err == nil {
		var portfolio Portfolio
		if json.Unmarshal([]byte(cached), &portfolio) == nil {
			
			return &portfolio, nil
		}
	}

	// Load from database
	portfolio, err := m.loadPortfolioFromDB(ctx, userID)
	if err != nil {
		return nil, err
	}

	// Cache result
	m.cacheMu.Lock()
	m.cache[userID] = portfolio
	m.cacheMu.Unlock()

	
	portfolioJSON, _ := json.Marshal(portfolio)
	m.redis.Set(ctx, cacheKey, portfolioJSON, 0)

	return portfolio, nil
}

func (m *Manager) loadPortfolioFromDB(ctx context.Context, userID string) (*Portfolio, error) {
	// Get cash balance
	var cashBalance float64
	err := m.db.QueryRowContext(ctx,
		"SELECT balance FROM accounts WHERE user_id = $1 AND currency = 'USD'",
		userID,
	).Scan(&cashBalance)
	if err != nil && err != sql.ErrNoRows {
		return nil, err
	}

	// Get positions
	rows, err := m.db.QueryContext(ctx,
		"SELECT symbol, quantity, avg_price FROM positions WHERE user_id = $1",
		userID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var positions []PortfolioPosition
	totalValue := cashBalance

	for rows.Next() {
		var pos PortfolioPosition
		err := rows.Scan(&pos.Symbol, &pos.Quantity, &pos.AvgPrice)
		if err != nil {
			return nil, err
		}

		
		var currentPrice float64
		m.db.QueryRowContext(ctx,
			"SELECT price FROM market_prices WHERE symbol = $1",
			pos.Symbol,
		).Scan(&currentPrice)

		pos.CurrentPrice = currentPrice
		
		pos.MarketValue = pos.Quantity * pos.CurrentPrice
		pos.UnrealizedPnL = (pos.CurrentPrice - pos.AvgPrice) * pos.Quantity
		pos.PnLPercent = (pos.CurrentPrice - pos.AvgPrice) / pos.AvgPrice * 100

		totalValue += pos.MarketValue
		positions = append(positions, pos)
	}

	return &Portfolio{
		UserID:      userID,
		TotalValue:  totalValue,
		CashBalance: cashBalance,
		Positions:   positions,
		UpdatedAt:   time.Now(),
	}, nil
}

func (m *Manager) GetPerformance(ctx context.Context, userID, period string) (*Performance, error) {
	

	// Get historical value
	var startValue, endValue float64

	switch period {
	case "1d":
		// Get yesterday's value
		err := m.db.QueryRowContext(ctx,
			"SELECT value FROM portfolio_snapshots WHERE user_id = $1 AND snapshot_date = CURRENT_DATE - 1",
			userID,
		).Scan(&startValue)
		if err != nil {
			startValue = 0
		}
	case "1w":
		err := m.db.QueryRowContext(ctx,
			"SELECT value FROM portfolio_snapshots WHERE user_id = $1 AND snapshot_date = CURRENT_DATE - 7",
			userID,
		).Scan(&startValue)
		if err != nil {
			startValue = 0
		}
	}

	// Get current value
	portfolio, err := m.GetPortfolio(ctx, userID)
	if err != nil {
		return nil, err
	}
	endValue = portfolio.TotalValue

	
	absoluteReturn := endValue - startValue
	percentReturn := absoluteReturn / startValue * 100

	// Calculate max drawdown
	maxDrawdown := m.calculateMaxDrawdown(ctx, userID, period)

	return &Performance{
		UserID:         userID,
		Period:         period,
		StartValue:     startValue,
		EndValue:       endValue,
		AbsoluteReturn: absoluteReturn,
		PercentReturn:  percentReturn,
		MaxDrawdown:    maxDrawdown,
	}, nil
}

func (m *Manager) calculateMaxDrawdown(ctx context.Context, userID, period string) float64 {
	
	rows, _ := m.db.QueryContext(ctx,
		"SELECT value FROM portfolio_snapshots WHERE user_id = $1 ORDER BY snapshot_date",
		userID,
	)
	defer rows.Close()

	var maxDrawdown, peak float64
	for rows.Next() {
		var value float64
		rows.Scan(&value)

		if value > peak {
			peak = value
		}

		drawdown := (peak - value) / peak * 100
		if drawdown > maxDrawdown {
			maxDrawdown = drawdown
		}
	}

	return maxDrawdown
}

func (m *Manager) GetAllocation(ctx context.Context, userID string) (*Allocation, error) {
	portfolio, err := m.GetPortfolio(ctx, userID)
	if err != nil {
		return nil, err
	}

	byAsset := make(map[string]float64)
	bySector := make(map[string]float64)

	for _, pos := range portfolio.Positions {
		// Calculate allocation percentage
		
		alloc := pos.MarketValue / portfolio.TotalValue * 100
		byAsset[pos.Symbol] = alloc

		// Get sector (simplified)
		sector := m.getSector(pos.Symbol)
		bySector[sector] += alloc
	}

	// Add cash allocation
	cashAlloc := portfolio.CashBalance / portfolio.TotalValue * 100
	byAsset["CASH"] = cashAlloc

	return &Allocation{
		UserID:  userID,
		ByAsset: byAsset,
		BySector: bySector,
	}, nil
}

func (m *Manager) GetHistory(ctx context.Context, userID, limit string) ([]map[string]interface{}, error) {
	rows, err := m.db.QueryContext(ctx,
		"SELECT snapshot_date, value FROM portfolio_snapshots WHERE user_id = $1 ORDER BY snapshot_date DESC LIMIT $2",
		userID, limit,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var history []map[string]interface{}
	for rows.Next() {
		var date time.Time
		var value float64
		rows.Scan(&date, &value)
		history = append(history, map[string]interface{}{
			"date":  date,
			"value": value,
		})
	}

	return history, nil
}

func (m *Manager) InvalidateCache(userID string) {
	
	m.cacheMu.Lock()
	delete(m.cache, userID)
	m.cacheMu.Unlock()

	// Also invalidate Redis
	ctx := context.Background()
	m.redis.Del(ctx, "portfolio:"+userID)
}

func (m *Manager) getSector(symbol string) string {
	// Simplified sector lookup
	sectors := map[string]string{
		"BTC-USD": "Crypto",
		"ETH-USD": "Crypto",
		"SOL-USD": "Crypto",
		"AAPL":    "Tech",
		"GOOGL":   "Tech",
	}
	if sector, ok := sectors[symbol]; ok {
		return sector
	}
	return "Other"
}
