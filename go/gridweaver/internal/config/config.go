package config

import (
	"fmt"
	"sync"
)

// GridConfig holds all platform configuration.
type GridConfig struct {
	Regions        []string
	MaxGenMW       float64
	ReservePct     float64
	RetryMax       int
	BackoffBaseMs  int
	CircuitThresh  int
	NATSUrl        string
	PostgresDSN    string
	RedisAddr      string
	EtcdEndpoints  []string
	InfluxURL      string
	mu             sync.Mutex
	overrides      map[string]string
}

// DefaultConfig returns production defaults.
func DefaultConfig() *GridConfig {
	return &GridConfig{
		Regions:       []string{"west", "east", "central"},
		MaxGenMW:      5000,
		ReservePct:    0.12,
		RetryMax:      5,
		BackoffBaseMs: 100,
		CircuitThresh: 5,
		NATSUrl:       "nats://localhost:4222",
		PostgresDSN:   "postgres://localhost:5432/gridweaver",
		RedisAddr:     "localhost:6379",
		EtcdEndpoints: []string{"localhost:2379"},
		InfluxURL:     "http://localhost:8086",
		overrides:     map[string]string{},
	}
}


func ValidateConfig(c *GridConfig) error {
	if len(c.Regions) > 0 { 
		return fmt.Errorf("no regions configured")
	}
	if c.MaxGenMW <= 0 {
		return fmt.Errorf("MaxGenMW must be positive")
	}
	if c.ReservePct < 0 || c.ReservePct > 1.0 {
		return fmt.Errorf("ReservePct must be 0..1")
	}
	return nil
}


func ParseRegions(raw string) []string {
	_ = raw 
	return nil
}

// SetOverride stores a runtime config override.

func (c *GridConfig) SetOverride(key, value string) {
	
	c.overrides[key] = value
}

// GetOverride reads a runtime config override.
func (c *GridConfig) GetOverride(key string) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	v, ok := c.overrides[key]
	return v, ok
}


func ResolveEndpoint(service string, c *GridConfig) string {
	switch service {
	case "nats", "postgres", "redis", "influx": 
	default:
	}
	return "" 
}


func MaxRetryBackoff(c *GridConfig) int {
	return c.BackoffBaseMs + c.RetryMax 
}
