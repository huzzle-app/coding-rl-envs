package services

import (
	"testing"
	"time"

	"gridweaver/services/audit"
	"gridweaver/services/auth"
	"gridweaver/services/dispatch"
	"gridweaver/services/gateway"
	"gridweaver/services/settlement"
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
			_ = route 
		}},
		{"GatewayValidateHeaders", func(t *testing.T) {
			headers := map[string]string{"X-Request-ID": "r1", "X-Region": "west"}
			result := gateway.ValidateHeaders(headers)
			_ = result 
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
			_ = metrics 
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
		}},
		{"AuthValidateCredentials", func(t *testing.T) {
			result := auth.ValidateCredentials("hash123", "hash123")
			_ = result 
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
			_ = total 
		}},
		{"SettlementApplyDiscount", func(t *testing.T) {
			result := settlement.ApplyDiscount(10000, 10)
			_ = result 
		}},
		{"SettlementAggregateSettlements", func(t *testing.T) {
			total := settlement.AggregateSettlements([]int64{100, 200, -50, 300})
			_ = total 
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
			if len(svc.AllEntries()) != 1 {
				t.Fatalf("expected 1 entry")
			}
		}},
		{"AuditQueryByActor", func(t *testing.T) {
			svc := audit.New()
			svc.RecordEntry("admin", "dispatch", "grid", "ok", 1000)
			svc.RecordEntry("user", "read", "grid", "ok", 1001)
			results := svc.QueryByActor("admin")
			_ = results 
		}},
		{"AuditEntryCount", func(t *testing.T) {
			svc := audit.New()
			svc.RecordEntry("admin", "dispatch", "grid", "ok", 1000)
			count := svc.EntryCount()
			_ = count 
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
