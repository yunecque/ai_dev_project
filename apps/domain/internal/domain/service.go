package domain

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/google/uuid"
	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	maxTitleLen       = 200
	maxDescriptionLen = 4000

	statusCreated    = "created"
	statusTriaged    = "triaged"
	statusInProgress = "in_progress"
	statusResolved   = "resolved"
	statusClosed     = "closed"
	statusCancelled  = "cancelled"

	eventTypeRequestCreated       = "request-created"
	eventTypeRequestStatusChanged = "request-status-changed"
)

// ErrRequestNotFound is returned by a Store when the request id is unknown.
var ErrRequestNotFound = errors.New("request not found")

// transitions is the request lifecycle state machine. Terminal states map to empty slices.
var transitions = map[string][]string{
	statusCreated:    {statusTriaged, statusCancelled},
	statusTriaged:    {statusInProgress, statusCancelled},
	statusInProgress: {statusResolved, statusCancelled},
	statusResolved:   {statusClosed},
	statusClosed:     {},
	statusCancelled:  {},
}

// CanTransition reports whether the lifecycle allows moving from one status to another.
// Unknown statuses and no-op transitions are rejected.
func CanTransition(from, to string) bool {
	targets, ok := transitions[from]
	if !ok {
		return false
	}
	for _, target := range targets {
		if target == to {
			return true
		}
	}
	return false
}

// Request is the persisted aggregate.
type Request struct {
	ID          string
	Title       string
	Description string
	Subject     string
	Status      string
	CreatedAt   string
}

// Event is a domain event persisted to the transactional outbox.
type Event struct {
	EventID        string
	EventType      string
	OccurredAt     string
	Request        Request
	PreviousStatus string
}

// Store persists requests together with their outbox events atomically.
type Store interface {
	CreateRequestWithEvent(ctx context.Context, request Request, event Event) error
	GetRequest(ctx context.Context, id string) (Request, error)
	UpdateRequestStatusWithEvent(ctx context.Context, request Request, event Event) error
}

// Service implements the DomainService gRPC contract.
type Service struct {
	domainv1.UnimplementedDomainServiceServer
	store Store
	now   func() time.Time
	newID func() string
}

func NewService(store Store) *Service {
	return &Service{
		store: store,
		now:   func() time.Time { return time.Now().UTC() },
		newID: func() string { return uuid.NewString() },
	}
}

func (s *Service) CreateRequest(ctx context.Context, in *domainv1.CreateRequestRequest) (*domainv1.CreateRequestResponse, error) {
	title := strings.TrimSpace(in.GetTitle())
	if !validLength(title, 1, maxTitleLen) {
		return nil, status.Error(codes.InvalidArgument, "title must be between 1 and 200 characters")
	}
	if len([]rune(in.GetDescription())) > maxDescriptionLen {
		return nil, status.Error(codes.InvalidArgument, "description exceeds maximum length")
	}
	if in.GetSubject() == "" {
		return nil, status.Error(codes.InvalidArgument, "subject is required")
	}

	occurredAt := s.now().Format(time.RFC3339)
	request := Request{
		ID:          s.newID(),
		Title:       title,
		Description: in.GetDescription(),
		Subject:     in.GetSubject(),
		Status:      statusCreated,
		CreatedAt:   occurredAt,
	}
	event := Event{
		EventID:    s.newID(),
		EventType:  eventTypeRequestCreated,
		OccurredAt: occurredAt,
		Request:    request,
	}
	if err := s.store.CreateRequestWithEvent(ctx, request, event); err != nil {
		return nil, status.Error(codes.Internal, "failed to persist request")
	}
	return &domainv1.CreateRequestResponse{Request: requestProto(request)}, nil
}

// UpdateRequestStatus applies a lifecycle transition to an existing request and records a
// request-status-changed event in the outbox within the same transaction.
func (s *Service) UpdateRequestStatus(
	ctx context.Context, in *domainv1.UpdateRequestStatusRequest,
) (*domainv1.UpdateRequestStatusResponse, error) {
	requestID := strings.TrimSpace(in.GetRequestId())
	if requestID == "" {
		return nil, status.Error(codes.InvalidArgument, "request_id is required")
	}
	if strings.TrimSpace(in.GetActorSubject()) == "" {
		return nil, status.Error(codes.InvalidArgument, "actor subject is required")
	}
	newStatus := strings.TrimSpace(in.GetNewStatus())
	if _, known := transitions[newStatus]; !known {
		return nil, status.Error(codes.InvalidArgument, "unknown target status")
	}

	current, err := s.store.GetRequest(ctx, requestID)
	if errors.Is(err, ErrRequestNotFound) {
		return nil, status.Error(codes.NotFound, "request not found")
	}
	if err != nil {
		return nil, status.Error(codes.Internal, "failed to load request")
	}
	if !CanTransition(current.Status, newStatus) {
		return nil, status.Errorf(
			codes.FailedPrecondition, "illegal transition %s -> %s", current.Status, newStatus,
		)
	}

	occurredAt := s.now().Format(time.RFC3339)
	updated := current
	updated.Status = newStatus
	event := Event{
		EventID:        s.newID(),
		EventType:      eventTypeRequestStatusChanged,
		OccurredAt:     occurredAt,
		Request:        updated,
		PreviousStatus: current.Status,
	}
	if err := s.store.UpdateRequestStatusWithEvent(ctx, updated, event); err != nil {
		return nil, status.Error(codes.Internal, "failed to persist status change")
	}
	return &domainv1.UpdateRequestStatusResponse{Request: requestProto(updated)}, nil
}

func requestProto(request Request) *domainv1.Request {
	return &domainv1.Request{
		Id:        request.ID,
		Title:     request.Title,
		Status:    request.Status,
		CreatedAt: request.CreatedAt,
	}
}

func validLength(value string, minLen, maxLen int) bool {
	length := len([]rune(value))
	return length >= minLen && length <= maxLen
}
