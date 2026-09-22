package outbox

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

// PostgresStore reads and marks rows in the transactional outbox.
type PostgresStore struct {
	pool *pgxpool.Pool
}

func NewPostgresStore(pool *pgxpool.Pool) *PostgresStore {
	return &PostgresStore{pool: pool}
}

func (s *PostgresStore) FetchUnpublished(ctx context.Context, limit int) ([]Record, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT event_id::text, event_type, payload
		   FROM outbox
		  WHERE published_at IS NULL
		  ORDER BY occurred_at
		  LIMIT $1`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var records []Record
	for rows.Next() {
		var record Record
		if err := rows.Scan(&record.EventID, &record.EventType, &record.Payload); err != nil {
			return nil, err
		}
		records = append(records, record)
	}
	return records, rows.Err()
}

func (s *PostgresStore) MarkPublished(ctx context.Context, eventID string) error {
	_, err := s.pool.Exec(ctx,
		`UPDATE outbox SET published_at = now() WHERE event_id = $1::uuid`, eventID)
	return err
}
