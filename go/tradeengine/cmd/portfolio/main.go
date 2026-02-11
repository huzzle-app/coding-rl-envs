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
	"github.com/terminal-bench/tradeengine/internal/portfolio"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8007"
	}

	natsURL := os.Getenv("NATS_URL")
	dbURL := os.Getenv("DATABASE_URL")
	redisURL := os.Getenv("REDIS_URL")

	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	natsClient, err := messaging.NewClient(natsURL, messaging.ClientOptions{
		Name:          "portfolio-service",
		ReconnectWait: time.Second,
		MaxReconnects: 5,
	})
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}

	portfolioService := portfolio.NewManager(db, natsClient, redisURL)

	r := gin.Default()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})

	r.GET("/api/v1/portfolio/:user_id", func(c *gin.Context) {
		userID := c.Param("user_id")

		
		port, err := portfolioService.GetPortfolio(c.Request.Context(), userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, port)
	})

	r.GET("/api/v1/portfolio/:user_id/performance", func(c *gin.Context) {
		userID := c.Param("user_id")
		period := c.DefaultQuery("period", "1d")

		
		perf, err := portfolioService.GetPerformance(c.Request.Context(), userID, period)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, perf)
	})

	r.GET("/api/v1/portfolio/:user_id/allocation", func(c *gin.Context) {
		userID := c.Param("user_id")

		allocation, err := portfolioService.GetAllocation(c.Request.Context(), userID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, allocation)
	})

	r.GET("/api/v1/portfolio/:user_id/history", func(c *gin.Context) {
		userID := c.Param("user_id")
		limit := c.DefaultQuery("limit", "100")

		history, err := portfolioService.GetHistory(c.Request.Context(), userID, limit)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, history)
	})

	// Subscribe to position updates
	go func() {
		natsClient.Subscribe("positions.updated", func(msg *nats.Msg) {
			
			portfolioService.InvalidateCache(string(msg.Data))
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

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	db.Close()
}
