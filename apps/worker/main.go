package main

import (
	"context"
	"log"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/nats-io/nats.go"
	"github.com/yunecque/ai_dev_project/apps/worker/internal/consumer"
)

const subject = "requests.created"

func main() {
	ctx := context.Background()
	dsn := getenv("DATABASE_URL", "postgres://sdlc:sdlc-dev-password@localhost:5432/requests")
	natsURL := getenv("NATS_URL", nats.DefaultURL)

	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		log.Fatalf("worker: postgres: %v", err)
	}
	defer pool.Close()

	conn, err := nats.Connect(natsURL)
	if err != nil {
		log.Fatalf("worker: nats: %v", err)
	}
	defer func() { _ = conn.Drain() }()

	jetstream, err := conn.JetStream()
	if err != nil {
		log.Fatalf("worker: jetstream: %v", err)
	}

	handler := consumer.NewHandler(
		consumer.NewPostgresDedupe(pool),
		func(_ context.Context, event consumer.Event) error {
			log.Printf("worker: processed %s request=%s", event.EventID, event.Request.ID)
			return nil
		},
	)

	subscription, err := jetstream.Subscribe(subject, func(msg *nats.Msg) {
		if err := handler.Handle(context.Background(), msg.Data); err != nil {
			log.Printf("worker: %v", err)
			return
		}
		if err := msg.Ack(); err != nil {
			log.Printf("worker: ack: %v", err)
		}
	}, nats.Durable("worker"), nats.ManualAck(), nats.DeliverAll())
	if err != nil {
		log.Fatalf("worker: subscribe: %v", err)
	}
	defer func() { _ = subscription.Unsubscribe() }()

	log.Printf("worker: subscribed to %s", subject)
	select {}
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
