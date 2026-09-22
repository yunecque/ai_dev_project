package outbox

import (
	"context"
	"errors"
	"testing"
)

type fakeStore struct {
	records  []Record
	marked   []string
	fetchErr error
	markErr  error
}

func (f *fakeStore) FetchUnpublished(_ context.Context, limit int) ([]Record, error) {
	if f.fetchErr != nil {
		return nil, f.fetchErr
	}
	if limit > 0 && len(f.records) > limit {
		return f.records[:limit], nil
	}
	return f.records, nil
}

func (f *fakeStore) MarkPublished(_ context.Context, eventID string) error {
	if f.markErr != nil {
		return f.markErr
	}
	f.marked = append(f.marked, eventID)
	return nil
}

type fakePublisher struct {
	subject   string
	subjects  []string
	published [][]byte
	err       error
}

func (f *fakePublisher) Publish(_ context.Context, subject string, data []byte) error {
	if f.err != nil {
		return f.err
	}
	f.subject = subject
	f.subjects = append(f.subjects, subject)
	f.published = append(f.published, data)
	return nil
}

var testRoutes = map[string]string{
	"request-created":        "requests.created",
	"request-status-changed": "requests.status-changed",
}

func TestPublishBatchPublishesAndMarksInOrder(t *testing.T) {
	store := &fakeStore{records: []Record{
		{EventID: "e1", EventType: "request-created", Payload: []byte("1")},
		{EventID: "e2", EventType: "request-created", Payload: []byte("2")},
	}}
	publisher := &fakePublisher{}
	poller := NewPoller(store, publisher, testRoutes, 0)

	count, err := poller.PublishBatch(context.Background())
	if err != nil {
		t.Fatalf("PublishBatch: %v", err)
	}
	if count != 2 {
		t.Fatalf("count = %d, want 2", count)
	}
	if len(publisher.published) != 2 || publisher.subject != "requests.created" {
		t.Fatalf("unexpected publish: subject=%q n=%d", publisher.subject, len(publisher.published))
	}
	if len(store.marked) != 2 || store.marked[0] != "e1" || store.marked[1] != "e2" {
		t.Fatalf("unexpected marked: %v", store.marked)
	}
}

func TestPublishBatchRoutesByEventType(t *testing.T) {
	store := &fakeStore{records: []Record{
		{EventID: "e1", EventType: "request-created", Payload: []byte("1")},
		{EventID: "e2", EventType: "request-status-changed", Payload: []byte("2")},
	}}
	publisher := &fakePublisher{}
	poller := NewPoller(store, publisher, testRoutes, 0)

	if _, err := poller.PublishBatch(context.Background()); err != nil {
		t.Fatalf("PublishBatch: %v", err)
	}
	if publisher.subjects[0] != "requests.created" || publisher.subjects[1] != "requests.status-changed" {
		t.Fatalf("subjects = %v", publisher.subjects)
	}
}

func TestPublishBatchRejectsUnknownEventType(t *testing.T) {
	store := &fakeStore{records: []Record{{EventID: "e1", EventType: "mystery", Payload: []byte("1")}}}
	publisher := &fakePublisher{}
	poller := NewPoller(store, publisher, testRoutes, 0)

	count, err := poller.PublishBatch(context.Background())
	if err == nil {
		t.Fatal("expected error for unroutable event type")
	}
	if count != 0 || len(publisher.published) != 0 || len(store.marked) != 0 {
		t.Fatalf("nothing should be published/marked: count=%d", count)
	}
}

func TestPublishBatchRespectsLimit(t *testing.T) {
	store := &fakeStore{records: []Record{
		{EventID: "e1", EventType: "request-created"},
		{EventID: "e2", EventType: "request-created"},
		{EventID: "e3", EventType: "request-created"},
	}}
	poller := NewPoller(store, &fakePublisher{}, testRoutes, 2)
	count, err := poller.PublishBatch(context.Background())
	if err != nil {
		t.Fatalf("PublishBatch: %v", err)
	}
	if count != 2 {
		t.Fatalf("count = %d, want 2", count)
	}
}

func TestPublishFailureStopsBeforeMarking(t *testing.T) {
	store := &fakeStore{records: []Record{
		{EventID: "e1", EventType: "request-created"},
		{EventID: "e2", EventType: "request-created"},
	}}
	poller := NewPoller(store, &fakePublisher{err: errors.New("broker down")}, testRoutes, 0)
	count, err := poller.PublishBatch(context.Background())
	if err == nil {
		t.Fatal("expected error")
	}
	if count != 0 {
		t.Fatalf("count = %d, want 0", count)
	}
	if len(store.marked) != 0 {
		t.Fatalf("nothing should be marked on publish failure: %v", store.marked)
	}
}

func TestFetchFailureIsReturned(t *testing.T) {
	store := &fakeStore{fetchErr: errors.New("db down")}
	poller := NewPoller(store, &fakePublisher{}, testRoutes, 0)
	if _, err := poller.PublishBatch(context.Background()); err == nil {
		t.Fatal("expected fetch error")
	}
}

func TestMarkFailureIsReturned(t *testing.T) {
	store := &fakeStore{records: []Record{{EventID: "e1", EventType: "request-created"}}, markErr: errors.New("db down")}
	poller := NewPoller(store, &fakePublisher{}, testRoutes, 0)
	if _, err := poller.PublishBatch(context.Background()); err == nil {
		t.Fatal("expected mark error")
	}
}
