package outbox

import (
	"context"

	"github.com/nats-io/nats.go"
)

// NATSPublisher publishes payloads to a NATS JetStream subject.
type NATSPublisher struct {
	jetstream nats.JetStreamContext
}

func NewNATSPublisher(jetstream nats.JetStreamContext) *NATSPublisher {
	return &NATSPublisher{jetstream: jetstream}
}

func (p *NATSPublisher) Publish(_ context.Context, subject string, data []byte) error {
	_, err := p.jetstream.Publish(subject, data)
	return err
}
