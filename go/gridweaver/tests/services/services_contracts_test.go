package services

import (
	"testing"
	"time"

	"gridweaver/services/audit"
	"gridweaver/services/auth"
	svcdr "gridweaver/services/demandresponse"
	"gridweaver/services/dispatch"
	svcest "gridweaver/services/estimator"
	"gridweaver/services/forecast"
	"gridweaver/services/gateway"
	svcoutage "gridweaver/services/outage"
	"gridweaver/services/settlement"
	svctopo "gridweaver/services/topology"
	"gridweaver/shared/contracts"
)

func TestServiceContractRoundTrip(t *testing.T) {
	cmd := contracts.GridCommand{CommandID: "cmd-1", Region: "west", Type: "dispatch.plan", Payload: map[string]string{"k": "v"}, IssuedAt: time.Now()}
	event := dispatch.New().Handle(cmd)
	if event.EventType == "" || event.CorrelationID != cmd.CommandID {
		t.Fatalf("unexpected event envelope")
	}
}

func TestServicesExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"GatewayHandle", func(t *testing.T) {
			cmd := contracts.GridCommand{CommandID: "g1", Region: "west", Type: "dispatch.plan"}
			event := gateway.New().Handle(cmd)
			if event.CorrelationID != "g1" {
				t.Fatalf("unexpected correlation ID")
			}
		}},
		{"GatewayRouteCommand", func(t *testing.T) {
			cmd := contracts.GridCommand{Type: "dispatch.plan"}
			route := gateway.RouteCommand(cmd)
			if route != "dispatch" {
				t.Fatalf("dispatch.plan should route to dispatch, got %s", route)
			}
		}},
		{"GatewayValidateHeaders", func(t *testing.T) {
			headers := map[string]string{"X-Request-ID": "r1", "X-Region": "west"}
			result := gateway.ValidateHeaders(headers)
			if !result {
				t.Fatalf("expected valid headers with X-Request-ID and X-Region")
			}
		}},
		{"GatewayNormalizeRegion", func(t *testing.T) {
			if gateway.NormalizeRegion(" WEST ") != "west" {
				t.Fatalf("expected normalized region")
			}
		}},
		{"GatewayIsHealthy", func(t *testing.T) {
			svc := gateway.New()
			if !svc.IsHealthy() {
				t.Fatalf("expected healthy")
			}
		}},
		{"GatewayRequestMetrics", func(t *testing.T) {
			start := time.Now()
			end := start.Add(100 * time.Millisecond)
			metrics := gateway.RequestMetrics(start, end)
			if metrics["latency_ms"] <= 0 {
				t.Fatalf("expected positive latency for 100ms duration, got %d", metrics["latency_ms"])
			}
		}},
		{"AuthHandle", func(t *testing.T) {
			cmd := contracts.GridCommand{CommandID: "a1", Region: "west", Type: "auth"}
			event := auth.New().Handle(cmd)
			if event.CorrelationID != "a1" {
				t.Fatalf("unexpected correlation ID")
			}
		}},
		{"AuthDefaultRoles", func(t *testing.T) {
			roles := auth.DefaultRoles()
			if len(roles) != 3 {
				t.Fatalf("expected 3 roles")
			}
			found := false
			for _, r := range roles {
				if r == "grid_admin" {
					found = true
				}
			}
			if !found {
				t.Fatalf("expected grid_admin in default roles, got %v", roles)
			}
		}},
		{"AuthValidateCredentials", func(t *testing.T) {
			result := auth.ValidateCredentials("hash123", "hash123")
			if !result {
				t.Fatalf("matching credentials should validate")
			}
		}},
		{"AuthRoleExists", func(t *testing.T) {
			if !auth.RoleExists("observer") {
				t.Fatalf("expected observer to exist")
			}
		}},
		{"AuthGrantPermission", func(t *testing.T) {
			if !auth.GrantPermission("grid_admin", "control.substation") {
				t.Fatalf("expected permission granted")
			}
		}},
		{"AuthIsAuthenticated", func(t *testing.T) {
			if !auth.IsAuthenticated("token123") {
				t.Fatalf("expected authenticated")
			}
			if auth.IsAuthenticated("") {
				t.Fatalf("expected not authenticated for empty token")
			}
		}},
		{"DispatchRecordEvent", func(t *testing.T) {
			svc := dispatch.New()
			event := contracts.GridEvent{EventID: "e1", EventType: "dispatch.handled"}
			svc.RecordEvent(event)
			if svc.HistoryCount() < 1 {
				t.Fatalf("expected recorded event")
			}
		}},
		{"DispatchGetHistory", func(t *testing.T) {
			svc := dispatch.New()
			event := contracts.GridEvent{EventID: "e1"}
			svc.RecordEvent(event)
			h := svc.GetHistory()
			if len(h) < 1 {
				t.Fatalf("expected history")
			}
		}},
		{"DispatchClearHistory", func(t *testing.T) {
			svc := dispatch.New()
			svc.RecordEvent(contracts.GridEvent{EventID: "e1"})
			svc.ClearHistory()
			if svc.HistoryCount() != 0 {
				t.Fatalf("expected empty history")
			}
		}},
		{"DispatchLastEvent", func(t *testing.T) {
			svc := dispatch.New()
			svc.RecordEvent(contracts.GridEvent{EventID: "e1"})
			svc.RecordEvent(contracts.GridEvent{EventID: "e2"})
			last := svc.LastEvent()
			if last == nil || last.EventID != "e2" {
				t.Fatalf("expected last event e2")
			}
		}},
		{"SettlementCalculateTotal", func(t *testing.T) {
			total := settlement.CalculateTotal(10.5, 100)
			if total != 1050 {
				t.Fatalf("expected 1050 (10.5 * 100), got %d", total)
			}
		}},
		{"SettlementApplyDiscount", func(t *testing.T) {
			result := settlement.ApplyDiscount(10000, 10)
			if result != 9000 {
				t.Fatalf("expected 9000 (10%% discount on 10000), got %d", result)
			}
		}},
		{"SettlementAggregateSettlements", func(t *testing.T) {
			total := settlement.AggregateSettlements([]int64{100, 200, -50, 300})
			if total != 550 {
				t.Fatalf("expected sum 550, got %d", total)
			}
		}},
		{"SettlementFormatCents", func(t *testing.T) {
			str := settlement.FormatCents(1234)
			if str != "$12.34" {
				t.Fatalf("expected $12.34, got %s", str)
			}
		}},
		{"SettlementFormatCentsNegative", func(t *testing.T) {
			str := settlement.FormatCents(-567)
			if str != "-$5.67" {
				t.Fatalf("expected -$5.67, got %s", str)
			}
		}},
		{"SettlementValidate", func(t *testing.T) {
			if !settlement.ValidateSettlement("west", "2024-Q1", 100.0) {
				t.Fatalf("expected valid settlement")
			}
			if settlement.ValidateSettlement("", "2024-Q1", 100.0) {
				t.Fatalf("expected invalid for empty region")
			}
		}},
		{"AuditRecordEntry", func(t *testing.T) {
			svc := audit.New()
			svc.RecordEntry("admin", "dispatch", "grid-west", "success", 1000)
			entries := svc.AllEntries()
			if len(entries) != 1 {
				t.Fatalf("expected 1 entry")
			}
			if entries[0].Timestamp != 1000 {
				t.Fatalf("expected timestamp 1000, got %d", entries[0].Timestamp)
			}
		}},
		{"AuditQueryByActor", func(t *testing.T) {
			svc := audit.New()
			svc.RecordEntry("admin", "dispatch", "grid", "ok", 1000)
			svc.RecordEntry("user", "read", "grid", "ok", 1001)
			results := svc.QueryByActor("admin")
			if len(results) != 1 {
				t.Fatalf("expected 1 admin entry, got %d", len(results))
			}
		}},
		{"AuditEntryCount", func(t *testing.T) {
			svc := audit.New()
			svc.RecordEntry("admin", "dispatch", "grid", "ok", 1000)
			count := svc.EntryCount()
			if count != 1 {
				t.Fatalf("expected count 1, got %d", count)
			}
		}},
		{"AuditHasEntry", func(t *testing.T) {
			svc := audit.New()
			svc.RecordEntry("admin", "dispatch", "grid", "ok", 1000)
			if !svc.HasEntry("dispatch") {
				t.Fatalf("expected to find dispatch entry")
			}
			if svc.HasEntry("nonexistent") {
				t.Fatalf("should not find nonexistent entry")
			}
		}},
		{"AuditLastEntry", func(t *testing.T) {
			svc := audit.New()
			svc.RecordEntry("admin", "action1", "r1", "ok", 1000)
			svc.RecordEntry("admin", "action2", "r2", "ok", 1001)
			last := svc.LastEntry()
			if last == nil || last.Action != "action2" {
				t.Fatalf("expected last entry action2")
			}
		}},
		{"AuditClearEntries", func(t *testing.T) {
			svc := audit.New()
			svc.RecordEntry("admin", "dispatch", "grid", "ok", 1000)
			svc.ClearEntries()
			if len(svc.AllEntries()) != 0 {
				t.Fatalf("expected empty after clear")
			}
		}},
		{"OutageResolveNonExistent", func(t *testing.T) {
			svc := svcoutage.New()
			svc.ReportOutage("o1")
			if !svc.ResolveOutage("o1") {
				t.Fatalf("expected true when resolving existing outage")
			}
			if svc.ResolveOutage("nonexistent") {
				t.Fatalf("expected false when resolving non-existent outage")
			}
		}},
		{"TopologyDefaultRegionsUnique", func(t *testing.T) {
			regions := svctopo.DefaultRegions()
			seen := map[string]bool{}
			for _, r := range regions {
				if seen[r] {
					t.Fatalf("duplicate region %q in DefaultRegions", r)
				}
				seen[r] = true
			}
		}},
		{"ForecastTemperatureImpact", func(t *testing.T) {
			// At 22°C (comfortable), impact on 1000MW should be near baseline
			result := forecast.TemperatureImpact(22, 1000)
			if result < 900 || result > 1100 {
				t.Fatalf("expected ~1000 for 22C baseline, got %f (using Fahrenheit reference?)", result)
			}
		}},
		{"EstimatorCacheLoadPersists", func(t *testing.T) {
			svc := svcest.New()
			svc.CacheLoad("west", 500.0)
			svc.CacheLoad("east", 300.0)
			svc.ClearCache()
			_, ok := svc.GetCachedLoad("west")
			if ok {
				t.Fatalf("expected cache cleared after ClearCache")
			}
		}},
		{"DRDispatchCount", func(t *testing.T) {
			svc := svcdr.New()
			svc.RecordDispatch("d1")
			svc.RecordDispatch("d2")
			svc.RecordDispatch("d3")
			count := svc.DispatchCount()
			if count != 3 {
				t.Fatalf("expected dispatch count 3 after 3 dispatches, got %d", count)
			}
		}},
		{"ContractValidation", func(t *testing.T) {
			cmd := contracts.GridCommand{CommandID: "c1", Region: "west", Type: "dispatch.plan"}
			result := cmd.Validate()
			if !result.Valid {
				t.Fatalf("expected valid command")
			}
		}},
		{"ContractValidationMissing", func(t *testing.T) {
			cmd := contracts.GridCommand{}
			result := cmd.Validate()
			if result.Valid {
				t.Fatalf("expected invalid for empty command")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
