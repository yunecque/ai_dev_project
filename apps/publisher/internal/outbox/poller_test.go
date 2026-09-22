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
	published [][]byte
	err       error
}

func (f *fakePublisher) Publish(_ context.Context, subject string, data []byte) error {
	if f.err != nil {
		return f.err
	}
	f.subject = subject
	f.published = append(f.published, data)
	return nil
}

func TestPublishBatchPublishesAndMarksInOrder(t *testing.T) {
	store := &fakeStore{records: []Record{
		{EventID: "e1", EventType: "request-created", Payload: []byte("1")},
		{EventID: "e2", EventType: "request-created", Payload: []byte("2")},
	}}
	publisher := &fakePublisher{}
	poller := NewPoller(store, publisher, "requests.created", 0)

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

func TestPublishBatchRespectsLimit(t *testing.T) {
	store := &fakeStore{records: []Record{{EventID: "e1"}, {EventID: "e2"}, {EventID: "e3"}}}
	poller := NewPoller(store, &fakePublisher{}, "requests.created", 2)
	count, err := poller.PublishBatch(context.Background())
	if err != nil {
		t.Fatalf("PublishBatch: %v", err)
	}
	if count != 2 {
		t.Fatalf("count = %d, want 2", count)
	}
}

func TestPublishFailureStopsBeforeMarking(t *testing.T) {
	store := &fakeStore{records: []Record{{EventID: "e1"}, {EventID: "e2"}}}
	poller := NewPoller(store, &fakePublisher{err: errors.New("broker down")}, "requests.created", 0)
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
	poller := NewPoller(store, &fakePublisher{}, "requests.created", 0)
	if _, err := poller.PublishBatch(context.Background()); err == nil {
		t.Fatal("expected fetch error")
	}
}

func TestMarkFailureIsReturned(t *testing.T) {
	store := &fakeStore{records: []Record{{EventID: "e1"}}, markErr: errors.New("db down")}
	poller := NewPoller(store, &fakePublisher{}, "requests.created", 0)
	if _, err := poller.PublishBatch(context.Background()); err == nil {
		t.Fatal("expected mark error")
	}
}
