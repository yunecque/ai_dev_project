package consumer

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

// PostgresDedupe records processed event ids in a table with a unique constraint.
type PostgresDedupe struct {
	pool *pgxpool.Pool
}

func NewPostgresDedupe(pool *pgxpool.Pool) *PostgresDedupe {
	return &PostgresDedupe{pool: pool}
}

func (d *PostgresDedupe) MarkProcessed(ctx context.Context, eventID string) (bool, error) {
	tag, err := d.pool.Exec(ctx,
		`INSERT INTO processed_events (event_id) VALUES ($1::uuid)
		 ON CONFLICT (event_id) DO NOTHING`, eventID)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}
