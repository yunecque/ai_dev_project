package domain

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var fixedNow = time.Date(2026, 9, 22, 12, 0, 0, 0, time.UTC)

func newTestService(store Store) *Service {
	service := NewService(store)
	service.now = func() time.Time { return fixedNow }
	ids := []string{
		"11111111-1111-1111-1111-111111111111",
		"22222222-2222-2222-2222-222222222222",
		"33333333-3333-3333-3333-333333333333",
		"44444444-4444-4444-4444-444444444444",
	}
	index := 0
	service.newID = func() string {
		id := ids[index%len(ids)]
		index++
		return id
	}
	return service
}

func TestCreateRequestPersistsRequestAndEvent(t *testing.T) {
	store := NewMemoryStore()
	service := newTestService(store)

	response, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:       "Reset VPN access",
		Description: "please",
		Subject:     "user-123",
	})
	if err != nil {
		t.Fatalf("CreateRequest: %v", err)
	}

	if response.GetRequest().GetId() != "11111111-1111-1111-1111-111111111111" {
		t.Fatalf("id = %q", response.GetRequest().GetId())
	}
	if response.GetRequest().GetStatus() != "created" {
		t.Fatalf("status = %q, want created", response.GetRequest().GetStatus())
	}
	if response.GetRequest().GetCreatedAt() != fixedNow.Format(time.RFC3339) {
		t.Fatalf("created_at = %q", response.GetRequest().GetCreatedAt())
	}

	requests := store.Requests()
	if len(requests) != 1 {
		t.Fatalf("stored requests = %d, want 1", len(requests))
	}
	if requests[0].Subject != "user-123" {
		t.Fatalf("subject = %q", requests[0].Subject)
	}

	events := store.Events()
	if len(events) != 1 {
		t.Fatalf("stored events = %d, want 1", len(events))
	}
	if events[0].EventType != eventTypeRequestCreated {
		t.Fatalf("event type = %q", events[0].EventType)
	}
	if events[0].Request.ID != requests[0].ID {
		t.Fatalf("event request id = %q, want %q", events[0].Request.ID, requests[0].ID)
	}
	if events[0].OccurredAt != requests[0].CreatedAt {
		t.Fatalf("event occurred_at and request created_at must match")
	}
}

func TestCreateRequestTrimsTitle(t *testing.T) {
	store := NewMemoryStore()
	service := newTestService(store)
	if _, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:   "  spaced  ",
		Subject: "user-1",
	}); err != nil {
		t.Fatalf("CreateRequest: %v", err)
	}
	if got := store.Requests()[0].Title; got != "spaced" {
		t.Fatalf("title = %q, want trimmed", got)
	}
}

func TestCreateRequestRejectsWhitespaceOnlyTitle(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:   "   ",
		Subject: "user-1",
	})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}

func TestCreateRequestRequiresSubject(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{Title: "x"})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}

func TestCreateRequestRejectsLongTitle(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:   strings.Repeat("a", maxTitleLen+1),
		Subject: "user-1",
	})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}

func TestCreateRequestRejectsLongDescription(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:       "ok",
		Description: strings.Repeat("d", maxDescriptionLen+1),
		Subject:     "user-1",
	})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}

func TestCreateRequestStoreFailureIsInternal(t *testing.T) {
	store := NewMemoryStore()
	store.failWith = errors.New("db down")
	service := newTestService(store)
	_, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:   "ok",
		Subject: "user-1",
	})
	if status.Code(err) != codes.Internal {
		t.Fatalf("code = %v, want Internal", status.Code(err))
	}
}

func TestValidLengthCountsRunes(t *testing.T) {
	if !validLength(strings.Repeat("я", maxTitleLen), 1, maxTitleLen) {
		t.Fatal("expected 200 cyrillic runes to be valid")
	}
	if validLength(strings.Repeat("я", maxTitleLen+1), 1, maxTitleLen) {
		t.Fatal("expected 201 runes to be invalid")
	}
}
