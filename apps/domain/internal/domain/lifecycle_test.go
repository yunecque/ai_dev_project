package domain

import (
	"context"
	"errors"
	"testing"

	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var allStatuses = []string{
	statusCreated,
	statusTriaged,
	statusInProgress,
	statusResolved,
	statusClosed,
	statusCancelled,
}

func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func TestCanTransitionMatchesLifecycleTable(t *testing.T) {
	allowed := map[string][]string{
		statusCreated:    {statusTriaged, statusCancelled},
		statusTriaged:    {statusInProgress, statusCancelled},
		statusInProgress: {statusResolved, statusCancelled},
		statusResolved:   {statusClosed},
		statusClosed:     {},
		statusCancelled:  {},
	}
	for from, targets := range allowed {
		for _, to := range allStatuses {
			want := contains(targets, to)
			if got := CanTransition(from, to); got != want {
				t.Errorf("CanTransition(%q, %q) = %v, want %v", from, to, got, want)
			}
		}
	}
}

func TestCanTransitionRejectsUnknownStatuses(t *testing.T) {
	if CanTransition("archived", statusTriaged) {
		t.Error("unknown source status must not be transitionable")
	}
	if CanTransition(statusCreated, "archived") {
		t.Error("unknown target status must not be transitionable")
	}
}

func TestUpdateRequestStatusAppliesTransitionAndEmitsEvent(t *testing.T) {
	store := NewMemoryStore()
	service := newTestService(store)

	created, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:   "Reset VPN access",
		Subject: "user-1",
	})
	if err != nil {
		t.Fatalf("CreateRequest: %v", err)
	}

	response, err := service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId:    created.GetRequest().GetId(),
		NewStatus:    statusTriaged,
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if err != nil {
		t.Fatalf("UpdateRequestStatus: %v", err)
	}
	if response.GetRequest().GetStatus() != statusTriaged {
		t.Fatalf("status = %q, want triaged", response.GetRequest().GetStatus())
	}
	if response.GetRequest().GetId() != created.GetRequest().GetId() {
		t.Fatalf("id changed: %q", response.GetRequest().GetId())
	}

	if got := store.Requests()[0].Status; got != statusTriaged {
		t.Fatalf("stored status = %q, want triaged", got)
	}

	events := store.Events()
	change := events[len(events)-1]
	if change.EventType != eventTypeRequestStatusChanged {
		t.Fatalf("event type = %q", change.EventType)
	}
	if change.PreviousStatus != statusCreated {
		t.Fatalf("previous status = %q, want created", change.PreviousStatus)
	}
	if change.Request.Status != statusTriaged {
		t.Fatalf("event request status = %q", change.Request.Status)
	}
	if change.OccurredAt != fixedNow.Format("2006-01-02T15:04:05Z07:00") {
		t.Fatalf("occurred_at = %q", change.OccurredAt)
	}
}

func TestUpdateRequestStatusRequiresActor(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId: "11111111-1111-1111-1111-111111111111",
		NewStatus: statusTriaged,
	})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}

func TestUpdateRequestStatusRejectsUnknownStatus(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId:    "11111111-1111-1111-1111-111111111111",
		NewStatus:    "archived",
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if status.Code(err) != codes.InvalidArgument {
		t.Fatalf("code = %v, want InvalidArgument", status.Code(err))
	}
}

func TestUpdateRequestStatusUnknownRequestIsNotFound(t *testing.T) {
	service := newTestService(NewMemoryStore())
	_, err := service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId:    "99999999-9999-9999-9999-999999999999",
		NewStatus:    statusTriaged,
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if status.Code(err) != codes.NotFound {
		t.Fatalf("code = %v, want NotFound", status.Code(err))
	}
}

func TestUpdateRequestStatusRejectsIllegalTransition(t *testing.T) {
	service := newTestService(NewMemoryStore())
	created, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:   "t",
		Subject: "user-1",
	})
	if err != nil {
		t.Fatalf("CreateRequest: %v", err)
	}
	_, err = service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId:    created.GetRequest().GetId(),
		NewStatus:    statusResolved,
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("code = %v, want FailedPrecondition", status.Code(err))
	}
}

func TestUpdateRequestStatusRejectsNoOpTransition(t *testing.T) {
	service := newTestService(NewMemoryStore())
	created, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:   "t",
		Subject: "user-1",
	})
	if err != nil {
		t.Fatalf("CreateRequest: %v", err)
	}
	_, err = service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId:    created.GetRequest().GetId(),
		NewStatus:    statusCreated,
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("code = %v, want FailedPrecondition", status.Code(err))
	}
}

func TestUpdateRequestStatusTerminalStateRejectsFurtherChange(t *testing.T) {
	service := newTestService(NewMemoryStore())
	created, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:   "t",
		Subject: "user-1",
	})
	if err != nil {
		t.Fatalf("CreateRequest: %v", err)
	}
	id := created.GetRequest().GetId()
	for _, next := range []string{statusTriaged, statusInProgress, statusResolved, statusClosed} {
		if _, err := service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
			RequestId:    id,
			NewStatus:    next,
			ActorSubject: "operator-1",
			ActorRole:    roleOperator,
		}); err != nil {
			t.Fatalf("transition to %s: %v", next, err)
		}
	}
	_, err = service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId:    id,
		NewStatus:    statusCancelled,
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("code = %v, want FailedPrecondition", status.Code(err))
	}
}

func TestUpdateRequestStatusStoreFailureIsInternal(t *testing.T) {
	store := NewMemoryStore()
	service := newTestService(store)
	created, err := service.CreateRequest(context.Background(), &domainv1.CreateRequestRequest{
		Title:   "t",
		Subject: "user-1",
	})
	if err != nil {
		t.Fatalf("CreateRequest: %v", err)
	}
	store.failWith = errors.New("db down")
	_, err = service.UpdateRequestStatus(context.Background(), &domainv1.UpdateRequestStatusRequest{
		RequestId:    created.GetRequest().GetId(),
		NewStatus:    statusTriaged,
		ActorSubject: "operator-1",
		ActorRole:    roleOperator,
	})
	if status.Code(err) != codes.Internal {
		t.Fatalf("code = %v, want Internal", status.Code(err))
	}
}
