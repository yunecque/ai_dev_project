// Package consumer handles domain events idempotently.
package consumer

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
)

const EventTypeRequestCreated = "request-created"

// Event is the wire representation of a domain event.
type Event struct {
	EventID    string       `json:"event_id"`
	EventType  string       `json:"event_type"`
	OccurredAt string       `json:"occurred_at"`
	Request    EventRequest `json:"request"`
}

type EventRequest struct {
	ID        string `json:"id"`
	Title     string `json:"title"`
	Status    string `json:"status"`
	CreatedAt string `json:"created_at"`
}

// Dedupe records an event id and reports whether it is new (idempotency gate).
type Dedupe interface {
	MarkProcessed(ctx context.Context, eventID string) (bool, error)
}

// Applier performs the side effect for a fresh event.
type Applier func(ctx context.Context, event Event) error

// Handler validates, deduplicates, and applies events exactly once.
type Handler struct {
	dedupe Dedupe
	apply  Applier
}

func NewHandler(dedupe Dedupe, apply Applier) *Handler {
	return &Handler{dedupe: dedupe, apply: apply}
}

func (h *Handler) Handle(ctx context.Context, data []byte) error {
	var event Event
	if err := json.Unmarshal(data, &event); err != nil {
		return fmt.Errorf("malformed event: %w", err)
	}
	if event.EventID == "" {
		return errors.New("event_id is required")
	}
	if event.EventType != EventTypeRequestCreated {
		return fmt.Errorf("unsupported event type %q", event.EventType)
	}
	fresh, err := h.dedupe.MarkProcessed(ctx, event.EventID)
	if err != nil {
		return fmt.Errorf("dedupe: %w", err)
	}
	if !fresh {
		return nil
	}
	return h.apply(ctx, event)
}
