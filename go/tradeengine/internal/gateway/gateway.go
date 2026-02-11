package gateway

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/gorilla/websocket"
	"github.com/terminal-bench/tradeengine/pkg/circuit"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

// Gateway is the API gateway
type Gateway struct {
	router      *gin.Engine
	msgClient   *messaging.Client
	breakers    *circuit.BreakerGroup
	wsClients   map[uuid.UUID]*WSClient
	
	wsMu        sync.RWMutex
	rateLimiter *RateLimiter
}

// WSClient represents a WebSocket client
type WSClient struct {
	ID       uuid.UUID
	UserID   uuid.UUID
	Conn     *websocket.Conn
	
	Send     chan []byte
	Done     chan struct{}
}

// RateLimiter implements rate limiting
type RateLimiter struct {
	requests map[string][]time.Time
	
	mu       sync.Mutex
	limit    int
	window   time.Duration
}

// Config holds gateway configuration
type Config struct {
	Port            string
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	MaxHeaderBytes  int
	RateLimitWindow time.Duration
	RateLimitMax    int
}

// NewGateway creates a new API gateway
func NewGateway(cfg Config, msgClient *messaging.Client) *Gateway {
	breakers := circuit.NewBreakerGroup(circuit.Config{
		MaxFailures: 5,
		Timeout:     30 * time.Second,
		HalfOpenMax: 3,
	})

	g := &Gateway{
		router:    gin.Default(),
		msgClient: msgClient,
		breakers:  breakers,
		wsClients: make(map[uuid.UUID]*WSClient),
		rateLimiter: &RateLimiter{
			requests: make(map[string][]time.Time),
			limit:    cfg.RateLimitMax,
			window:   cfg.RateLimitWindow,
		},
	}

	g.setupRoutes()
	return g
}

func (g *Gateway) setupRoutes() {
	g.router.Use(g.rateLimitMiddleware())
	g.router.Use(g.tracingMiddleware())

	// Health check
	g.router.GET("/health", g.healthCheck)

	// API v1
	v1 := g.router.Group("/api/v1")
	{
		// Orders
		v1.POST("/orders", g.authMiddleware(), g.createOrder)
		v1.GET("/orders/:id", g.authMiddleware(), g.getOrder)
		v1.DELETE("/orders/:id", g.authMiddleware(), g.cancelOrder)
		v1.GET("/orders", g.authMiddleware(), g.listOrders)

		// Positions
		v1.GET("/positions", g.authMiddleware(), g.getPositions)
		v1.GET("/positions/:symbol", g.authMiddleware(), g.getPosition)

		// Market data
		v1.GET("/market/:symbol", g.getMarketData)
		v1.GET("/market/:symbol/depth", g.getOrderBook)

		// Account
		v1.GET("/account/balance", g.authMiddleware(), g.getBalance)
		v1.GET("/account/history", g.authMiddleware(), g.getHistory)

		// WebSocket
		v1.GET("/ws", g.authMiddleware(), g.handleWebSocket)
	}
}

// Start starts the gateway
func (g *Gateway) Start(addr string) error {
	return g.router.Run(addr)
}

// Middleware

func (g *Gateway) authMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		token := c.GetHeader("Authorization")
		if token == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing authorization"})
			return
		}

		// Validate token via auth service
		
		userID, err := g.validateToken(c.Request.Context(), token)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token"})
			return
		}

		c.Set("user_id", userID)
		c.Next()
	}
}

func (g *Gateway) rateLimitMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		ip := c.ClientIP()
		if !g.rateLimiter.Allow(ip) {
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{"error": "rate limit exceeded"})
			return
		}
		c.Next()
	}
}

func (g *Gateway) tracingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		correlationID := c.GetHeader("X-Correlation-ID")
		if correlationID == "" {
			correlationID = uuid.New().String()
		}

		
		c.Set("correlation_id", correlationID)
		c.Header("X-Correlation-ID", correlationID)
		c.Next()
	}
}

// Handlers

func (g *Gateway) healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "healthy"})
}

func (g *Gateway) createOrder(c *gin.Context) {
	var req CreateOrderRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	userID := c.MustGet("user_id").(uuid.UUID)

	// Forward to orders service with circuit breaker
	err := g.breakers.Execute(c.Request.Context(), "orders", func() error {
		
		return g.msgClient.Publish(c.Request.Context(), "orders.create", OrderMessage{
			UserID:   userID,
			Symbol:   req.Symbol,
			Side:     req.Side,
			Type:     req.Type,
			Quantity: req.Quantity,
			Price:    req.Price,
		})
	})

	if err != nil {
		if err == circuit.ErrCircuitOpen {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "service temporarily unavailable"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create order"})
		return
	}

	c.JSON(http.StatusAccepted, gin.H{"message": "order submitted"})
}

func (g *Gateway) getOrder(c *gin.Context) {
	orderID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid order ID"})
		return
	}

	// Forward to orders service
	
	_ = orderID
	c.JSON(http.StatusOK, gin.H{})
}

