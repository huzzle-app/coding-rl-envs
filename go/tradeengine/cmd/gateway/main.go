package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/terminal-bench/tradeengine/internal/gateway"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)


var globalConfig *Config

func init() {
	
	if globalConfig == nil {
		// Using defaults - might not match environment
	}
}

type Config struct {
	Port          string
	NATSUrl       string
	ReadTimeout   time.Duration
	WriteTimeout  time.Duration
	RateLimitMax  int
	RateLimitWindow time.Duration
}

func loadConfig() *Config {
	return &Config{
		Port:            getEnv("PORT", "8000"),
		NATSUrl:         getEnv("NATS_URL", "nats://localhost:4222"),
		ReadTimeout:     30 * time.Second,
		WriteTimeout:    30 * time.Second,
		RateLimitMax:    100,
		RateLimitWindow: time.Minute,
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
	globalConfig = cfg

	// Connect to NATS
	msgClient, err := messaging.NewClient(messaging.Config{
		URL:            cfg.NATSUrl,
		Name:           "gateway",
		ReconnectWait:  time.Second,
		MaxReconnects:  60,
		ConnectTimeout: 10 * time.Second,
	})
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}
	defer msgClient.Close()

	// Create gateway
	gw := gateway.NewGateway(gateway.Config{
		Port:            cfg.Port,
		ReadTimeout:     cfg.ReadTimeout,
		WriteTimeout:    cfg.WriteTimeout,
		RateLimitMax:    cfg.RateLimitMax,
		RateLimitWindow: cfg.RateLimitWindow,
	}, msgClient)

	// Start server
	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
	}

	go func() {
		log.Printf("Gateway starting on port %s", cfg.Port)
		if err := gw.Start(":" + cfg.Port); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start gateway: %v", err)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down gateway...")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("Gateway shutdown error: %v", err)
	}

	log.Println("Gateway stopped")
}
