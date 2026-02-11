package stress

import (
	"fmt"
	"ironfleet/services/analytics"
	"ironfleet/services/audit"
	"ironfleet/services/gateway"
	"ironfleet/services/notifications"
	"ironfleet/services/policy"
	"ironfleet/services/resilience"
	"ironfleet/services/routing"
	"ironfleet/services/security"
	"testing"
	"time"
)

const totalServiceMeshCases = 2167

func TestServiceMeshMatrix(t *testing.T) {
	for i := 0; i < totalServiceMeshCases; i++ {
		i := i
		t.Run(fmt.Sprintf("case_%05d", i), func(t *testing.T) {
			bucket := i % 8
			switch bucket {
			case 0:
				// gateway: ScoreNode, SelectPrimaryNode, AdmissionControl
				load := float64(i%100) / 100.0
				latency := (i % 50) + 1
				n := gateway.RouteNode{ID: fmt.Sprintf("n-%d", i), Load: load, Healthy: true, Latency: latency}
				score := gateway.ScoreNode(n)
				if score < 0 {
					t.Fatalf("negative score: %f", score)
				}
				nodes := []gateway.RouteNode{
					{ID: "a", Load: 0.2, Healthy: true, Latency: 10},
					{ID: "b", Load: 0.8, Healthy: true, Latency: 5},
					{ID: "c", Load: 0.5, Healthy: i%3 != 0, Latency: 20},
				}
				primary := gateway.SelectPrimaryNode(nodes)
				if primary == nil && i%3 != 0 {
					// At least 2 healthy nodes
				}
				admitted := gateway.AdmissionControl(load*100, 80.0, (i%5)+1)
				_ = admitted

			case 1:
				// audit + analytics
				trail := audit.AuditTrail{Entries: []audit.AuditEntry{
					{Service: "gateway", Action: "route", UserID: fmt.Sprintf("u-%d", i), Success: i%2 == 0, Timestamp: time.Now()},
					{Service: "routing", Action: "plan", UserID: fmt.Sprintf("u-%d", i), Success: true, Timestamp: time.Now()},
				}}
				total, rate := audit.SummarizeTrail(trail)
				if total != 2 {
					t.Fatalf("expected 2 entries, got %d", total)
				}
				if rate < 0 {
					t.Fatalf("negative rate: %f", rate)
				}
				vessels := []analytics.VesselStatus{
					{ID: "v1", Healthy: i%3 != 0, Load: float64(i%100) / 100.0},
					{ID: "v2", Healthy: true, Load: float64((i*7)%100) / 100.0},
				}
				health := analytics.ComputeFleetHealth(vessels)
				if health < 0 || health > 1.0 {
					t.Fatalf("health out of range: %f", health)
				}

			case 2:
				// notifications + policy
				channels := notifications.PlanChannels((i % 5) + 1)
				if len(channels) == 0 {
					t.Fatal("expected at least one channel")
				}
				throttled := notifications.ShouldThrottle(i%20, 15, (i%5)+1)
				_ = throttled
				risk := float64(i%100) / 100.0
				allowed := policy.EvaluatePolicyGate(risk, i%2 == 0, i%3 == 0, (i%5)+1)
				_ = allowed
				band := policy.RiskBand(risk)
				if band == "" {
					t.Fatal("expected risk band")
				}

			case 3:
				// resilience + routing svc
				plan := resilience.BuildReplayPlan((i%50)+1, (i%10)+1, (i%4)+1)
				if plan.Count <= 0 || plan.Budget <= 0 {
					t.Fatal("invalid replay plan")
				}
				mode := resilience.ClassifyReplayMode(100, i%100)
				if mode == "" {
					t.Fatal("expected replay mode")
				}
				legs := []routing.Leg{
					{From: "A", To: "B", Distance: float64((i % 500) + 10), Risk: float64(i%100) / 100.0},
					{From: "B", To: "C", Distance: float64((i*3)%500 + 10), Risk: float64((i*7)%100) / 100.0},
				}
				path := routing.ComputeOptimalPath(legs)
				if len(path) != 2 {
					t.Fatalf("expected 2 legs, got %d", len(path))
				}

			case 4:
				// security svc
				command := fmt.Sprintf("CMD:%d", i)
				sig := "invalid-sig"
				valid := security.ValidateCommandAuth(command, sig, "secret")
				if valid {
					t.Fatal("expected invalid auth")
				}
				safe := security.CheckPathTraversal(fmt.Sprintf("/data/fleet/%d/manifest", i))
				if !safe {
					t.Fatal("expected safe path")
				}
				underLimit := security.RateLimitCheck(i%20, 15, 60)
				_ = underLimit
				riskScore := security.ComputeRiskScore(i%5, i%3 == 0, i%4 == 0)
				if riskScore < 0 || riskScore > 1.0 {
					t.Fatalf("risk score out of range: %f", riskScore)
				}

			case 5:
				// gateway + audit cross-service
				nodes := []gateway.RouteNode{
					{ID: fmt.Sprintf("gw-%d", i), Load: float64(i%100)/100.0, Healthy: true, Latency: (i % 30) + 1},
				}
				ratio := gateway.HealthRatio(nodes)
				if ratio < 0 || ratio > 1.0 {
					t.Fatalf("health ratio out of range: %f", ratio)
				}
				entry := audit.AuditEntry{
					Service: "gateway", Action: "health_check",
					UserID: fmt.Sprintf("sys-%d", i), Timestamp: time.Now(), Success: true,
				}
				if !audit.ValidateAuditEntry(entry) {
					t.Fatal("expected valid audit entry")
				}

			case 6:
				// analytics + notifications cross-service
				vessels := []analytics.VesselStatus{
					{ID: fmt.Sprintf("v-%d", i), Healthy: true, Load: float64(i%100) / 100.0},
					{ID: fmt.Sprintf("v-%d", i+1), Healthy: i%4 != 0, Load: float64((i*3)%100) / 100.0},
				}
				summary := analytics.FleetSummary(vessels)
				if len(summary) != 2 {
					t.Fatal("expected 2 in summary")
				}
				sent, notifs := notifications.BatchNotify([]string{fmt.Sprintf("fleet-%d", i)}, (i%5)+1, "status update")
				if sent != 1 || len(notifs) == 0 {
					t.Fatal("expected notifications")
				}

			case 7:
				// policy + security cross-service
				compliance := policy.ComputeComplianceScore(i%100, 100, 95.0)
				if compliance < 0 {
					t.Fatal("negative compliance")
				}
				strength := security.ValidateSecretStrength(fmt.Sprintf("secret-%d-key", i))
				_ = strength
				dualOK := policy.EnforceDualControl(fmt.Sprintf("op-%d", i), fmt.Sprintf("op-%d", i+1))
				if !dualOK {
					t.Fatal("expected dual control pass")
				}
			}
		})
	}
}
