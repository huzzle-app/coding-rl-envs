package services

import (
	"ironfleet/services/notifications"
	"testing"
)

func TestPlanChannelsIncludesEmailAlways(t *testing.T) {
	channels := notifications.PlanChannels(1)
	if len(channels) == 0 || channels[0] != "email" {
		t.Fatal("expected email channel")
	}
}

func TestShouldThrottleRespectsLimit(t *testing.T) {
	if notifications.ShouldThrottle(5, 10, 1) {
		t.Fatal("should not throttle under limit")
	}
	if !notifications.ShouldThrottle(10, 10, 1) {
		t.Fatal("should throttle at limit")
	}
}

func TestFormatNotificationReturnsString(t *testing.T) {
	msg := notifications.FormatNotification("deploy", 3, "new version")
	if msg == "" {
		t.Fatal("expected formatted message")
	}
}

func TestBatchNotifyCreatesNotifications(t *testing.T) {
	sent, notifs := notifications.BatchNotify([]string{"op1", "op2"}, 3, "msg")
	if sent != 2 {
		t.Fatalf("expected 2 sent, got %d", sent)
	}
	if len(notifs) == 0 {
		t.Fatal("expected notifications")
	}
}
