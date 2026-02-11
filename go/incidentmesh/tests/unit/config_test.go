package unit

import (
	"strings"
	"testing"
	"incidentmesh/internal/config"
)

func TestConfigEdges(t *testing.T) {
	// L01: LoadPort should return parsed env value, not default
	t.Run("LoadPort_default", func(t *testing.T) {
		p := config.LoadPort("NONEXISTENT_PORT_VAR", 8080)
		if p != 8080 { t.Fatalf("expected default port 8080, got %d", p) }
	})
	t.Run("LoadPort_env", func(t *testing.T) {
		// When env is set, LoadPort should return the parsed value
		
		t.Setenv("TEST_PORT_L01", "9999")
		p := config.LoadPort("TEST_PORT_L01", 8080)
		if p != 9999 { t.Fatalf("expected parsed port 9999, got %d", p) }
	})

	// L02: BuildDatabaseURL should have postgres:// prefix
	t.Run("DatabaseURL_basic", func(t *testing.T) {
		url := config.BuildDatabaseURL("localhost", 5432, "testdb")
		if !strings.HasPrefix(url, "postgres://") {
			t.Fatalf("expected postgres:// prefix, got %s", url)
		}
	})
	t.Run("DatabaseURL_empty", func(t *testing.T) {
		url := config.BuildDatabaseURL("", 0, "")
		if url == "" { t.Fatalf("expected non-empty URL") }
	})

	// L03: BuildRedisURL should use redis:// scheme
	t.Run("RedisURL_basic", func(t *testing.T) {
		url := config.BuildRedisURL("localhost", 6379)
		if !strings.HasPrefix(url, "redis://") {
			t.Fatalf("expected redis:// scheme, got %s", url)
		}
	})
	t.Run("RedisURL_empty", func(t *testing.T) {
		url := config.BuildRedisURL("", 0)
		if url == "" { t.Fatalf("expected non-empty URL") }
	})

	// L04: MergeConfig should merge, not replace
	t.Run("MergeConfig_override", func(t *testing.T) {
		base := map[string]string{"a":"1","b":"2"}
		overlay := map[string]string{"b":"3","c":"4"}
		merged := config.MergeConfig(base, overlay)
		if merged["a"] != "1" { t.Fatalf("expected a=1 from base, got %s", merged["a"]) }
		if merged["b"] != "3" { t.Fatalf("expected b=3 from overlay, got %s", merged["b"]) }
		if merged["c"] != "4" { t.Fatalf("expected c=4 from overlay, got %s", merged["c"]) }
	})
	t.Run("MergeConfig_empty", func(t *testing.T) {
		base := map[string]string{"a":"1"}
		overlay := map[string]string{}
		merged := config.MergeConfig(base, overlay)
		if merged["a"] != "1" { t.Fatalf("expected a=1 preserved, got %s", merged["a"]) }
	})

	// L05: ParseTimeout should return value directly (already ms)
	t.Run("ParseTimeout_valid", func(t *testing.T) {
		v := config.ParseTimeout("5000")
		if v != 5000 { t.Fatalf("expected 5000ms, got %d", v) }
	})
	t.Run("ParseTimeout_negative", func(t *testing.T) {
		v := config.ParseTimeout("-1")
		if v < 0 { t.Fatalf("expected positive or default, got %d", v) }
	})

	// L06: ServiceDiscoveryURL should have / separator
	t.Run("ServiceDiscovery_port", func(t *testing.T) {
		url := config.ServiceDiscoveryURL("http://host:8080", "service")
		if !strings.Contains(url, "/service") {
			t.Fatalf("expected /service in URL, got %s", url)
		}
	})
	t.Run("ServiceDiscovery_zero", func(t *testing.T) {
		url := config.ServiceDiscoveryURL("http://host", "")
		if url == "" { t.Fatalf("expected non-empty") }
	})

	// L07: ParseBool should return false for "false"
	t.Run("ParseBool_true", func(t *testing.T) {
		if !config.ParseBool("true") { t.Fatalf("expected true for 'true'") }
	})
	t.Run("ParseBool_false", func(t *testing.T) {
		if config.ParseBool("false") { t.Fatalf("expected false for 'false'") }
	})
	t.Run("ParseBool_empty", func(t *testing.T) {
		if config.ParseBool("") { t.Fatalf("expected false for empty") }
	})

	// L08: DefaultRegion should return configured value when non-empty
	t.Run("DefaultRegion_empty", func(t *testing.T) {
		r := config.DefaultRegion("")
		if r != "us-east-1" { t.Fatalf("expected us-east-1, got %s", r) }
	})
	t.Run("DefaultRegion_set", func(t *testing.T) {
		r := config.DefaultRegion("eu-west-1")
		if r != "eu-west-1" { t.Fatalf("expected eu-west-1, got %s", r) }
	})
}
