package domain

import (
	"context"
	"encoding/json"

	"github.com/jackc/pgx/v5/pgxpool"
)

// PostgresStore persists requests and outbox events atomically (ADR-0003).
type PostgresStore struct {
	pool *pgxpool.Pool
}

func NewPostgresStore(ctx context.Context, dsn string) (*PostgresStore, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return &PostgresStore{pool: pool}, nil
}

func (p *PostgresStore) Close() {
	p.pool.Close()
}

type outboxPayload struct {
	EventID    string        `json:"event_id"`
	EventType  string        `json:"event_type"`
	OccurredAt string        `json:"occurred_at"`
	Request    requestRecord `json:"request"`
}

type requestRecord struct {
	ID        string `json:"id"`
	Title     string `json:"title"`
	Status    string `json:"status"`
	CreatedAt string `json:"created_at"`
}

func (p *PostgresStore) CreateRequestWithEvent(ctx context.Context, request Request, event Event) error {
	payload, err := json.Marshal(outboxPayload{
		EventID:    event.EventID,
		EventType:  event.EventType,
		OccurredAt: event.OccurredAt,
		Request: requestRecord{
			ID:        request.ID,
			Title:     request.Title,
			Status:    request.Status,
			CreatedAt: request.CreatedAt,
		},
	})
	if err != nil {
		return err
	}

	tx, err := p.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	if _, err := tx.Exec(ctx,
		`INSERT INTO requests (id, title, description, subject, status, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6)`,
		request.ID, request.Title, request.Description, request.Subject, request.Status, request.CreatedAt,
	); err != nil {
		return err
	}

	if _, err := tx.Exec(ctx,
		`INSERT INTO outbox (event_id, event_type, occurred_at, payload)
		 VALUES ($1, $2, $3, $4)`,
		event.EventID, event.EventType, event.OccurredAt, payload,
	); err != nil {
		return err
	}

	return tx.Commit(ctx)
}
