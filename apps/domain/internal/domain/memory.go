package domain

import (
	"context"
	"errors"
	"sort"
	"sync"
)

// MemoryStore is an in-memory Store used for tests and local development.
type MemoryStore struct {
	mu       sync.Mutex
	requests map[string]Request
	events   []Event
	failWith error
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{requests: make(map[string]Request)}
}

func (m *MemoryStore) CreateRequestWithEvent(_ context.Context, request Request, event Event) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.failWith != nil {
		return m.failWith
	}
	if _, exists := m.requests[request.ID]; exists {
		return errors.New("duplicate request id")
	}
	m.requests[request.ID] = request
	m.events = append(m.events, event)
	return nil
}

func (m *MemoryStore) GetRequest(_ context.Context, id string) (Request, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.failWith != nil {
		return Request{}, m.failWith
	}
	request, exists := m.requests[id]
	if !exists {
		return Request{}, ErrRequestNotFound
	}
	return request, nil
}

func (m *MemoryStore) UpdateRequestStatusWithEvent(_ context.Context, request Request, event Event) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.failWith != nil {
		return m.failWith
	}
	if _, exists := m.requests[request.ID]; !exists {
		return ErrRequestNotFound
	}
	m.requests[request.ID] = request
	m.events = append(m.events, event)
	return nil
}

func (m *MemoryStore) ListRequests(_ context.Context, filter ListFilter) ([]Request, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.failWith != nil {
		return nil, m.failWith
	}
	out := make([]Request, 0, len(m.requests))
	for _, request := range m.requests {
		if filter.Status != "" && request.Status != filter.Status {
			continue
		}
		if filter.Subject != "" && request.Subject != filter.Subject {
			continue
		}
		out = append(out, request)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].CreatedAt != out[j].CreatedAt {
			return out[i].CreatedAt > out[j].CreatedAt
		}
		return out[i].ID > out[j].ID
	})
	if filter.Limit > 0 && len(out) > filter.Limit {
		out = out[:filter.Limit]
	}
	return out, nil
}

func (m *MemoryStore) Requests() []Request {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]Request, 0, len(m.requests))
	for _, request := range m.requests {
		out = append(out, request)
	}
	return out
}

func (m *MemoryStore) Events() []Event {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]Event, len(m.events))
	copy(out, m.events)
	return out
}
