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
	"github.com/terminal-bench/tradeengine/internal/positions"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8005"
	}

	natsURL := os.Getenv("NATS_URL")
	dbURL := os.Getenv("DATABASE_URL")

	natsClient, err := messaging.NewClient(natsURL, messaging.ClientOptions{
		Name:          "positions-service",
		ReconnectWait: time.Second,
		MaxReconnects: 5,
	})
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}

	tracker := positions.NewTracker(positions.TrackerConfig{
		SnapshotInterval: time.Minute * 5,
		MaxEventsBuffer:  1000,
	})

	r := gin.Default()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})

	r.GET("/api/v1/positions/:user_id", func(c *gin.Context) {
		userID := c.Param("user_id")
		pos := tracker.GetPositions(userID)
		c.JSON(http.StatusOK, pos)
	})

	r.GET("/api/v1/positions/:user_id/:symbol", func(c *gin.Context) {
		userID := c.Param("user_id")
		symbol := c.Param("symbol")
		pos, exists := tracker.GetPosition(userID, symbol)
		if !exists {
			c.JSON(http.StatusNotFound, gin.H{"error": "position not found"})
			return
		}
		c.JSON(http.StatusOK, pos)
	})

	r.GET("/api/v1/positions/:user_id/pnl", func(c *gin.Context) {
		userID := c.Param("user_id")
		
		pnl := tracker.CalculatePnL(userID)
		c.JSON(http.StatusOK, pnl)
	})

	// Subscribe to trade events
	
	go func() {
		natsClient.Subscribe("trades.executed", func(msg *nats.Msg) {
			
			tracker.ProcessTrade(msg.Data)
		})
	}()

	// Start tracker background processes
	ctx, cancel := context.WithCancel(context.Background())
	tracker.Start(ctx)

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

	cancel()

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	_ = dbURL
}
