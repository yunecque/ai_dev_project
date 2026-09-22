package domain

import (
	"context"
	"errors"
	"testing"

	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func seedRequest(t *testing.T, store *MemoryStore, id, subject, requestStatus string) {
	t.Helper()
	request := Request{
		ID:        id,
		Title:     "t-" + id,
		Subject:   subject,
		Status:    requestStatus,
		CreatedAt: "2026-09-22T00:00:00Z",
	}
	if err := store.CreateRequestWithEvent(context.Background(), request, Event{Request: request}); err != nil {
		t.Fatalf("seed %s: %v", id, err)
	}
}

func TestGetRequestReturnsStoredRequest(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, "11111111-1111-1111-1111-111111111111", "user-1", statusCreated)
	service := newTestService(store)

	response, err := service.GetRequest(context.Background(), &domainv1.GetRequestRequest{
		RequestId:    "11111111-1111-1111-1111-111111111111",
		ActorSubject: "user-1",
		ActorRole:    roleUser,
	})
	if err != nil {
		t.Fatalf("GetRequest: %v", err)
	}
	if response.GetRequest().GetId() != "11111111-1111-1111-1111-111111111111" {
		t.Fatalf("id = %q", response.GetRequest().GetId())
	}
	if response.GetRequest().GetStatus() != statusCreated {
		t.Fatalf("status = %q", response.GetRequest().GetStatus())
	}
}

func TestGetRequestRequiresID(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.GetRequest(context.Background(), &domainv1.GetRequestRequest{})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}

func TestGetRequestUnknownIsNotFound(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.GetRequest(context.Background(), &domainv1.GetRequestRequest{
		RequestId:    "missing",
		ActorSubject: "user-1",
		ActorRole:    roleUser,
	})
	if status.Code(err) != codes.NotFound {
		t.Fatalf("code = %v, want NotFound", status.Code(err))
	}
}

func TestListRequestsReturnsAllNewestFirst(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, "11111111-1111-1111-1111-111111111111", "user-1", statusCreated)
	seedRequest(t, store, "22222222-2222-2222-2222-222222222222", "user-2", statusTriaged)
	service := newTestService(store)

	response, err := service.ListRequests(context.Background(), &domainv1.ListRequestsRequest{
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if err != nil {
		t.Fatalf("ListRequests: %v", err)
	}
	if len(response.GetRequests()) != 2 {
		t.Fatalf("requests = %d, want 2", len(response.GetRequests()))
	}
}

func TestListRequestsFiltersByStatus(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, "11111111-1111-1111-1111-111111111111", "user-1", statusCreated)
	seedRequest(t, store, "22222222-2222-2222-2222-222222222222", "user-2", statusTriaged)
	service := newTestService(store)

	response, err := service.ListRequests(context.Background(), &domainv1.ListRequestsRequest{
		Status:       statusTriaged,
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if err != nil {
		t.Fatalf("ListRequests: %v", err)
	}
	if len(response.GetRequests()) != 1 {
		t.Fatalf("requests = %d, want 1", len(response.GetRequests()))
	}
	if response.GetRequests()[0].GetId() != "22222222-2222-2222-2222-222222222222" {
		t.Fatalf("id = %q", response.GetRequests()[0].GetId())
	}
}

func TestListRequestsFiltersBySubject(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, "11111111-1111-1111-1111-111111111111", "user-1", statusCreated)
	seedRequest(t, store, "22222222-2222-2222-2222-222222222222", "user-2", statusCreated)
	service := newTestService(store)

	response, err := service.ListRequests(context.Background(), &domainv1.ListRequestsRequest{
		Subject:      "user-2",
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if err != nil {
		t.Fatalf("ListRequests: %v", err)
	}
	if len(response.GetRequests()) != 1 || response.GetRequests()[0].GetId() != "22222222-2222-2222-2222-222222222222" {
		t.Fatalf("unexpected requests: %+v", response.GetRequests())
	}
}

func TestListRequestsRejectsUnknownStatusFilter(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.ListRequests(context.Background(), &domainv1.ListRequestsRequest{
		Status:       "archived",
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}

func TestListRequestsCapsLimit(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, "11111111-1111-1111-1111-111111111111", "user-1", statusCreated)
	service := newTestService(store)

	response, err := service.ListRequests(context.Background(), &domainv1.ListRequestsRequest{
		Limit:        10_000,
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if err != nil {
		t.Fatalf("ListRequests: %v", err)
	}
	if len(response.GetRequests()) != 1 {
		t.Fatalf("requests = %d, want 1", len(response.GetRequests()))
	}
}

func TestListRequestsStoreFailureIsInternal(t *testing.T) {
	store := NewMemoryStore()
	store.failWith = errors.New("db down")
	service := newTestService(store)
	_, err := service.ListRequests(context.Background(), &domainv1.ListRequestsRequest{
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if status.Code(err) != codes.Internal {
		t.Fatalf("code = %v, want Internal", status.Code(err))
	}
}
