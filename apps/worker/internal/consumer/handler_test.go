package consumer

import (
	"context"
	"errors"
	"testing"
)

const sampleEvent = `{
  "event_id": "11111111-1111-1111-1111-111111111111",
  "event_type": "request-created",
  "occurred_at": "2026-09-22T00:00:00Z",
  "request": {"id": "22222222-2222-2222-2222-222222222222", "title": "t", "status": "created", "created_at": "2026-09-22T00:00:00Z"}
}`

type failingDedupe struct{ err error }

func (f failingDedupe) MarkProcessed(context.Context, string) (bool, error) {
	return false, f.err
}

func TestHandleAppliesFreshEventOnce(t *testing.T) {
	var applied []string
	handler := NewHandler(NewMemoryDedupe(), func(_ context.Context, event Event) error {
		applied = append(applied, event.Request.ID)
		return nil
	})
	ctx := context.Background()

	if err := handler.Handle(ctx, []byte(sampleEvent)); err != nil {
		t.Fatalf("first Handle: %v", err)
	}
	if err := handler.Handle(ctx, []byte(sampleEvent)); err != nil {
		t.Fatalf("duplicate Handle: %v", err)
	}
	if len(applied) != 1 {
		t.Fatalf("applied %d times, want 1 (idempotent)", len(applied))
	}
}

func TestHandleRejectsMalformedEvent(t *testing.T) {
	handler := NewHandler(NewMemoryDedupe(), func(context.Context, Event) error { return nil })
	if err := handler.Handle(context.Background(), []byte("not-json")); err == nil {
		t.Fatal("expected error for malformed event")
	}
}

func TestHandleRejectsMissingEventID(t *testing.T) {
	handler := NewHandler(NewMemoryDedupe(), func(context.Context, Event) error { return nil })
	if err := handler.Handle(context.Background(), []byte(`{"event_type":"request-created"}`)); err == nil {
		t.Fatal("expected error for missing event_id")
	}
}

func TestHandleRejectsUnsupportedType(t *testing.T) {
	handler := NewHandler(NewMemoryDedupe(), func(context.Context, Event) error { return nil })
	payload := `{"event_id":"33333333-3333-3333-3333-333333333333","event_type":"request-deleted"}`
	if err := handler.Handle(context.Background(), []byte(payload)); err == nil {
		t.Fatal("expected error for unsupported event type")
	}
}

func TestHandlePropagatesDedupeError(t *testing.T) {
	handler := NewHandler(failingDedupe{err: errors.New("db down")}, func(context.Context, Event) error { return nil })
	if err := handler.Handle(context.Background(), []byte(sampleEvent)); err == nil {
		t.Fatal("expected dedupe error")
	}
}

func TestHandlePropagatesApplyError(t *testing.T) {
	handler := NewHandler(NewMemoryDedupe(), func(context.Context, Event) error {
		return errors.New("apply failed")
	})
	if err := handler.Handle(context.Background(), []byte(sampleEvent)); err == nil {
		t.Fatal("expected apply error")
	}
}
