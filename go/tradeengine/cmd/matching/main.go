package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/terminal-bench/tradeengine/internal/matching"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

type Config struct {
	NATSUrl string
	Port    string
}

func loadConfig() *Config {
	return &Config{
		NATSUrl: getEnv("NATS_URL", "nats://localhost:4222"),
		Port:    getEnv("PORT", "8003"),
	}
}

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func main() {
	cfg := loadConfig()

	// Connect to NATS
	msgClient, err := messaging.NewClient(messaging.Config{
		URL:            cfg.NATSUrl,
		Name:           "matching-engine",
		ReconnectWait:  time.Second,
		MaxReconnects:  60,
		ConnectTimeout: 10 * time.Second,
	})
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}
	defer msgClient.Close()

	// Create matching engine
	engine := matching.NewEngine(msgClient)

	// Start engine
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	if err := engine.Start(ctx); err != nil {
		log.Fatalf("Failed to start matching engine: %v", err)
	}

	log.Printf("Matching engine started on port %s", cfg.Port)

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down matching engine...")
	engine.Stop()
	log.Println("Matching engine stopped")
}
