//go:build integration

package consumer

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/nats-io/nats.go"
)

// TestGoldenPathEventSmoke consumes the canonical golden-path event example from the repository
// contract, publishes it twice through embedded JetStream, and asserts exactly-once processing.
// The domain side guarantees the outbox payload matches this same contract
// (apps/domain/internal/domain payload_test.go), closing the async golden path.
func TestGoldenPathEventSmoke(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join(
		"..", "..", "..", "..", "contracts", "events", "examples", "request-created.json",
	))
	if err != nil {
		t.Fatalf("read golden event example: %v", err)
	}
	var expected Event
	if err := json.Unmarshal(raw, &expected); err != nil {
		t.Fatalf("decode golden event example: %v", err)
	}
	if expected.EventType != EventTypeRequestCreated || expected.Request.ID == "" {
		t.Fatalf("golden example is not a valid request-created event: %+v", expected)
	}

	conn := startEmbeddedNATS(t)
	jetstream, err := conn.JetStream()
	if err != nil {
		t.Fatalf("jetstream: %v", err)
	}
	if _, err := jetstream.AddStream(&nats.StreamConfig{
		Name:     "REQUESTS",
		Subjects: []string{"requests.created"},
		Storage:  nats.MemoryStorage,
	}); err != nil {
		t.Fatalf("add stream: %v", err)
	}

	var mu sync.Mutex
	var processed []Event
	handler := NewHandler(NewMemoryDedupe(), func(_ context.Context, event Event) error {
		mu.Lock()
		processed = append(processed, event)
		mu.Unlock()
		return nil
	})

	subscription, err := jetstream.Subscribe("requests.created", func(message *nats.Msg) {
		if handleErr := handler.Handle(context.Background(), message.Data); handleErr != nil {
			t.Logf("handle: %v", handleErr)
		}
		_ = message.Ack()
	}, nats.Durable("e2e-smoke"), nats.ManualAck(), nats.DeliverAll())
	if err != nil {
		t.Fatalf("subscribe: %v", err)
	}
	defer func() { _ = subscription.Unsubscribe() }()

	for i := 0; i < 2; i++ {
		if _, err := jetstream.Publish("requests.created", raw); err != nil {
			t.Fatalf("publish %d: %v", i, err)
		}
	}

	deadline := time.Now().Add(5 * time.Second)
	for {
		mu.Lock()
		count := len(processed)
		mu.Unlock()
		if count > 0 || time.Now().After(deadline) {
			break
		}
		time.Sleep(20 * time.Millisecond)
	}
	time.Sleep(300 * time.Millisecond)

	mu.Lock()
	defer mu.Unlock()
	if len(processed) != 1 {
		t.Fatalf("processed %d events, want exactly 1", len(processed))
	}
	if processed[0].Request.ID != expected.Request.ID {
		t.Fatalf("processed request id = %q, want %q", processed[0].Request.ID, expected.Request.ID)
	}
}

// TestStatusChangedEventSmoke consumes the canonical request-status-changed example twice
// through embedded JetStream and asserts exactly-once processing (M2, TASK-0006).
func TestStatusChangedEventSmoke(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join(
		"..", "..", "..", "..", "contracts", "events", "examples", "request-status-changed.json",
	))
	if err != nil {
		t.Fatalf("read golden event example: %v", err)
	}
	var expected Event
	if err := json.Unmarshal(raw, &expected); err != nil {
		t.Fatalf("decode golden event example: %v", err)
	}
	if expected.EventType != EventTypeRequestStatusChanged || expected.Request.Status == "" {
		t.Fatalf("golden example is not a valid request-status-changed event: %+v", expected)
	}

	conn := startEmbeddedNATS(t)
	jetstream, err := conn.JetStream()
	if err != nil {
		t.Fatalf("jetstream: %v", err)
	}
	if _, err := jetstream.AddStream(&nats.StreamConfig{
		Name:     "REQUESTS",
		Subjects: []string{"requests.status-changed"},
		Storage:  nats.MemoryStorage,
	}); err != nil {
		t.Fatalf("add stream: %v", err)
	}

	var mu sync.Mutex
	var processed []Event
	handler := NewHandler(NewMemoryDedupe(), func(_ context.Context, event Event) error {
		mu.Lock()
		processed = append(processed, event)
		mu.Unlock()
		return nil
	})

	subscription, err := jetstream.Subscribe("requests.status-changed", func(message *nats.Msg) {
		if handleErr := handler.Handle(context.Background(), message.Data); handleErr != nil {
			t.Logf("handle: %v", handleErr)
		}
		_ = message.Ack()
	}, nats.Durable("e2e-status"), nats.ManualAck(), nats.DeliverAll())
	if err != nil {
		t.Fatalf("subscribe: %v", err)
	}
	defer func() { _ = subscription.Unsubscribe() }()

	for i := 0; i < 2; i++ {
		if _, err := jetstream.Publish("requests.status-changed", raw); err != nil {
			t.Fatalf("publish %d: %v", i, err)
		}
	}

	deadline := time.Now().Add(5 * time.Second)
	for {
		mu.Lock()
		count := len(processed)
		mu.Unlock()
		if count > 0 || time.Now().After(deadline) {
			break
		}
		time.Sleep(20 * time.Millisecond)
	}
	time.Sleep(300 * time.Millisecond)

	mu.Lock()
	defer mu.Unlock()
	if len(processed) != 1 {
		t.Fatalf("processed %d events, want exactly 1", len(processed))
	}
	if processed[0].Request.Status != expected.Request.Status {
		t.Fatalf("processed status = %q, want %q", processed[0].Request.Status, expected.Request.Status)
	}
}
