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
	"github.com/terminal-bench/tradeengine/internal/ledger"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8008"
	}

	natsURL := os.Getenv("NATS_URL")
	dbURL := os.Getenv("DATABASE_URL")

	
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	
	// db.SetMaxOpenConns(25)
	// db.SetMaxIdleConns(5)
	// db.SetConnMaxLifetime(5 * time.Minute)

	natsClient, err := messaging.NewClient(natsURL, messaging.ClientOptions{
		Name:          "ledger-service",
		ReconnectWait: time.Second,
		MaxReconnects: 5,
	})
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}

	ledgerService := ledger.NewLedger(db)

	r := gin.Default()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy"})
	})

	r.GET("/api/v1/ledger/balance/:account_id", func(c *gin.Context) {
		accountID := c.Param("account_id")
		balance, err := ledgerService.GetBalance(c.Request.Context(), accountID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusOK, balance)
	})

	r.GET("/api/v1/ledger/transactions/:account_id", func(c *gin.Context) {
		accountID := c.Param("account_id")
		limit := c.DefaultQuery("limit", "50")
		offset := c.DefaultQuery("offset", "0")

		txns, err := ledgerService.GetTransactions(c.Request.Context(), accountID, limit, offset)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusOK, txns)
	})

	r.POST("/api/v1/ledger/transfer", func(c *gin.Context) {
		var req struct {
			FromAccount string  `json:"from_account"`
			ToAccount   string  `json:"to_account"`
			Amount      float64 `json:"amount"`
			Currency    string  `json:"currency"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		
		txn, err := ledgerService.Transfer(c.Request.Context(), req.FromAccount, req.ToAccount, req.Amount, req.Currency)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, txn)
	})

	// Subscribe to trade events for settlement
	go func() {
		natsClient.Subscribe("trades.executed", func(msg *nats.Msg) {
			
			ctx := context.Background()
			ledgerService.SettleTrade(ctx, msg.Data)
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
