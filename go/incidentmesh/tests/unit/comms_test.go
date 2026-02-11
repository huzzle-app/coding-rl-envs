package unit

import (
	"testing"
	"incidentmesh/internal/communications"
)

func TestFailoverChannel(t *testing.T) {
	ch := communications.NextChannel("sms", []string{"sms","email","push"})
	if ch == "sms" { t.Fatalf("should failover from primary") }
}

func TestCommsExtended(t *testing.T) {
	cases := []struct{ name string; fn func(t *testing.T) }{
		{"HealthLow", func(t *testing.T) {
			h := communications.ChannelHealth(100, 0.01)
			if h != "healthy" { t.Fatalf("expected healthy") }
		}},
		{"HealthDegraded", func(t *testing.T) {
			h := communications.ChannelHealth(6000, 0.01)
			if h != "degraded" { t.Fatalf("expected degraded") }
		}},
		{"HealthUnhealthy", func(t *testing.T) {
			h := communications.ChannelHealth(100, 0.95)
			
			if h != "unhealthy" { t.Fatalf("95%% error rate should be unhealthy, got %s", h) }
		}},
		{"RetryDelay0", func(t *testing.T) {
			d := communications.RetryDelay(0, 100)
			if d != 100 { t.Fatalf("expected base delay") }
		}},
		{"RetryDelay2", func(t *testing.T) {
			d := communications.RetryDelay(2, 100)
			
			if d < 100 { t.Fatalf("retry delay should increase with attempts, got %d", d) }
		}},
		{"CBClosed", func(t *testing.T) {
			s := communications.CircuitBreakerState(1, 5)
			if s != "closed" { t.Fatalf("expected closed") }
		}},
		{"CBOpen", func(t *testing.T) {
			s := communications.CircuitBreakerState(5, 5)
			if s != "open" { t.Fatalf("expected open") }
		}},
		{"FailoverChain", func(t *testing.T) {
			ch := communications.FailoverChain([]string{"sms","email"}, map[string]bool{"sms":true})
			if ch == "" { t.Fatalf("expected channel") }
		}},
		{"MaxRetries", func(t *testing.T) {
			r := communications.MaxRetries(2)
			if r != 3 { t.Fatalf("expected 3") }
		}},
		{"MaxRetriesHigh", func(t *testing.T) {
			r := communications.MaxRetries(5)
			
			if r < 3 { t.Fatalf("high severity should get more retries, got %d", r) }
		}},
		{"Broadcast", func(t *testing.T) {
			ch := communications.BroadcastChannels([]string{"sms","email","push"}, "sms")
			
			for _, c := range ch {
				if c == "sms" { t.Fatalf("excluded channel 'sms' should not be in result") }
			}
		}},
		{"Priority", func(t *testing.T) {
			if communications.ChannelPriority("sms") != 3 { t.Fatalf("expected 3") }
		}},
		{"Dedup", func(t *testing.T) {
			keys := communications.MessageDedup([]string{"a","b","a"})
			
			if len(keys) != 2 { t.Fatalf("expected 2 unique keys, got %d", len(keys)) }
		}},
	}
	for _, tc := range cases { t.Run(tc.name, tc.fn) }
}
