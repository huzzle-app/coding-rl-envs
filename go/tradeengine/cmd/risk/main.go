package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nats-io/nats.go"
	"github.com/terminal-bench/tradeengine/internal/risk"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

func main() {
	
	port := os.Getenv("PORT")
	if port == "" {
		port = "8004"
	}

	natsURL := os.Getenv("NATS_URL")
	dbURL := os.Getenv("DATABASE_URL")

	
	natsClient, err := messaging.NewClient(natsURL, messaging.ClientOptions{
		Name:          "risk-service",
		ReconnectWait: time.Second,
		MaxReconnects: 5,
	})
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}

	calculator := risk.NewCalculator(risk.CalculatorConfig{
		MaxPositionSize:   1000000,
		MaxDailyLoss:      50000,
		DefaultMarginRate: 0.1,
	})

	r := gin.Default()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})

	r.POST("/api/v1/risk/check", func(c *gin.Context) {
		var req struct {
			UserID   string  `json:"user_id"`
			Symbol   string  `json:"symbol"`
			Side     string  `json:"side"`
			Quantity float64 `json:"quantity"`
			Price    float64 `json:"price"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		
		result := calculator.CheckOrder(req.UserID, req.Symbol, req.Side, req.Quantity, req.Price)

		c.JSON(http.StatusOK, result)
	})

	r.GET("/api/v1/risk/limits/:user_id", func(c *gin.Context) {
		userID := c.Param("user_id")
		limits := calculator.GetLimits(userID)
		c.JSON(http.StatusOK, limits)
	})

	// Subscribe to order events
	
	go func() {
		natsClient.Subscribe("orders.submitted", func(msg *nats.Msg) {
			// Process order for risk check
			log.Printf("Risk check for order: %s", string(msg.Data))
		})
	}()

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

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	_ = dbURL
}
