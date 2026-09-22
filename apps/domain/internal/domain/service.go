package domain

import (
	"context"
	"strings"
	"time"

	"github.com/google/uuid"
	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	maxTitleLen             = 200
	maxDescriptionLen       = 4000
	statusCreated           = "created"
	eventTypeRequestCreated = "request-created"
)

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
	EventID    string
	EventType  string
	OccurredAt string
	Request    Request
}

// Store persists a request together with its outbox event in one transaction.
type Store interface {
	CreateRequestWithEvent(ctx context.Context, request Request, event Event) error
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
	return &domainv1.CreateRequestResponse{
		Request: &domainv1.Request{
			Id:        request.ID,
			Title:     request.Title,
			Status:    request.Status,
			CreatedAt: request.CreatedAt,
		},
	}, nil
}

func validLength(value string, minLen, maxLen int) bool {
	length := len([]rune(value))
	return length >= minLen && length <= maxLen
}
