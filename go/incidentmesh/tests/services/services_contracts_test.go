package services

import (
	"testing"
	"time"

	"incidentmesh/services/analytics"
	"incidentmesh/services/auth"
	svcCapacity "incidentmesh/services/capacity"
	svcComms "incidentmesh/services/communications"
	svcCompliance "incidentmesh/services/compliance"
	svcEscalation "incidentmesh/services/escalation"
	"incidentmesh/services/gateway"
	"incidentmesh/services/identity"
	"incidentmesh/services/intake"
	"incidentmesh/services/notifications"
	"incidentmesh/services/resources"
	svcRouting "incidentmesh/services/routing"
	svcTriage "incidentmesh/services/triage"
	"incidentmesh/shared/contracts"
)

func TestServiceContractRoundTrip(t *testing.T) {
	cmd := contracts.IncidentCommand{CommandID: "cmd-1", Region: "north", Action: "triage.score", Payload: map[string]string{"severity": "high"}, IssuedAt: time.Now(), Priority: 5}
	event := svcTriage.New().Handle(cmd)
	if event.EventType == "" || event.CorrelationID != cmd.CommandID {
		t.Fatalf("unexpected event")
	}
}

func TestAllServicesHandle(t *testing.T) {
	cmd := contracts.IncidentCommand{CommandID: "cmd-2", Region: "north", Action: "test", IssuedAt: time.Now(), Priority: 3}
	svcs := []struct {
		name string
		fn   func() contracts.IncidentEvent
	}{
		{"gateway", func() contracts.IncidentEvent { return gateway.New().Handle(cmd) }},
		{"auth", func() contracts.IncidentEvent { return auth.New().Handle(cmd) }},
		{"identity", func() contracts.IncidentEvent { return identity.New().Handle(cmd) }},
		{"intake", func() contracts.IncidentEvent { return intake.New().Handle(cmd) }},
		{"triage", func() contracts.IncidentEvent { return svcTriage.New().Handle(cmd) }},
		{"resources", func() contracts.IncidentEvent { return resources.New().Handle(cmd) }},
		{"routing", func() contracts.IncidentEvent { return svcRouting.New().Handle(cmd) }},
		{"capacity", func() contracts.IncidentEvent { return svcCapacity.New().Handle(cmd) }},
		{"communications", func() contracts.IncidentEvent { return svcComms.New().Handle(cmd) }},
		{"escalation", func() contracts.IncidentEvent { return svcEscalation.New().Handle(cmd) }},
		{"compliance", func() contracts.IncidentEvent { return svcCompliance.New().Handle(cmd) }},
		{"notifications", func() contracts.IncidentEvent { return notifications.New().Handle(cmd) }},
		{"analytics", func() contracts.IncidentEvent { return analytics.New().Handle(cmd) }},
	}
	for _, svc := range svcs {
		t.Run(svc.name+"_Handle", func(t *testing.T) {
			e := svc.fn()
			if e.EventID == "" {
				t.Fatalf("expected event ID")
			}
			if e.CorrelationID != cmd.CommandID {
				t.Fatalf("correlation mismatch")
			}
		})
	}
}

