package domain

import (
	"context"
	"testing"

	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	ownerID   = "11111111-1111-1111-1111-111111111111"
	foreignID = "22222222-2222-2222-2222-222222222222"
)

func TestGetRequestOwnerCanReadOwn(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, ownerID, "user-1", statusCreated)
	service := newTestService(store)

	response, err := service.GetRequest(context.Background(), &domainv1.GetRequestRequest{
		RequestId:    ownerID,
		ActorSubject: "user-1",
		ActorRole:    roleUser,
	})
	if err != nil {
		t.Fatalf("GetRequest: %v", err)
	}
	if response.GetRequest().GetId() != ownerID {
		t.Fatalf("id = %q", response.GetRequest().GetId())
	}
}

func TestGetRequestForeignOwnerIsNotFound(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, ownerID, "user-1", statusCreated)
	service := newTestService(store)

	_, err := service.GetRequest(context.Background(), &domainv1.GetRequestRequest{
		RequestId:    ownerID,
		ActorSubject: "user-2",
		ActorRole:    roleUser,
	})
	if status.Code(err) != codes.NotFound {
		t.Fatalf("code = %v, want NotFound (no existence leak)", status.Code(err))
	}
}

func TestGetRequestOperatorCanReadAny(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, ownerID, "user-1", statusCreated)
	service := newTestService(store)

	if _, err := service.GetRequest(context.Background(), &domainv1.GetRequestRequest{
		RequestId:    ownerID,
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	}); err != nil {
		t.Fatalf("GetRequest: %v", err)
	}
}

func TestGetRequestRequiresIdentity(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, ownerID, "user-1", statusCreated)
	service := newTestService(store)

	_, err := service.GetRequest(context.Background(), &domainv1.GetRequestRequest{RequestId: ownerID})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}

func TestListRequestsScopesToActorForUser(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, ownerID, "user-1", statusCreated)
	seedRequest(t, store, foreignID, "user-2", statusCreated)
	service := newTestService(store)

	response, err := service.ListRequests(context.Background(), &domainv1.ListRequestsRequest{
		ActorSubject: "user-1",
		ActorRole:    roleUser,
	})
	if err != nil {
		t.Fatalf("ListRequests: %v", err)
	}
	if len(response.GetRequests()) != 1 || response.GetRequests()[0].GetId() != ownerID {
		t.Fatalf("unexpected requests: %+v", response.GetRequests())
	}
}

func TestListRequestsOperatorSeesAll(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, ownerID, "user-1", statusCreated)
	seedRequest(t, store, foreignID, "user-2", statusCreated)
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

func TestListRequestsRequiresIdentity(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.ListRequests(context.Background(), &domainv1.ListRequestsRequest{})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}

func TestUpdateStatusRequiresOperator(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, ownerID, "user-1", statusCreated)
	service := newTestService(store)

	_, err := service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId:    ownerID,
		NewStatus:    statusTriaged,
		ActorSubject: "user-1",
		ActorRole:    roleUser,
	})
	if status.Code(err) != codes.PermissionDenied {
		t.Fatalf("code = %v, want PermissionDenied", status.Code(err))
	}
	if got := store.Requests()[0].Status; got != statusCreated {
		t.Fatalf("status must not change, got %q", got)
	}
}

func TestUpdateStatusOperatorSucceeds(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, ownerID, "user-1", statusCreated)
	service := newTestService(store)

	response, err := service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId:    ownerID,
		NewStatus:    statusTriaged,
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if err != nil {
		t.Fatalf("UpdateRequestStatus: %v", err)
	}
	if response.GetRequest().GetStatus() != statusTriaged {
		t.Fatalf("status = %q", response.GetRequest().GetStatus())
	}
}

func TestUpdateStatusRequiresIdentity(t *testing.T) {
	store := NewMemoryStore()
	seedRequest(t, store, ownerID, "user-1", statusCreated)
	service := newTestService(store)

	_, err := service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId: ownerID,
		NewStatus: statusTriaged,
	})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}
