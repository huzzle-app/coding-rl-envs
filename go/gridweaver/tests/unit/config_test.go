package unit

import (
	"testing"

	"gridweaver/internal/config"
)

func TestConfigExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"DefaultConfig", func(t *testing.T) {
			c := config.DefaultConfig()
			if c == nil {
				t.Fatalf("expected non-nil config")
			}
			if len(c.Regions) == 0 {
				t.Fatalf("expected regions")
			}
		}},
		{"ValidateConfigDefault", func(t *testing.T) {
			c := config.DefaultConfig()
			err := config.ValidateConfig(c)
			_ = err
		}},
		{"ParseRegions", func(t *testing.T) {
			regions := config.ParseRegions("west,east,central")
			if len(regions) != 3 {
				t.Fatalf("expected 3 regions, got %d", len(regions))
			}
		}},
		{"ParseRegionsWithSpaces", func(t *testing.T) {
			regions := config.ParseRegions("west, east, central")
			if len(regions) != 3 {
				t.Fatalf("expected 3 regions")
			}
		}},
		{"GetOverrideMissing", func(t *testing.T) {
			c := config.DefaultConfig()
			_, ok := c.GetOverride("nonexistent")
			if ok {
				t.Fatalf("expected missing override")
			}
		}},
		{"ResolveEndpointNATS", func(t *testing.T) {
			c := config.DefaultConfig()
			ep := config.ResolveEndpoint("nats", c)
			if ep == "" {
				t.Fatalf("expected NATS endpoint")
			}
		}},
		{"ResolveEndpointPostgres", func(t *testing.T) {
			c := config.DefaultConfig()
			ep := config.ResolveEndpoint("postgres", c)
			if ep == "" {
				t.Fatalf("expected Postgres endpoint")
			}
		}},
		{"ResolveEndpointRedis", func(t *testing.T) {
			c := config.DefaultConfig()
			ep := config.ResolveEndpoint("redis", c)
			if ep == "" {
				t.Fatalf("expected Redis endpoint")
			}
		}},
		{"ResolveEndpointUnknown", func(t *testing.T) {
			c := config.DefaultConfig()
			ep := config.ResolveEndpoint("unknown_service", c)
			_ = ep
		}},
		{"MaxRetryBackoff", func(t *testing.T) {
			c := config.DefaultConfig()
			backoff := config.MaxRetryBackoff(c)
			if backoff <= 0 {
				t.Fatalf("expected positive backoff")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