func TestServiceDomainFunctions(t *testing.T) {
	cmd := contracts.IncidentCommand{CommandID: "cmd-3", Region: "north", Action: "dispatch", IssuedAt: time.Now(), Priority: 5}
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"GatewayValidate", func(t *testing.T) {
			err := gateway.New().ValidateRequest(cmd)
			if err != nil { t.Fatalf("expected valid request, got error: %v", err) }
		}},
		{"GatewayRegion", func(t *testing.T) {
			r := gateway.New().ExtractRegion(cmd)
			if r == "" {
				t.Fatalf("expected non-empty")
			}
		}},
		{"AuthAuthenticate", func(t *testing.T) {
			r := auth.New().AuthenticateCommand(cmd)
			if !r { t.Fatalf("expected authenticated command") }
		}},
		{"AuthRole", func(t *testing.T) {
			r := auth.New().RequiredRole("admin.action")
			if r == "" {
				t.Fatalf("expected role")
			}
		}},
		{"IdentityResolve", func(t *testing.T) {
			r := identity.New().ResolveIdentity(cmd)
			if r == "" {
				t.Fatalf("expected identity")
			}
		}},
		{"IntakeBatch", func(t *testing.T) {
			cmds := []contracts.IncidentCommand{cmd, cmd}
			events := intake.New().BatchIntake(cmds)
			if len(events) != 2 {
				t.Fatalf("expected 2")
			}
		}},
		{"IntakeQueue", func(t *testing.T) {
			cmds := []contracts.IncidentCommand{cmd, cmd, cmd}
			q := intake.New().IntakeQueue(cmds, 2)
			if len(q) != 2 { t.Fatalf("expected queue of 2, got %d", len(q)) }
		}},
		{"TriagePriorityRoute", func(t *testing.T) {
			r := svcTriage.New().PriorityRoute(cmd)
			if r == "" {
				t.Fatalf("expected route")
			}
		}},
		{"TriageClassify", func(t *testing.T) {
			c := svcTriage.New().ClassifyCommand(cmd)
			if c == "" {
				t.Fatalf("expected class")
			}
		}},
		{"ResourcesAllocate", func(t *testing.T) {
			r := resources.New().AllocateResources(cmd, 3)
			if len(r) != 3 {
				t.Fatalf("expected 3")
			}
		}},
		{"ResourcePool", func(t *testing.T) {
			p := resources.New().ResourcePool(5)
			if len(p) != 5 { t.Fatalf("expected pool of 5, got %d", len(p)) }
		}},
		{"RoutingOptimal", func(t *testing.T) {
			r := svcRouting.New().OptimalRoute(cmd)
			if r == "" {
				t.Fatalf("expected route")
			}
		}},
		{"RoutingWeight", func(t *testing.T) {
			w := svcRouting.New().RouteWeight(cmd)
			if w <= 0 { t.Fatalf("expected positive route weight, got %.1f", w) }
		}},
		{"CapacityCheck", func(t *testing.T) {
			c := svcCapacity.New().CheckCapacity("north")
			if c <= 0 {
				t.Fatalf("expected positive")
			}
		}},
		{"CapacityEmpty", func(t *testing.T) {
			if svcCapacity.New().CheckCapacity("") != 0 {
				t.Fatalf("expected 0")
			}
		}},
		{"CommsTrace", func(t *testing.T) {
			tr := svcComms.New().MessageTrace(cmd)
			if tr == "" {
				t.Fatalf("expected trace")
			}
		}},
		{"CommsLog", func(t *testing.T) {
			log := svcComms.New().ChannelLog(cmd)
			if len(log) == 0 {
				t.Fatalf("expected entries")
			}
		}},
		{"EscRetry", func(t *testing.T) {
			r := svcEscalation.New().EscalationRetry(cmd, 5)
			
			if r != 5 { t.Fatalf("expected retry count 5, got %d", r) }
		}},
		{"EscBackoff", func(t *testing.T) {
			b := svcEscalation.New().BackoffMs(3)
			if b <= 0 { t.Fatalf("expected positive backoff, got %d", b) }
		}},
		{"CompAudit", func(t *testing.T) {
			a := svcCompliance.New().AuditCommand(cmd)
			if a == "" {
				t.Fatalf("expected audit")
			}
		}},
		{"CompTag", func(t *testing.T) {
			tag := svcCompliance.New().ComplianceTag(cmd)
			if tag == "" {
				t.Fatalf("expected tag")
			}
		}},
		{"NotifSend", func(t *testing.T) {
			err := notifications.New().SendNotification(cmd, "sms")
			if err != nil { t.Fatalf("expected successful send, got: %v", err) }
		}},
		{"NotifPriority", func(t *testing.T) {
			p := notifications.New().NotificationPriority(cmd)
			if p <= 0 { t.Fatalf("expected positive priority, got %d", p) }
		}},
		{"AnalyticsTrack", func(t *testing.T) {
			m := analytics.New().TrackEvent(cmd)
			if len(m) == 0 {
				t.Fatalf("expected metrics")
			}
		}},
		{"AnalyticsLabels", func(t *testing.T) {
			labels := analytics.New().MetricLabels(cmd)
			if len(labels) == 0 {
				t.Fatalf("expected labels")
			}
		}},
		{"CommandValid", func(t *testing.T) {
			if !cmd.CommandValid() {
				t.Fatalf("expected valid")
			}
		}},
		{"CommandInvalid", func(t *testing.T) {
			bad := contracts.IncidentCommand{}
			if bad.CommandValid() {
				t.Fatalf("expected invalid")
			}
		}},
		{"EventValid", func(t *testing.T) {
			e := gateway.New().Handle(cmd)
			if !e.EventValid() {
				t.Fatalf("expected valid")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
