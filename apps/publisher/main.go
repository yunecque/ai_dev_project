package main

import (
	"context"
	"errors"
	"log"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/nats-io/nats.go"
	"github.com/yunecque/ai_dev_project/apps/publisher/internal/outbox"
)

// eventSubjects maps each domain event type to its NATS subject.
var eventSubjects = map[string]string{
	"request-created":        "requests.created",
	"request-status-changed": "requests.status-changed",
}

func main() {
	ctx := context.Background()
	dsn := getenv("DATABASE_URL", "postgres://sdlc:sdlc-dev-password@localhost:5432/requests")
	natsURL := getenv("NATS_URL", nats.DefaultURL)

	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		log.Fatalf("publisher: postgres: %v", err)
	}
	defer pool.Close()

	conn, err := nats.Connect(natsURL)
	if err != nil {
		log.Fatalf("publisher: nats: %v", err)
	}
	defer func() { _ = conn.Drain() }()

	jetstream, err := conn.JetStream()
	if err != nil {
		log.Fatalf("publisher: jetstream: %v", err)
	}
	subjects := make([]string, 0, len(eventSubjects))
	for _, subject := range eventSubjects {
		subjects = append(subjects, subject)
	}
	if _, err := jetstream.AddStream(&nats.StreamConfig{
		Name:     "REQUESTS",
		Subjects: subjects,
		Storage:  nats.FileStorage,
	}); err != nil && !errors.Is(err, nats.ErrStreamNameAlreadyInUse) {
		log.Fatalf("publisher: stream: %v", err)
	}

	poller := outbox.NewPoller(
		outbox.NewPostgresStore(pool),
		outbox.NewNATSPublisher(jetstream),
		eventSubjects,
		outbox.DefaultBatchSize,
	)

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	log.Printf("publisher: polling outbox -> %v", subjects)
	for range ticker.C {
		published, err := poller.PublishBatch(ctx)
		if err != nil {
			log.Printf("publisher: %v", err)
			continue
		}
		if published > 0 {
			log.Printf("publisher: published %d event(s)", published)
		}
	}
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
