package domain

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
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

type statusChangedPayload struct {
	EventID    string       `json:"event_id"`
	EventType  string       `json:"event_type"`
	OccurredAt string       `json:"occurred_at"`
	Request    statusChange `json:"request"`
}

type statusChange struct {
	ID             string `json:"id"`
	Status         string `json:"status"`
	PreviousStatus string `json:"previous_status"`
	UpdatedAt      string `json:"updated_at"`
}

// buildPayload serialises an event using the payload shape required by its contract.
func buildPayload(event Event) ([]byte, error) {
	switch event.EventType {
	case eventTypeRequestCreated:
		return json.Marshal(outboxPayload{
			EventID:    event.EventID,
			EventType:  event.EventType,
			OccurredAt: event.OccurredAt,
			Request: requestRecord{
				ID:        event.Request.ID,
				Title:     event.Request.Title,
				Status:    event.Request.Status,
				CreatedAt: event.Request.CreatedAt,
			},
		})
	case eventTypeRequestStatusChanged:
		return json.Marshal(statusChangedPayload{
			EventID:    event.EventID,
			EventType:  event.EventType,
			OccurredAt: event.OccurredAt,
			Request: statusChange{
				ID:             event.Request.ID,
				Status:         event.Request.Status,
				PreviousStatus: event.PreviousStatus,
				UpdatedAt:      event.OccurredAt,
			},
		})
	default:
		return nil, fmt.Errorf("unsupported event type %q", event.EventType)
	}
}

func (p *PostgresStore) CreateRequestWithEvent(ctx context.Context, request Request, event Event) error {
	payload, err := buildPayload(event)
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

	if err := insertOutbox(ctx, tx, event, payload); err != nil {
		return err
	}

	return tx.Commit(ctx)
}

func (p *PostgresStore) GetRequest(ctx context.Context, id string) (Request, error) {
	var (
		request   Request
		createdAt time.Time
	)
	err := p.pool.QueryRow(ctx,
		`SELECT id, title, description, subject, status, created_at FROM requests WHERE id = $1`,
		id,
	).Scan(&request.ID, &request.Title, &request.Description, &request.Subject, &request.Status, &createdAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return Request{}, ErrRequestNotFound
	}
	if err != nil {
		return Request{}, err
	}
	request.CreatedAt = createdAt.UTC().Format(time.RFC3339)
	return request, nil
}

func (p *PostgresStore) ListRequests(ctx context.Context, filter ListFilter) ([]Request, error) {
	limit := filter.Limit
	if limit <= 0 {
		limit = defaultListLimit
	}
	rows, err := p.pool.Query(ctx,
		`SELECT id, title, description, subject, status, created_at
		 FROM requests
		 WHERE ($1 = '' OR status = $1)
		   AND ($2 = '' OR subject = $2)
		 ORDER BY created_at DESC, id DESC
		 LIMIT $3`,
		filter.Status, filter.Subject, limit,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []Request
	for rows.Next() {
		var (
			request   Request
			createdAt time.Time
		)
		if err := rows.Scan(
			&request.ID, &request.Title, &request.Description, &request.Subject, &request.Status, &createdAt,
		); err != nil {
			return nil, err
		}
		request.CreatedAt = createdAt.UTC().Format(time.RFC3339)
		out = append(out, request)
	}
	return out, rows.Err()
}

func (p *PostgresStore) UpdateRequestStatusWithEvent(ctx context.Context, request Request, event Event) error {
	payload, err := buildPayload(event)
	if err != nil {
		return err
	}

	tx, err := p.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	tag, err := tx.Exec(ctx, `UPDATE requests SET status = $2 WHERE id = $1`, request.ID, request.Status)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return ErrRequestNotFound
	}

	if err := insertOutbox(ctx, tx, event, payload); err != nil {
		return err
	}

	return tx.Commit(ctx)
}

func insertOutbox(ctx context.Context, tx pgx.Tx, event Event, payload []byte) error {
	_, err := tx.Exec(ctx,
		`INSERT INTO outbox (event_id, event_type, occurred_at, payload)
		 VALUES ($1, $2, $3, $4)`,
		event.EventID, event.EventType, event.OccurredAt, payload,
	)
	return err
}
