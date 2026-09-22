// Package outbox polls the transactional outbox and publishes events to a broker.
package outbox

import (
	"context"
	"fmt"
)

const DefaultBatchSize = 100

// Record is an unpublished outbox row.
type Record struct {
	EventID   string
	EventType string
	Payload   []byte
}

// Store reads unpublished rows and marks them published.
type Store interface {
	FetchUnpublished(ctx context.Context, limit int) ([]Record, error)
	MarkPublished(ctx context.Context, eventID string) error
}

// Publisher delivers a raw payload to a subject.
type Publisher interface {
	Publish(ctx context.Context, subject string, data []byte) error
}

// Poller publishes unpublished outbox records in order.
type Poller struct {
	store     Store
	publisher Publisher
	subject   string
	limit     int
}

func NewPoller(store Store, publisher Publisher, subject string, limit int) *Poller {
	if limit <= 0 {
		limit = DefaultBatchSize
	}
	return &Poller{store: store, publisher: publisher, subject: subject, limit: limit}
}

// PublishBatch publishes up to one batch. On the first publish/mark failure it stops and
// returns the number already published plus the error; already-marked rows are not re-published.
func (p *Poller) PublishBatch(ctx context.Context) (int, error) {
	records, err := p.store.FetchUnpublished(ctx, p.limit)
	if err != nil {
		return 0, fmt.Errorf("fetch unpublished: %w", err)
	}
	published := 0
	for _, record := range records {
		if err := p.publisher.Publish(ctx, p.subject, record.Payload); err != nil {
			return published, fmt.Errorf("publish %s: %w", record.EventID, err)
		}
		if err := p.store.MarkPublished(ctx, record.EventID); err != nil {
			return published, fmt.Errorf("mark published %s: %w", record.EventID, err)
		}
		published++
	}
	return published, nil
}
