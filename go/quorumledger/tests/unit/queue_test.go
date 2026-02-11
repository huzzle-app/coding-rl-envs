package unit_test

import (
	"testing"

	"quorumledger/internal/queue"
	"quorumledger/pkg/models"
)

func TestShouldShed(t *testing.T) {
	if !queue.ShouldShed(40, 40, false) {
		t.Fatalf("expected shed at max depth")
	}
	if queue.ShouldShed(39, 40, false) {
		t.Fatalf("unexpected shed below max")
	}
	if queue.ShouldShed(50, 40, true) {
		t.Fatalf("should not shed critical")
	}
}

func TestPriorityQueue(t *testing.T) {
	q := queue.NewPriorityQueue(3)
	q.Enqueue(models.QueueItem{ID: "a", Priority: 1})
	q.Enqueue(models.QueueItem{ID: "b", Priority: 5})
	q.Enqueue(models.QueueItem{ID: "c", Priority: 3})
	item, ok := q.Dequeue()
	if !ok || item.ID != "b" {
		t.Fatalf("expected highest priority item b, got %s", item.ID)
	}
}

func TestQueueHealth(t *testing.T) {
	if queue.QueueHealth(49, 100) != "healthy" {
		t.Fatalf("expected healthy at 49/100, got %s", queue.QueueHealth(49, 100))
	}
}

func TestEstimateWaitTime(t *testing.T) {
	if queue.EstimateWaitTime(5, 100) != 500 {
		t.Fatalf("expected 500ms wait, got %d", queue.EstimateWaitTime(5, 100))
	}
}
