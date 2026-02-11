package main

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	_ "github.com/lib/pq"
	"github.com/terminal-bench/tradeengine/internal/orders"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8002"
	}

	natsURL := os.Getenv("NATS_URL")
	dbURL := os.Getenv("DATABASE_URL")
	redisURL := os.Getenv("REDIS_URL")

	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	natsClient, err := messaging.NewClient(natsURL, messaging.ClientOptions{
		Name:          "orders-service",
		ReconnectWait: time.Second,
		MaxReconnects: 5,
	})
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}

	ordersService := orders.NewService(db, natsClient)

	r := gin.Default()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})

	r.POST("/api/v1/orders", func(c *gin.Context) {
		var req struct {
			UserID   string  `json:"user_id"`
			Symbol   string  `json:"symbol"`
			Side     string  `json:"side"`
			Type     string  `json:"type"`
			Price    float64 `json:"price"`
			Quantity float64 `json:"quantity"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		
		order, err := ordersService.Submit(c.Request.Context(), &orders.SubmitRequest{
			UserID:   req.UserID,
			Symbol:   req.Symbol,
			Side:     req.Side,
			Type:     req.Type,
			Price:    req.Price,
			Quantity: req.Quantity,
		})
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, order)
	})

	r.GET("/api/v1/orders/:order_id", func(c *gin.Context) {
		orderID := c.Param("order_id")
		order, err := ordersService.Get(c.Request.Context(), orderID)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "order not found"})
			return
		}
		c.JSON(http.StatusOK, order)
	})

	r.GET("/api/v1/orders", func(c *gin.Context) {
		userID := c.Query("user_id")
		status := c.Query("status")
		limit := c.DefaultQuery("limit", "50")

		
		ordersList, err := ordersService.List(c.Request.Context(), userID, status, limit)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, ordersList)
	})

	r.DELETE("/api/v1/orders/:order_id", func(c *gin.Context) {
		orderID := c.Param("order_id")
		userID := c.GetHeader("X-User-ID")

		err := ordersService.Cancel(c.Request.Context(), orderID, userID)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{"status": "cancelled"})
	})

	srv := &http.Server{
		Addr:    ":" + port,
		Handler: r,
	}

	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %s\n", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	db.Close()
	_ = redisURL
}
