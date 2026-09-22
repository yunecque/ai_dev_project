//go:build integration

package outbox

import (
	"context"
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

func TestPollerPublishesToJetStream(t *testing.T) {
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
	subscription, err := jetstream.SubscribeSync("requests.created", nats.DeliverNew())
	if err != nil {
		t.Fatalf("subscribe: %v", err)
	}
	defer func() { _ = subscription.Unsubscribe() }()

	store := &fakeStore{records: []Record{{
		EventID:   "e1",
		EventType: "request-created",
		Payload:   []byte(`{"event_id":"e1"}`),
	}}}
	poller := NewPoller(store, NewNATSPublisher(jetstream), map[string]string{"request-created": "requests.created"}, 0)

	count, err := poller.PublishBatch(context.Background())
	if err != nil {
		t.Fatalf("PublishBatch: %v", err)
	}
	if count != 1 {
		t.Fatalf("count = %d, want 1", count)
	}
	if len(store.marked) != 1 {
		t.Fatalf("marked = %v, want [e1]", store.marked)
	}

	message, err := subscription.NextMsg(5 * time.Second)
	if err != nil {
		t.Fatalf("next message: %v", err)
	}
	if string(message.Data) != `{"event_id":"e1"}` {
		t.Fatalf("payload = %s", message.Data)
	}
}
