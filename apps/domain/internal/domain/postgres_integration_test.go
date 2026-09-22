//go:build integration

package domain

import (
	"context"
	"errors"
	"os"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
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

func TestPostgresStoreUpdatesStatusAndOutboxAtomically(t *testing.T) {
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
	created := Event{EventID: eventID1, EventType: eventTypeRequestCreated, OccurredAt: createdAt, Request: request}
	if err := store.CreateRequestWithEvent(ctx, request, created); err != nil {
		t.Fatalf("create: %v", err)
	}

	updated := request
	updated.Status = statusTriaged
	change := Event{
		EventID:        eventID2,
		EventType:      eventTypeRequestStatusChanged,
		OccurredAt:     createdAt,
		Request:        updated,
		PreviousStatus: statusCreated,
	}
	if err := store.UpdateRequestStatusWithEvent(ctx, updated, change); err != nil {
		t.Fatalf("update: %v", err)
	}

	if requests, outbox := countRows(t, ctx, pool); requests != 1 || outbox != 2 {
		t.Fatalf("requests=%d outbox=%d, want 1/2", requests, outbox)
	}

	loaded, err := store.GetRequest(ctx, requestID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if loaded.Status != statusTriaged {
		t.Fatalf("status = %q, want triaged", loaded.Status)
	}
	if loaded.CreatedAt != createdAt {
		t.Fatalf("created_at = %q, want %q", loaded.CreatedAt, createdAt)
	}

	// Unknown request id must not append an outbox row.
	unknown := request
	unknown.ID = "99999999-9999-9999-9999-999999999999"
	orphan := Event{EventID: eventID2, EventType: eventTypeRequestStatusChanged, OccurredAt: createdAt, Request: unknown}
	if err := store.UpdateRequestStatusWithEvent(ctx, unknown, orphan); !errors.Is(err, ErrRequestNotFound) {
		t.Fatalf("error = %v, want ErrRequestNotFound", err)
	}
	if requests, outbox := countRows(t, ctx, pool); requests != 1 || outbox != 2 {
		t.Fatalf("after failed update requests=%d outbox=%d, want 1/2", requests, outbox)
	}
}

func TestPostgresStoreListRequestsFilters(t *testing.T) {
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

	first := Request{ID: requestID, Title: "t1", Subject: "user-1", Status: statusCreated, CreatedAt: createdAt}
	second := Request{ID: "44444444-4444-4444-4444-444444444444", Title: "t2", Subject: "user-2", Status: statusTriaged, CreatedAt: "2026-09-23T00:00:00Z"}
	for i, request := range []Request{first, second} {
		event := Event{EventID: eventID1, EventType: eventTypeRequestCreated, OccurredAt: request.CreatedAt, Request: request}
		if i == 1 {
			event.EventID = eventID2
		}
		if err := store.CreateRequestWithEvent(ctx, request, event); err != nil {
			t.Fatalf("seed %d: %v", i, err)
		}
	}

	all, err := store.ListRequests(ctx, ListFilter{Limit: 10})
	if err != nil {
		t.Fatalf("list all: %v", err)
	}
	if len(all) != 2 || all[0].ID != second.ID {
		t.Fatalf("all = %+v, want newest first", all)
	}

	byStatus, err := store.ListRequests(ctx, ListFilter{Status: statusTriaged, Limit: 10})
	if err != nil {
		t.Fatalf("list by status: %v", err)
	}
	if len(byStatus) != 1 || byStatus[0].ID != second.ID {
		t.Fatalf("byStatus = %+v", byStatus)
	}

	bySubject, err := store.ListRequests(ctx, ListFilter{Subject: "user-1", Limit: 10})
	if err != nil {
		t.Fatalf("list by subject: %v", err)
	}
	if len(bySubject) != 1 || bySubject[0].ID != first.ID {
		t.Fatalf("bySubject = %+v", bySubject)
	}
}

// TestOperatorLifecycleFlowIntegration exercises the full operator lifecycle against Postgres:
// create -> triaged -> in_progress -> resolved -> closed, then reads it back and checks the
// outbox contains exactly one created event plus four status-changed events (M2, TASK-0006).
func TestOperatorLifecycleFlowIntegration(t *testing.T) {
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
	service := NewService(store)

	created, err := service.CreateRequest(ctx, &domainv1.CreateRequestRequest{Title: "flow", Subject: "user-1"})
	if err != nil {
		t.Fatalf("CreateRequest: %v", err)
	}
	id := created.GetRequest().GetId()

	for _, next := range []string{statusTriaged, statusInProgress, statusResolved, statusClosed} {
		if _, err := service.UpdateRequestStatus(ctx, &domainv1.UpdateRequestStatusRequest{
			RequestId:    id,
			NewStatus:    next,
			ActorSubject: "operator-1",
			ActorRole:    roleOperator,
		}); err != nil {
			t.Fatalf("transition to %s: %v", next, err)
		}
	}

	got, err := service.GetRequest(ctx, &domainv1.GetRequestRequest{
		RequestId:    id,
		ActorSubject: "user-1",
		ActorRole:    roleUser,
	})
	if err != nil {
		t.Fatalf("GetRequest: %v", err)
	}
	if got.GetRequest().GetStatus() != statusClosed {
		t.Fatalf("final status = %q, want closed", got.GetRequest().GetStatus())
	}

	var requests, createdEvents, changedEvents int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM requests").Scan(&requests); err != nil {
		t.Fatalf("count requests: %v", err)
	}
	if err := pool.QueryRow(ctx,
		"SELECT count(*) FROM outbox WHERE event_type = $1", eventTypeRequestCreated,
	).Scan(&createdEvents); err != nil {
		t.Fatalf("count created events: %v", err)
	}
	if err := pool.QueryRow(ctx,
		"SELECT count(*) FROM outbox WHERE event_type = $1", eventTypeRequestStatusChanged,
	).Scan(&changedEvents); err != nil {
		t.Fatalf("count status events: %v", err)
	}
	if requests != 1 || createdEvents != 1 || changedEvents != 4 {
		t.Fatalf("requests=%d created=%d changed=%d, want 1/1/4", requests, createdEvents, changedEvents)
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
