//go:build integration

package domain

import (
	"context"
	"os"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	requestID = "11111111-1111-1111-1111-111111111111"
	eventID1  = "22222222-2222-2222-2222-222222222222"
	eventID2  = "33333333-3333-3333-3333-333333333333"
	createdAt = "2026-09-22T00:00:00Z"
)

func applyMigrations(t *testing.T, ctx context.Context, pool *pgxpool.Pool) {
	t.Helper()
	raw, err := os.ReadFile("../../migrations/0001_init.sql")
	if err != nil {
		t.Fatalf("read migrations: %v", err)
	}
	for _, statement := range strings.Split(string(raw), ";") {
		statement = strings.TrimSpace(statement)
		if statement == "" {
			continue
		}
		if _, err := pool.Exec(ctx, statement); err != nil {
			t.Fatalf("migrate: %v", err)
		}
	}
}

func TestPostgresStorePersistsRequestAndOutboxAtomically(t *testing.T) {
	dsn := os.Getenv("TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("TEST_DATABASE_URL not set")
	}
	ctx := context.Background()

	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("pool: %v", err)
	}
	defer pool.Close()
	applyMigrations(t, ctx, pool)
	if _, err := pool.Exec(ctx, "TRUNCATE requests, outbox"); err != nil {
		t.Fatalf("truncate: %v", err)
	}

	store, err := NewPostgresStore(ctx, dsn)
	if err != nil {
		t.Fatalf("store: %v", err)
	}
	defer store.Close()

	request := Request{ID: requestID, Title: "t", Subject: "u", Status: statusCreated, CreatedAt: createdAt}
	event := Event{EventID: eventID1, EventType: eventTypeRequestCreated, OccurredAt: createdAt, Request: request}
	if err := store.CreateRequestWithEvent(ctx, request, event); err != nil {
		t.Fatalf("create: %v", err)
	}

	if requests, outbox := countRows(t, ctx, pool); requests != 1 || outbox != 1 {
		t.Fatalf("requests=%d outbox=%d, want 1/1", requests, outbox)
	}

	// Atomicity: a duplicate request id must roll back the outbox insert too.
	event2 := Event{EventID: eventID2, EventType: eventTypeRequestCreated, OccurredAt: createdAt, Request: request}
	if err := store.CreateRequestWithEvent(ctx, request, event2); err == nil {
		t.Fatal("expected duplicate request id error")
	}
	if requests, outbox := countRows(t, ctx, pool); requests != 1 || outbox != 1 {
		t.Fatalf("after failed tx requests=%d outbox=%d, want 1/1 (no partial write)", requests, outbox)
	}
}

func countRows(t *testing.T, ctx context.Context, pool *pgxpool.Pool) (int, int) {
	t.Helper()
	var requests, outbox int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM requests").Scan(&requests); err != nil {
		t.Fatalf("count requests: %v", err)
	}
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM outbox").Scan(&outbox); err != nil {
		t.Fatalf("count outbox: %v", err)
	}
	return requests, outbox
}
