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
	"github.com/terminal-bench/tradeengine/internal/market"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8006"
	}

	natsURL := os.Getenv("NATS_URL")
	influxURL := os.Getenv("INFLUXDB_URL")
	influxToken := os.Getenv("INFLUXDB_TOKEN")
	influxOrg := os.Getenv("INFLUXDB_ORG")
	influxBucket := os.Getenv("INFLUXDB_BUCKET")

	natsClient, err := messaging.NewClient(natsURL, messaging.ClientOptions{
		Name:          "market-service",
		ReconnectWait: time.Second,
		MaxReconnects: 5,
	})
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}

	feed := market.NewFeed(market.FeedConfig{
		BufferSize:      10000,
		AggregateWindow: time.Second,
		Symbols:         []string{"BTC-USD", "ETH-USD", "SOL-USD"},
	})

	r := gin.Default()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})

	r.GET("/api/v1/market/ticker/:symbol", func(c *gin.Context) {
		symbol := c.Param("symbol")
		ticker := feed.GetTicker(symbol)
		if ticker == nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "symbol not found"})
			return
		}
		c.JSON(http.StatusOK, ticker)
	})

	r.GET("/api/v1/market/ohlcv/:symbol", func(c *gin.Context) {
		symbol := c.Param("symbol")
		interval := c.DefaultQuery("interval", "1m")
		limit := c.DefaultQuery("limit", "100")

		
		ohlcv := feed.GetOHLCV(symbol, interval, limit)
		c.JSON(http.StatusOK, ohlcv)
	})

	r.GET("/api/v1/market/orderbook/:symbol", func(c *gin.Context) {
		symbol := c.Param("symbol")
		depth := c.DefaultQuery("depth", "10")
		book := feed.GetOrderBookSnapshot(symbol, depth)
		c.JSON(http.StatusOK, book)
	})

	// WebSocket endpoint for real-time data
	r.GET("/ws/market/:symbol", func(c *gin.Context) {
		
		feed.HandleWebSocket(c.Writer, c.Request, c.Param("symbol"))
	})

	// Start feed
	ctx, cancel := context.WithCancel(context.Background())
	feed.Start(ctx, natsClient)

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

	_ = influxURL
	_ = influxToken
	_ = influxOrg
	_ = influxBucket
}
