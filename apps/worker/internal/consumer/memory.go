package consumer

import (
	"context"
	"sync"
)

// MemoryDedupe is an in-memory Dedupe for tests and local development.
type MemoryDedupe struct {
	mu   sync.Mutex
	seen map[string]struct{}
}

func NewMemoryDedupe() *MemoryDedupe {
	return &MemoryDedupe{seen: make(map[string]struct{})}
}

func (m *MemoryDedupe) MarkProcessed(_ context.Context, eventID string) (bool, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.seen[eventID]; ok {
		return false, nil
	}
	m.seen[eventID] = struct{}{}
	return true, nil
}