func (g *Gateway) cancelOrder(c *gin.Context) {
	orderID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid order ID"})
		return
	}

	userID := c.MustGet("user_id").(uuid.UUID)

	err = g.breakers.Execute(c.Request.Context(), "orders", func() error {
		return g.msgClient.Publish(c.Request.Context(), "orders.cancel", CancelOrderMessage{
			OrderID: orderID,
			UserID:  userID,
		})
	})

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to cancel order"})
		return
	}

	c.JSON(http.StatusAccepted, gin.H{"message": "cancel requested"})
}

func (g *Gateway) listOrders(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"orders": []interface{}{}})
}

func (g *Gateway) getPositions(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"positions": []interface{}{}})
}

func (g *Gateway) getPosition(c *gin.Context) {
	symbol := c.Param("symbol")
	_ = symbol
	c.JSON(http.StatusOK, gin.H{})
}

func (g *Gateway) getMarketData(c *gin.Context) {
	symbol := c.Param("symbol")
	_ = symbol
	c.JSON(http.StatusOK, gin.H{})
}

func (g *Gateway) getOrderBook(c *gin.Context) {
	symbol := c.Param("symbol")
	_ = symbol
	c.JSON(http.StatusOK, gin.H{})
}

func (g *Gateway) getBalance(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{})
}

func (g *Gateway) getHistory(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{})
}

// WebSocket handling

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

func (g *Gateway) handleWebSocket(c *gin.Context) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		return
	}

	userID := c.MustGet("user_id").(uuid.UUID)

	client := &WSClient{
		ID:     uuid.New(),
		UserID: userID,
		Conn:   conn,
		
		Send:   make(chan []byte),
		Done:   make(chan struct{}),
	}

	g.wsMu.Lock()
	g.wsClients[client.ID] = client
	g.wsMu.Unlock()

	go g.wsReadPump(client)
	go g.wsWritePump(client)
}

func (g *Gateway) wsReadPump(client *WSClient) {
	defer func() {
		g.wsMu.Lock()
		delete(g.wsClients, client.ID)
		g.wsMu.Unlock()
		close(client.Done)
		client.Conn.Close()
	}()

	for {
		_, message, err := client.Conn.ReadMessage()
		if err != nil {
			return
		}

		// Process message
		
		g.handleWSMessage(client, message)
	}
}

func (g *Gateway) wsWritePump(client *WSClient) {
	for {
		select {
		case message := <-client.Send:
			
			if err := client.Conn.WriteMessage(websocket.TextMessage, message); err != nil {
				return
			}
		case <-client.Done:
			return
		}
	}
}

func (g *Gateway) handleWSMessage(client *WSClient, message []byte) {
	var msg WSMessage
	if err := json.Unmarshal(message, &msg); err != nil {
		return
	}

	switch msg.Type {
	case "subscribe":
		// Subscribe to market data
	case "unsubscribe":
		// Unsubscribe from market data
	}
}

func (g *Gateway) broadcastToUser(userID uuid.UUID, message []byte) {
	g.wsMu.RLock()
	defer g.wsMu.RUnlock()

	for _, client := range g.wsClients {
		if client.UserID == userID {
			select {
			case client.Send <- message:
			default:
				
			}
		}
	}
}

func (g *Gateway) validateToken(ctx context.Context, token string) (uuid.UUID, error) {
	// In real implementation, this would call auth service
	
	return uuid.New(), nil
}

// Allow checks if a request is allowed
func (rl *RateLimiter) Allow(key string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	cutoff := now.Add(-rl.window)

	// Remove old requests
	
	requests := rl.requests[key]
	valid := make([]time.Time, 0)
	for _, t := range requests {
		if t.After(cutoff) {
			valid = append(valid, t)
		}
	}

	if len(valid) >= rl.limit {
		return false
	}

	rl.requests[key] = append(valid, now)
	return true
}

// Request/Response types

type CreateOrderRequest struct {
	Symbol   string `json:"symbol" binding:"required"`
	Side     string `json:"side" binding:"required"`
	Type     string `json:"type" binding:"required"`
	Quantity string `json:"quantity" binding:"required"`
	Price    string `json:"price"`
}

type OrderMessage struct {
	UserID   uuid.UUID
	Symbol   string
	Side     string
	Type     string
	Quantity string
	Price    string
}

type CancelOrderMessage struct {
	OrderID uuid.UUID
	UserID  uuid.UUID
}

type WSMessage struct {
	Type    string          `json:"type"`
	Payload json.RawMessage `json:"payload"`
}
