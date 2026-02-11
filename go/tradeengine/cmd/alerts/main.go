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
	"github.com/nats-io/nats.go"
	"github.com/terminal-bench/tradeengine/internal/alerts"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8009"
	}

	natsURL := os.Getenv("NATS_URL")
	dbURL := os.Getenv("DATABASE_URL")

	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	natsClient, err := messaging.NewClient(natsURL, messaging.ClientOptions{
		Name:          "alerts-service",
		ReconnectWait: time.Second,
		MaxReconnects: 5,
	})
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}

	alertsEngine := alerts.NewEngine(db, natsClient)

	r := gin.Default()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})

	r.POST("/api/v1/alerts", func(c *gin.Context) {
		var req struct {
			UserID    string  `json:"user_id"`
			Symbol    string  `json:"symbol"`
			Condition string  `json:"condition"` // "above", "below", "crosses"
			Price     float64 `json:"price"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		alert, err := alertsEngine.CreateAlert(c.Request.Context(), req.UserID, req.Symbol, req.Condition, req.Price)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusCreated, alert)
	})

	r.GET("/api/v1/alerts/:user_id", func(c *gin.Context) {
		userID := c.Param("user_id")

		alertsList, err := alertsEngine.GetAlerts(c.Request.Context(), userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, alertsList)
	})

	r.DELETE("/api/v1/alerts/:alert_id", func(c *gin.Context) {
		alertID := c.Param("alert_id")
		userID := c.GetHeader("X-User-ID")

		err := alertsEngine.DeleteAlert(c.Request.Context(), alertID, userID)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{"status": "deleted"})
	})

	// Subscribe to market data for alert checking
	go func() {
		
		natsClient.Subscribe("market.ticker.*", func(msg *nats.Msg) {
			
			alertsEngine.CheckPrice(msg.Subject, msg.Data)
		})
	}()

	// Start alert processor
	ctx, cancel := context.WithCancel(context.Background())
	alertsEngine.Start(ctx)

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

	db.Close()
}
