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

const subject = "requests.created"

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
	if _, err := jetstream.AddStream(&nats.StreamConfig{
		Name:     "REQUESTS",
		Subjects: []string{subject},
		Storage:  nats.FileStorage,
	}); err != nil && !errors.Is(err, nats.ErrStreamNameAlreadyInUse) {
		log.Fatalf("publisher: stream: %v", err)
	}

	poller := outbox.NewPoller(
		outbox.NewPostgresStore(pool),
		outbox.NewNATSPublisher(jetstream),
		subject,
		outbox.DefaultBatchSize,
	)

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	log.Printf("publisher: polling outbox -> %s", subject)
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
