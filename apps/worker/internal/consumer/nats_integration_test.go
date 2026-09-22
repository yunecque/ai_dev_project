//go:build integration

package consumer

import (
	"context"
	"sync/atomic"
	"testing"
	"time"

	"github.com/nats-io/nats-server/v2/server"
	"github.com/nats-io/nats.go"
)

func startEmbeddedNATS(t *testing.T) *nats.Conn {
	t.Helper()
	options := &server.Options{JetStream: true, StoreDir: t.TempDir(), Host: "127.0.0.1", Port: -1}
	embedded, err := server.NewServer(options)
	if err != nil {
		t.Fatalf("nats server: %v", err)
	}
	go embedded.Start()
	if !embedded.ReadyForConnections(10 * time.Second) {
		t.Fatal("nats server not ready")
	}
	t.Cleanup(embedded.Shutdown)

	conn, err := nats.Connect(embedded.ClientURL())
	if err != nil {
		t.Fatalf("nats connect: %v", err)
	}
	t.Cleanup(conn.Close)
	return conn
}

func TestHandlerConsumesDuplicateEventOnce(t *testing.T) {
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

	var applied atomic.Int32
	handler := NewHandler(NewMemoryDedupe(), func(context.Context, Event) error {
		applied.Add(1)
		return nil
	})

	subscription, err := jetstream.Subscribe("requests.created", func(message *nats.Msg) {
		if handleErr := handler.Handle(context.Background(), message.Data); handleErr != nil {
			t.Logf("handle: %v", handleErr)
		}
		_ = message.Ack()
	}, nats.Durable("worker-it"), nats.ManualAck(), nats.DeliverAll())
	if err != nil {
		t.Fatalf("subscribe: %v", err)
	}
	defer func() { _ = subscription.Unsubscribe() }()

	payload := []byte(sampleEvent)
	for i := 0; i < 2; i++ {
		if _, err := jetstream.Publish("requests.created", payload); err != nil {
			t.Fatalf("publish %d: %v", i, err)
		}
	}

	deadline := time.Now().Add(5 * time.Second)
	for applied.Load() == 0 && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}
	time.Sleep(300 * time.Millisecond)

	if got := applied.Load(); got != 1 {
		t.Fatalf("applied = %d, want exactly 1 (idempotent)", got)
	}
}
